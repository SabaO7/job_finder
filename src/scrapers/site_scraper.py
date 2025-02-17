import os
import re
import time
import asyncio
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from src.logger import setup_logger
from src.services.crewai_llm_service import CrewAILLMService
from src.services.google_sheets_service import GoogleSheetsService
from src.services.airtable_service import AirtableService
from urllib.parse import urljoin
from src.scrapers.langchain_agent import find_jobs
from src.logger import setup_logger




logger = setup_logger(__name__)
MAX_RETRIES = 3


class SiteScraper:
    """Scrapes job postings using LangChain Agent."""

    def __init__(self, config=None):
        self.config = config or {}

    async def scrape_company_jobs(self, company_url):
        """Uses the LangChain Agent to scrape jobs."""
        logger.info(f"Starting agent-driven job scrape for {company_url}")
        jobs = find_jobs(company_url)
        
        if not jobs:
            logger.warning(f"❌ No jobs found for {company_url}")
        else:
            logger.info(f"✅ {len(jobs)} jobs found for {company_url}")

        return jobs

    def find_careers_pages(self, company_url):
        """Find careers pages by scanning the homepage and extracting valid links."""
        careers_pages = []
        response = self._get_with_retries(company_url)
        if not response:
            return [company_url]

        soup = BeautifulSoup(response.text, "lxml")
        links = soup.find_all("a", href=True)

        for a_tag in links:
            href = a_tag["href"]

            # Ensure we don't append invalid mixed URLs
            if href.startswith("https") or href.startswith("http"):
                full_url = href
            else:
                full_url = self._build_absolute_url(company_url, href)

            if re.search(r"careers|jobs|join-our-team|join-us", full_url, re.IGNORECASE):
                if full_url not in careers_pages:
                    careers_pages.append(full_url)

        return careers_pages if careers_pages else [company_url]



    def _find_deep_career_pages(self, career_page_url):
        """
        Detects deeper career/job links inside career pages.
        Example: Redirects like https://careers.amd.com/careers-home → https://careers.amd.com/careers-home/jobs
        """
        deep_links = []
        response = self._get_with_retries(career_page_url)
        if not response:
            return []

        soup = BeautifulSoup(response.text, "lxml")
        links = soup.find_all("a", href=True)

        for a_tag in links:
            href = a_tag["href"]
            if re.search(r"jobs|positions|careers-home", href, re.IGNORECASE):
                full_url = self._build_absolute_url(career_page_url, href)
                if full_url not in deep_links:
                    deep_links.append(full_url)

        return deep_links


    async def _scrape_jobs_with_fallback(self, url, company_url):
        """
        Scrapes jobs using:
        1️⃣ Naïve BeautifulSoup (if page is static)
        2️⃣ Playwright for JavaScript-rendered job listings
        3️⃣ LLM fallback (if all else fails)
        4️⃣ Handles multi-step career pages & pagination
        """

        logger.info(f"Starting job scrape for {url}")

        # 1️⃣ Detect if there’s a deeper job page
        job_page_urls = self._find_deep_career_pages(url)
        if job_page_urls:
            logger.info(f"Detected deeper job page(s) for {company_url}: {job_page_urls}")
        else:
            job_page_urls = [url]  # Fallback to the original URL

        all_jobs = []

        for job_page_url in job_page_urls:
            logger.info(f"Scraping job page: {job_page_url}")

            # 2️⃣ Try Naïve Parsing First (for static job pages)
            jobs = self._naive_parse_job_page(job_page_url, company_url)
            if jobs:
                logger.info(f"✅ [Naïve] Found {len(jobs)} jobs on {job_page_url}")
                all_jobs.extend(jobs)
                continue  # Skip Playwright if we already got jobs

            # 3️⃣ Try Playwright for JavaScript-Rendered Job Pages
            playwright_jobs = await self._playwright_scrape_jobs(job_page_url, company_url)
            if playwright_jobs:
                logger.info(f"✅ [Playwright] Found {len(playwright_jobs)} jobs on {job_page_url}")
                all_jobs.extend(playwright_jobs)
                continue  # Skip LLM if we already got jobs

        # 4️⃣ If No Jobs Found, Use LLM as Last Resort
        if not all_jobs and self.use_llm and self.llm_service:
            logger.warning(f"⚠️ [LLM] Attempting LLM extraction for {company_url}")
            llm_jobs = await self.llm_service.parse_jobs_with_llm(company_url)
            if llm_jobs:
                logger.info(f"✅ [LLM] Extracted {len(llm_jobs)} jobs for {company_url}")
                all_jobs.extend(llm_jobs)
            else:
                logger.warning(f"❌ [LLM] No jobs found via LLM for {company_url}")

        # 5️⃣ Final logging for clarity
        if all_jobs:
            logger.info(f"🎯 Successfully scraped {len(all_jobs)} jobs from {company_url}")
        else:
            logger.warning(f"❌ No jobs found for {company_url} after all methods.")

        return all_jobs

    def naive_scrape(self, url, company_url):
        """Basic requests + BeautifulSoup scraping method."""
        jobs = []
        response = self._get_with_retries(url)
        if not response:
            logger.warning(f"❌ [Naïve] Failed to load {url} (Skipping)")
            return jobs

        soup = BeautifulSoup(response.text, "lxml")
        job_elems = soup.select("[class*=job], [class*=position]")

        if not job_elems:
            logger.warning(f"❌ [Naïve] No job elements found on {url}")

        for elem in job_elems:
            job_data = self._extract_job_data(elem, company_url, url)
            if job_data:
                jobs.append(job_data)

        return jobs


    async def playwright_scrape(self, url, company_url, max_pages=3):
        """Uses Playwright to scrape JavaScript-rendered job listings, handling pagination and iframes."""
        jobs = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                logger.info(f"🌐 [Playwright] Visiting {url}")
                await page.goto(url, timeout=30_000)  # 30-second timeout

                for page_num in range(1, max_pages + 1):
                    await page.wait_for_selector("body", timeout=5000)

                    # ✅ **Fix: Check if the page contains an iframe with job listings**
                    if len(page.frames) > 1:  
                        frame = page.frames[1]  # Get second frame (first is main)
                    else:
                        frame = page.main_frame  # Default to main frame
                    
                    content = await frame.content()  # Get page/iframe HTML
                    soup = BeautifulSoup(content, "lxml")
                    
                    job_elems = soup.select("[class*=job], [class*=position], [class*=listing]")
                    if not job_elems:
                        logger.warning(f"❌ [Playwright] No job listings found on page {page_num} at {url}")
                        break

                    for elem in job_elems:
                        job_data = self._extract_job_data(elem, company_url, url)
                        if job_data:
                            jobs.append(job_data)

                    logger.info(f"✅ [Playwright] Found {len(job_elems)} jobs on page {page_num} of {url}")

                    # Try clicking 'Next Page' if pagination exists
                    next_button = await page.query_selector("a[aria-label='Next'], a.next, button.next")
                    if next_button:
                        await next_button.click()
                        await asyncio.sleep(3)  # Wait before the next request
                    else:
                        break  # No more pages, exit loop

            except Exception as e:
                logger.error(f"❌ [Playwright] Error parsing {url}: {e}", exc_info=True)

            finally:
                await browser.close()

        if not jobs:
            logger.warning(f"❌ [Playwright] No jobs found for {url} after checking {max_pages} pages.")

        return jobs
    
    async def llm_extract(self, url, company_url):
        """Uses an LLM to extract job listings if other methods fail."""
        if self.llm_service:
            response = await self.llm_service.parse_jobs_with_llm(url)
            return [
                {"title": job.get("title", "Unknown"), "company": company_url, "url": url}
                for job in response
            ]
        return []



    def _extract_job_data(self, elem, company_url, source_url):
        """Extracts job title and job link."""
        title = elem.get_text(strip=True)[:50] if elem else None
        return {"company": company_url, "title": title, "url": source_url} if title else None

    def _get_with_retries(self, url, timeout=30):
        """Retries GET requests up to MAX_RETRIES times in case of failure. Detects and follows redirects."""
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(url, timeout=timeout, allow_redirects=True)  # ✅ Allow redirects

                if response.status_code == 200:
                    if response.history:  # Detects if the request was redirected
                        logger.info(f"Redirected: {url} → {response.url}")
                        return requests.get(response.url, timeout=timeout)  # Fetch final redirected URL

                    return response

                logger.warning(f"Request to {url} returned status {response.status_code}, retrying...")

            except requests.exceptions.RequestException as e:
                logger.warning(f"Error fetching {url}: {e}. Retry {attempt + 1}/{MAX_RETRIES}")

            time.sleep(2 ** attempt)  # Exponential backoff

        return None  # Return None if all retries fail


    def _build_absolute_url(self, base_url, relative_path):
        """Converts a relative URL into an absolute URL, but keeps absolute URLs unchanged."""
        
        if relative_path.startswith("http"):
            return relative_path  # Already a full URL, return as is

        return urljoin(base_url, relative_path)  # Properly join base and relative URLs


    async def _batch_process_jobs(self):
        """Sends filtered jobs to Google Sheets & Airtable after every 5 websites."""
        if not self.scraped_jobs:
            return

        logger.info(f"Processing batch of {len(self.scraped_jobs)} jobs...")

        from src.filters import filter_jobs  # Ensure it's imported correctly
        job_filters = self.config.get("job_filters", {})
        filtered_jobs = filter_jobs(self.scraped_jobs, job_filters)

        if filtered_jobs:
            if self.google_sheets:
                self.google_sheets.append_rows(filtered_jobs)
            self.airtable.append_records(filtered_jobs)
            logger.info(f"Successfully saved {len(filtered_jobs)} jobs to Google Sheets & Airtable.")

        # Clear buffer after processing
        self.scraped_jobs = []

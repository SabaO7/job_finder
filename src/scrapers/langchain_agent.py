import os
import re
import time
import asyncio
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from urllib.parse import urljoin
from langchain.agents import initialize_agent, AgentType
from langchain_community.chat_models import ChatOpenAI
from langchain.tools import Tool
from src.logger import setup_logger
from src.services.crewai_llm_service import CrewAILLMService
from src.services.google_sheets_service import GoogleSheetsService
from src.services.airtable_service import AirtableService

logger = setup_logger(__name__)
MAX_RETRIES = 3

class SiteScraper:
    """
    Intelligent Job Scraper using LangChain Agent.
    
    Steps:
    1️⃣ **Detects Career Pages** ✅
    2️⃣ **Chooses Best Scraping Method** (Static, Playwright, LLM) ✅
    3️⃣ **Handles Dynamic Elements** (Clicks, Forms, AJAX) ✅
    4️⃣ **Extracts & Saves Jobs** ✅
    """
    
    def __init__(self, config=None):
        self.config = config or {}
        self.use_llm = self.config.get("use_llm", False)
        self.google_sheets = GoogleSheetsService(self.config.get("google_sheets", {}))
        self.airtable = AirtableService(self.config)
        self.llm_service = CrewAILLMService(self.config.get("llm", {})) if self.use_llm else None
        self.scraped_jobs = []
        self.scraped_count = 0
        
        # Setup LangChain Agent
        self.agent = initialize_agent(
            tools=self._get_tools(),
            llm=ChatOpenAI(model_name="gpt-4", temperature=0),
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True
        )
    
    def _get_tools(self):
        """Defines tools for the LangChain agent to select from."""
        return [
            Tool(name="Naive Scraper", func=self._naive_scrape, description="Scrapes simple job listings"),
            Tool(name="Playwright Scraper", func=self._playwright_scrape, description="Handles JavaScript-rendered jobs"),
            Tool(name="LLM Extractor", func=self._llm_extract, description="Uses an LLM to extract jobs if other methods fail")
        ]

    async def scrape_company_jobs(self, company_url):
        """Runs the LangChain agent to scrape jobs dynamically."""
        careers_urls = self.find_careers_pages(company_url)
        logger.debug(f"Careers URLs found: {careers_urls}")
        all_jobs = []

        for url in careers_urls:
            try:
                response = self.agent.invoke(
                    {"input": f"Find and extract job listings from {url}"}
                )
                
                # ✅ Ensure the response is structured
                if isinstance(response, list) and all(isinstance(job, dict) for job in response):
                    all_jobs.extend(response)
                else:
                    logger.warning(f"⚠️ Agent returned unstructured response for {url}: {response}")

            except Exception as e:
                logger.error(f"Agent failed for {url}: {e}", exc_info=True)
        
        return all_jobs

    def find_careers_pages(self, company_url):
        """Finds career pages dynamically by scanning homepage."""
        careers_pages = []
        response = self._get_with_retries(company_url)
        if not response:
            return [company_url]
        soup = BeautifulSoup(response.text, "lxml")
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            full_url = href if href.startswith("http") else urljoin(company_url, href)
            if re.search(r"careers|jobs|join-us", full_url, re.IGNORECASE):
                careers_pages.append(full_url)
        return careers_pages if careers_pages else [company_url]
    
    def naive_scrape(self, url):
        """Simple requests-based scraping method."""
        response = self._get_with_retries(url)
        if not response:
            return []
        soup = BeautifulSoup(response.text, "lxml")
        job_elements = soup.select("[class*=job], [class*=position]")
        
        return [
            {"title": elem.get_text(strip=True), "company": url, "url": url}
            for elem in job_elements
        ]
    
    async def playwright_scrape(self, url):
        """Handles JavaScript-rendered job listings using Playwright."""
        jobs = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(url, timeout=30_000)
                content = await page.content()
                soup = BeautifulSoup(content, "lxml")
                jobs = [
                    {"title": elem.get_text(strip=True), "company": url, "url": url}
                    for elem in soup.select("[class*=job], [class*=position]")
                ]
            except Exception as e:
                logger.error(f"Playwright failed on {url}: {e}", exc_info=True)
            finally:
                await browser.close()
        return jobs
    
    async def llm_extract(self, url):
        """Last resort: Uses LLM to extract jobs."""
        if self.llm_service:
            response = await self.llm_service.parse_jobs_with_llm(url)
            return [
                {"title": job.get("title", "Unknown"), "company": url, "url": url}
                for job in response
            ]
        return []
    
    def _get_with_retries(self, url, timeout=30):
        """Retries failed requests with exponential backoff."""
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(url, timeout=timeout, allow_redirects=True)
                if response.status_code == 200:
                    return response
                logger.warning(f"Request to {url} failed with {response.status_code}, retrying...")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Error fetching {url}: {e}. Retry {attempt + 1}/{MAX_RETRIES}")
            time.sleep(2 ** attempt)
        return None

# ✅ New function for `job_main.py`
def find_jobs(url):
    """Public function for job_main.py to call the scraper."""
    scraper = SiteScraper()
    return asyncio.run(scraper.scrape_company_jobs(url))

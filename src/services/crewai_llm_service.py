import json
import asyncio
import re
from pydantic import BaseModel
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from crewai.agent import Agent
from src.logger import setup_logger

logger = setup_logger(__name__)

class JobPosting(BaseModel):
    title: str
    location: str = "Unknown"
    job_type: str = "Unknown"
    experience: str = "Unknown"
    description: str = ""
    url: str = ""

class CrewAILLMService:
    """
    CrewAI-based LLM service to extract job postings from cleaned web text.
    """

    def __init__(self, config):
        self.api_key = config.get("openai_api_key")
        self.model = config.get("model_name", "gpt-4o-mini")
        self.role = config.get("role", "Job Search Assistant")
        self.goal = config.get("goal", "Extract and structure job postings")
        self.backstory = config.get("backstory", "An AI trained to extract job listings from unstructured text.")

        if not self.api_key:
            raise ValueError("OpenAI API key is missing in the config.")

        logger.info(f"Initializing CrewAI Agent for LLM with role={self.role}, model={self.model}")
        self.agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            llm=self.model
        )

    async def fetch_clean_html(self, company_url):
        """
        Uses Playwright to fetch & clean HTML before sending to LLM.
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(company_url, timeout=30 * 1000)
                raw_html = await page.content()
            except Exception as e:
                logger.error(f"Error loading {company_url}: {e}", exc_info=True)
                return ""
            finally:
                await browser.close()

        # Clean HTML using BeautifulSoup
        soup = BeautifulSoup(raw_html, "html.parser")
        for tag in ["script", "style", "footer", "nav", "aside"]:
            for elem in soup.find_all(tag):
                elem.decompose()

        cleaned_text = " ".join([p.get_text() for p in soup.find_all(["h1", "h2", "h3", "p"])])
        return cleaned_text

    def get_job_extraction_prompt(self, html_text):
        """
        Returns a well-structured LLM prompt for extracting job postings.
        """
        return f"""
        You are an AI that extracts structured job postings from raw text. 
        Identify and return job listings as JSON with the following fields:
        
        - **title** (Job title)
        - **location** (City, State, or "Remote")
        - **job_type** (Full-time, Part-time, Contract)
        - **experience** (Years of experience required)
        - **description** (Short summary)
        - **url** (Job-specific URL if found, otherwise company careers page)
        
        If no job postings exist, return an empty JSON list: [].

        🔹 **Example Input**
        ```
        Acme Corp is hiring a Product Manager (Remote). Full-time, requires 5+ years of experience. Apply at acmecorp.com/jobs/123
        ```

        ✅ **Expected JSON Output**
        ```json
        [
            {{
                "title": "Product Manager",
                "location": "Remote",
                "job_type": "Full-time",
                "experience": "5+ years",
                "description": "Full-time, requires 5+ years of experience.",
                "url": "https://acmecorp.com/jobs/123"
            }}
        ]
        ```

        🔹 **Web Content to Parse:**
        {html_text}
        """

    async def parse_jobs_with_llm(self, company_url):
        """
        Extract job postings using the LLM after Playwright cleanup.
        """
        html_text = await self.fetch_clean_html(company_url)
        if not html_text or len(html_text) < 100:
            logger.warning(f"Insufficient content from {company_url}, skipping LLM.")
            return []

        prompt = self.get_job_extraction_prompt(html_text)
        logger.debug(f"Sending LLM prompt for {company_url}...")

        try:
            response = self.agent.chat(prompt)  # CrewAI v2 uses `.chat()`
            text_output = response.content.strip() if hasattr(response, "content") else str(response)
            parsed_data = json.loads(text_output) if text_output.startswith("[") else []
            
            if not isinstance(parsed_data, list):
                logger.warning(f"Unexpected LLM output format: {text_output}")
                return []

            jobs = [JobPosting(**item).dict() for item in parsed_data if isinstance(item, dict)]
            logger.info(f"LLM extracted {len(jobs)} jobs for {company_url}")
            return jobs
        except Exception as e:
            logger.error(f"Error calling LLM: {e}", exc_info=True)
            return []

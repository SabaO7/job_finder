# src/aggregator.py

import sys
import asyncio
from src.logger import setup_logger
from src.scrapers.site_scraper import SiteScraper

logger = setup_logger(__name__)

class Aggregator:
    """Handles scraping jobs from multiple company websites."""

    def __init__(self, config):
        self.config = config
        self.site_scraper = SiteScraper(config=config)

    async def run(self, company_list):
        """
        Runs the scraping process for multiple company websites asynchronously.
        """
        all_jobs = []

        logger.info(f"Aggregator starting. Will scrape {len(company_list)} companies.")

        # 🔹 **Run all tasks concurrently using asyncio.gather()**
        job_results = await asyncio.gather(
            *(self.site_scraper.scrape_company_jobs(company_url) for company_url in company_list)
        )

        for job_posts, company_url in zip(job_results, company_list):
            try:
                if job_posts:
                    logger.info(f"Found {len(job_posts)} jobs from {company_url}")
                    all_jobs.extend(job_posts)
                else:
                    logger.warning(f"No jobs found for {company_url}.")
            except Exception as e:
                logger.error(f"Error processing results for {company_url}: {e}", exc_info=True)

        logger.info(f"Aggregator finished. Total {len(all_jobs)} jobs scraped.")
        return all_jobs

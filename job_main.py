import os
import json
import asyncio
import logging
import csv
import yaml
from langchain_community.chat_models import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain.tools import Tool
from src.scrapers.site_scraper import SiteScraper
from src.logger import setup_logger
from src.filters import filter_jobs



# ✅ Setup logging
logger = setup_logger("JobFinder")

# ✅ File paths
CSV_FILE = "Company_Websites.csv"
CONFIG_FILE = "config.yaml"
OUTPUT_FILE = "jobs_output.json"

# ✅ Load company websites from CSV
def load_company_websites(csv_file):
    if not os.path.exists(csv_file):
        logger.error(f"CSV file '{csv_file}' not found.")
        return {}

    company_websites = {}
    try:
        with open(csv_file, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                company = row.get("Company", "").strip()
                website = row.get("Website", "").strip()
                if company and website:
                    company_websites[company] = website
        logger.info(f"Loaded {len(company_websites)} company websites.")
    except Exception as e:
        logger.error(f"Error loading CSV: {e}")
    return company_websites

# ✅ Load YAML configuration
def load_yaml_config(config_file):
    if not os.path.exists(config_file):
        logger.error(f"Config file '{config_file}' not found.")
        return {}

    try:
        with open(config_file, "r", encoding="utf-8") as file:
            config = yaml.safe_load(file)
        logger.info("Successfully loaded YAML configuration.")
        return config
    except Exception as e:
        logger.error(f"Error loading YAML: {e}")
        return {}

# ✅ Define LangChain Agent
def create_scraper_agent():
    """Initializes the LangChain-powered scraping agent."""
    memory = MemorySaver()
    
    scraper = SiteScraper()  # ✅ Ensure this is an instance
    
    tools = [
        Tool(name="Naive Scraper", func=lambda url: scraper.naive_scrape(url, url), description="Scrapes simple job listings"),
        Tool(name="Playwright Scraper", func=lambda url: asyncio.run(scraper.playwright_scrape(url, url)), description="Handles JavaScript-rendered jobs"),
        Tool(name="LLM Extractor", func=lambda url: asyncio.run(scraper.llm_extract(url, url)), description="Uses an LLM to extract jobs")
    ]
    
    # ✅ Instead of bind_tools(), use functions to specify tools
    model = ChatOpenAI(model_name="gpt-4-turbo", temperature=0, functions=tools)

    agent = create_react_agent(model, tools, checkpointer=memory)
    
    return agent



# ✅ Main job scraper logic
async def main():
    logger.info("Job scraper started.")

    # 🔹 Load company list & config
    company_websites = load_company_websites(CSV_FILE)
    if not company_websites:
        logger.error("No company websites found. Exiting...")
        return

    config = load_yaml_config(CONFIG_FILE) or {}

    # 🔹 Initialize LangChain Agent
    agent = create_scraper_agent()

    scraped_jobs = []
    for company, url in company_websites.items():
        logger.info(f"🔎 Scraping jobs for: {company} ({url})")
        
        try:
            # 🔹 Ask the agent to scrape
            response = agent.invoke(
                {"messages": [HumanMessage(content=f"Scrape jobs from {url}")]},
            )
            jobs = response.get("jobs", [])
            
            if jobs:
                logger.info(f"✅ {len(jobs)} jobs found for {company}")
                scraped_jobs.extend(jobs)
            else:
                logger.warning(f"❌ No jobs found for {company}")

        except Exception as e:
            logger.error(f"⚠️ Error scraping {company}: {e}")

    # 🔹 Apply filters & save results
    job_filters = config.get("job_filters", {})
    filtered_jobs = filter_jobs(scraped_jobs, job_filters)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(filtered_jobs, file, indent=4, ensure_ascii=False)

    logger.info(f"🎯 Successfully saved {len(filtered_jobs)} jobs to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())

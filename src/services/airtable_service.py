import os
import logging
from dotenv import load_dotenv
from pyairtable import Api

logger = logging.getLogger(__name__)

# Ensure environment variables are loaded from .env
load_dotenv()

class AirtableService:
    def __init__(self, config):
        """
        Initializes the Airtable service with API credentials.

        :param config: Dictionary containing:
            - api_key:    Airtable API token (AIRTABLE_API_TOKEN)
            - base_id:    The ID of your Airtable base
            - table_name: The name of the table to interact with
        """
        try:
            self.api_key = config.get("api_key", os.getenv("AIRTABLE_API_TOKEN"))
            self.base_id = config.get("base_id", os.getenv("AIRTABLE_BASE_ID"))
            self.table_name = config.get("table_name", "ScrapedJobs")  # Default table name

            if not self.api_key:
                raise ValueError("Missing Airtable API key. Check .env or config.yaml.")
            if not self.base_id:
                raise ValueError("Missing Airtable Base ID. Check .env or config.yaml.")

        except KeyError as e:
            raise ValueError(f"Missing Airtable config key: {e}")

        # Initialize Airtable API connection
        self.api = Api(self.api_key)
        self.table = self.api.table(self.base_id, self.table_name)

        logger.info(f"Setting up Airtable table: base_id={self.base_id}, table_name={self.table_name}")

    def get_existing_fields(self):
        """
        Retrieves existing field names by scanning some records.
        """
        try:
            records = self.table.all(page_size=5)
            if not records:
                logger.warning("No records found in Airtable; cannot infer fields.")
                return set()

            field_names = set()
            for record in records:
                fields_dict = record.get("fields", {})
                for f_name in fields_dict.keys():
                    field_names.add(f_name)

            logger.debug(f"Inferred fields: {field_names}")
            return field_names
        except Exception as e:
            logger.error(f"Error retrieving Airtable fields: {e}", exc_info=True)
            return set()

    def ensure_fields_exist(self, required_fields):
        """
        Checks if required fields exist.
        """
        existing_fields = self.get_existing_fields()
        missing_fields = [field for field in required_fields if field not in existing_fields]

        if missing_fields:
            logger.warning(f"Missing Airtable fields: {missing_fields}")
        else:
            logger.info("All required fields exist.")

    def create_record(self, record):
        """
        Creates a single record in Airtable.
        """
        try:
            created_record = self.table.create(record)
            logger.debug(f"Created record: {created_record}")
            return created_record
        except Exception as e:
            logger.error(f"Error creating record in Airtable: {e}", exc_info=True)
            raise

    def append_jobs(self, jobs):
        """
        Appends job postings to Airtable.
        """
        if not jobs:
            logger.info("No jobs to append to Airtable.")
            return

        required_fields = ["Company", "Title", "Location", "job_type", "experience", "url", "description"]
        self.ensure_fields_exist(required_fields)

        try:
            for job in jobs:
                record = {
                    "Company": job.get("Company", ""),
                    "Title": job.get("Title", ""),
                    "Location": job.get("Location", ""),
                    "job_type": job.get("job_type", ""),
                    "experience": job.get("experience", ""),
                    "url": job.get("url", ""),
                    "description": job.get("description", "")
                }
                logger.debug(f"Creating Airtable record: {record}")
                self.table.create(record)
        except Exception as e:
            logger.error(f"Error appending records to Airtable: {e}", exc_info=True)

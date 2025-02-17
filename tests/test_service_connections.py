import os
import unittest
import logging
from dotenv import load_dotenv

from src.services.google_sheets_service import GoogleSheetsService
from src.services.airtable_service import AirtableService

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables (for Airtable credentials)
load_dotenv()

class TestGoogleSheetsConnection(unittest.TestCase):
    """
    Tests GoogleSheetsService connection:
      1) Can open/connect to the sheet.
    """

    @classmethod
    def setUpClass(cls):
        """
        Load a small test config for GoogleSheetsService.
        """
        cls.gs_config = {
            "credentials_file": "credentials.json",
            "spreadsheet_name": "job_search_feb_2025",  
            "worksheet_name": "Scraped Jobs" 
        }
        
        try:
            cls.gs_service = GoogleSheetsService(cls.gs_config)
            logger.info("✅ GoogleSheetsService initialized successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize GoogleSheetsService: {e}")
            raise

    def test_google_sheets_connection(self):
        """
        Test whether the Google Sheets service can connect.
        """
        try:
            existing_values = self.gs_service.sheet.get_all_values()
            logger.info(f"✅ Google Sheets Connection Test Passed. Found {len(existing_values)} existing rows.")
            self.assertIsNotNone(existing_values, "❌ Google Sheets returned None - unexpected.")
        except Exception as e:
            logger.error(f"❌ Error fetching rows from Google Sheets: {e}")
            self.fail("❌ Google Sheets connection test failed.")


class TestAirtableConnection(unittest.TestCase):
    """
    Tests AirtableService connection:
      1) Can open/connect to the Airtable table.
    """

    @classmethod
    def setUpClass(cls):
        """
        Load a small test config for Airtable.
        """
        cls.at_config = {
            "api_key": os.getenv("AIRTABLE_API_TOKEN", "MISSING_KEY"),  # Changed from AIRTABLE_API_KEY
            "base_id": os.getenv("AIRTABLE_BASE_ID", "MISSING_BASE_ID"),
            "table_name": "ScrapedJobs"
        }

        if "MISSING_KEY" in cls.at_config["api_key"] or "MISSING_BASE_ID" in cls.at_config["base_id"]:
            raise ValueError("❌ Airtable API key or Base ID missing. Check .env file.")

        try:
            cls.at_service = AirtableService(cls.at_config)
            logger.info("✅ AirtableService initialized successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize AirtableService: {e}")
            raise

    def test_airtable_connection(self):
        """
        Test whether the Airtable service can connect.
        """
        try:
            records = self.at_service.table.all(page_size=5)
            logger.info(f"✅ Airtable Connection Test Passed. Fetched {len(records)} records.")
            self.assertIsNotNone(records, "❌ Airtable returned None - unexpected.")
        except Exception as e:
            logger.error(f"❌ Error fetching records from Airtable: {e}")
            self.fail("❌ Airtable connection test failed.")


if __name__ == "__main__":
    unittest.main()

# file: tests/test_service_integrity.py

import os
import unittest
import logging
from dotenv import load_dotenv

# Adjust these imports to point to your actual paths
from src.services.google_sheets_service import GoogleSheetsService
from src.services.airtable_service import AirtableService

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class TestGoogleSheetsIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """
        Setup the GoogleSheetsService with test config.
        Change 'spreadsheet_name' or 'worksheet_name' to a separate test sheet if needed.
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

    def test_ensure_columns_exist(self):
        """
        Example test to ensure certain columns exist in the first row.
        Your GoogleSheetsService must have some method to check columns if you want.
        Or you can do a manual approach by reading the first row.
        """
        required_columns = ["Company", "Title", "Location", "job_type", "experience", "url", "description"]
        try:
            # We assume the first row is the header
            existing_values = self.gs_service.sheet.get_all_values()
            if existing_values:
                existing_columns = existing_values[0]
                logger.debug(f"Found columns in first row: {existing_columns}")
                for col in required_columns:
                    self.assertIn(col, existing_columns, f"❌ Missing column: {col}")
                logger.info("✅ Google Sheets column validation test passed.")
            else:
                logger.warning("❌ The sheet is empty, no header row found!")
                self.fail("❌ No rows found in Google Sheets to validate columns.")
        except Exception as e:
            logger.error(f"❌ Error checking columns in Google Sheets: {e}")
            self.fail("❌ Google Sheets column integrity test failed.")

    def test_append_small_row(self):
        """
        Try appending a small row to confirm writes are working.
        """
        test_row = ["TestIntegration", "Test Title", "Remote", "Full-Time", "0-1", "https://test.com", "Test description"]
        try:
            logger.info(f"Appending row: {test_row}")
            self.gs_service.sheet.append_row(test_row)
            logger.info("✅ Append successful.")
        except Exception as e:
            logger.error(f"❌ Error appending row in Google Sheets: {e}")
            self.fail("❌ Google Sheets row append test failed.")


class TestAirtableIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """
        Setup AirtableService with test config from environment or fallback.
        'table_name' can also be a test table if you want to avoid production data.
        """
        cls.at_config = {
            "api_key": os.getenv("AIRTABLE_API_TOKEN", "MISSING_KEY"),
            "base_id": os.getenv("AIRTABLE_BASE_ID", "MISSING_BASE_ID"),
            "table_name": "ScrapedJobs"
        }

        if "MISSING_KEY" in cls.at_config["api_key"] or "MISSING_BASE_ID" in cls.at_config["base_id"]:
            raise ValueError("❌ Airtable API key or Base ID missing. Check .env file or environment variables.")

        try:
            cls.at_service = AirtableService(cls.at_config)
            logger.info("✅ AirtableService initialized successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize AirtableService: {e}")
            raise

    def test_ensure_fields_exist(self):
        """
        Check that each required field is present in at least one record.
        If the table is brand-new or fields are never used, they won't appear. 
        This test may fail if the fields haven't been used yet.
        """
        required_fields = ["Company", "Title", "Location", "job_type", "experience", "url", "description"]
        try:
            # Will log a warning if missing
            self.at_service.ensure_fields_exist(required_fields)
            existing_fields = self.at_service.get_existing_fields()
            logger.debug(f"Existing fields: {existing_fields}")
            for field in required_fields:
                self.assertIn(field, existing_fields, f"❌ Missing field: {field}")
            logger.info("✅ Airtable field validation test passed.")
        except Exception as e:
            logger.error(f"❌ Error ensuring fields exist in Airtable: {e}")
            self.fail("❌ Airtable field integrity test failed.")

    def test_create_small_record(self):
        """
        Create a small record to confirm we can write to the table.
        """
        test_record = {
            "Company": "TestCompany",
            "Title": "IntegrationTest",
            "Location": "Remote",
            "job_type": "Full-Time",
            "experience": "0-1",
            "url": "https://testcompany.com/job",
            "description": "Test integration job posting."
        }
        try:
            created = self.at_service.create_record(test_record)
            logger.debug(f"Created record: {created}")
            self.assertIn("id", created, "❌ Created record did not return an ID - suspicious.")
            logger.info(f"✅ Created record ID: {created.get('id')}")
        except Exception as e:
            logger.error(f"❌ Error creating record in Airtable: {e}")
            self.fail("❌ Airtable record append test failed.")


if __name__ == "__main__":
    unittest.main()

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from src.logger import setup_logger

logger = setup_logger(__name__)

class GoogleSheetsService:
    def __init__(self, config):
        """
        Initializes the Google Sheets service with API credentials.

        :param config: Dictionary containing Google Sheets configuration.
        """
        self.credentials_file = config["credentials_file"]
        self.spreadsheet_name = config["spreadsheet_name"]
        self.worksheet_name = config.get("worksheet_name", "Sheet1")

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive"
        ]

        logger.info("Setting up Google Sheets service with credentials=%s", self.credentials_file)

        creds = ServiceAccountCredentials.from_json_keyfile_name(self.credentials_file, scope)
        self.client = gspread.authorize(creds)

        try:
            self.sheet = self.client.open(self.spreadsheet_name).worksheet(self.worksheet_name)
        except gspread.WorksheetNotFound:
            logger.warning(f"Worksheet '{self.worksheet_name}' not found. Creating a new one.")
            workbook = self.client.open(self.spreadsheet_name)
            self.sheet = workbook.add_worksheet(title=self.worksheet_name, rows="100", cols="20")

    def ensure_columns_exist(self, required_columns):
        """
        Ensures that all required columns exist in the Google Sheet.
        Adds missing columns if necessary.

        :param required_columns: List of column names that should exist.
        """
        try:
            existing_values = self.sheet.get_all_values()

            if not existing_values:  # If sheet is empty, add header row
                self.sheet.append_row(required_columns)
                logger.info(f"Header row added: {required_columns}")
                return

            existing_columns = existing_values[0]  # First row as header
            missing_columns = [col for col in required_columns if col not in existing_columns]

            if missing_columns:
                logger.warning(f"Missing columns in Google Sheets: {missing_columns}")
                updated_header = existing_columns + missing_columns
                self.sheet.insert_row(updated_header, index=1)  # Update header row
        except Exception as e:
            logger.error(f"Error ensuring columns exist in Google Sheets: {e}", exc_info=True)

    def append_jobs(self, jobs):
        """
        Appends job data to the Google Sheet, ensuring required columns exist.

        :param jobs: List of job dictionaries.
        """
        if not jobs:
            logger.info("No jobs to append to Google Sheets.")
            return

        required_columns = ["Company", "Title", "Location", "Job Type", "Experience", "URL", "Description"]
        self.ensure_columns_exist(required_columns)

        try:
            for job in jobs:
                row = [job.get(col, "") for col in required_columns]
                logger.debug(f"Appending row: {row}")
                self.sheet.append_row(row)
        except Exception as e:
            logger.error(f"Error appending jobs to Google Sheets: {e}", exc_info=True)

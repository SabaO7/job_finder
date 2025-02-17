# src/history_service.py

from src.logger import setup_logger

logger = setup_logger(__name__)

class HistoryService:
    """
    Stores and retrieves historical data about job scraping performance.
    This is essential for a feedback loop: we track which sources or
    keywords yielded good results, and which did not.
    """

    def __init__(self, config):
        """
        :param config: Could include references to Google Sheets, Airtable,
                       or a local database. For example:
                       {
                           "use_google_sheets": True,
                           "use_airtable": True,
                           "google_sheets": {...},
                           "airtable": {...}
                       }
        """
        self.config = config
        # If you want to store feedback in a separate sheet/table, set that up here.
        self.google_sheets_service = None
        self.airtable_service = None

        # Initialize whichever services you want to use for storing feedback
        self._init_services()

    def _init_services(self):
        """Initialize Google Sheets or Airtable as needed."""
        if self.config.get("use_google_sheets"):
            try:
                from src.services.google_sheets_service import GoogleSheetsService
                gs_config = self.config.get("google_sheets", {})
                self.google_sheets_service = GoogleSheetsService(gs_config)
            except Exception as e:
                logger.error(f"Error initializing Google Sheets service: {e}")

        if self.config.get("use_airtable"):
            try:
                from src.services.airtable_service import AirtableService
                at_config = self.config.get("airtable", {})
                self.airtable_service = AirtableService(at_config)
            except Exception as e:
                logger.error(f"Error initializing Airtable service: {e}")

    def record_feedback(self, source, feedback):
        """
        Stores feedback about a particular source (company or aggregator).
        :param source: string identifier for the source
        :param feedback: dict with data like:
            {
                "relevant_jobs_found": 5,
                "irrelevant_jobs_found": 2,
                "notes": "Some additional info"
            }
        """
        # This is where you’d push data to your chosen store (Sheets/Airtable).
        # For example, to Google Sheets you might want a special "Feedback" tab:
        logger.info(f"Recording feedback for source={source}: {feedback}")

        # Example code if you had a special "Feedback" sheet:
        if self.google_sheets_service:
            row = [source, feedback.get("relevant_jobs_found", 0),
                   feedback.get("irrelevant_jobs_found", 0),
                   feedback.get("notes", "")]
            # (In your google_sheets_service, you might create a method like
            #  self.sheet_for_feedback.append_row(row).)
            # For now, we just log it:
            logger.debug(f"Would append row to 'Feedback' sheet: {row}")

        # Similarly for Airtable:
        if self.airtable_service:
            record = {
                "Source": source,
                "RelevantJobs": feedback.get("relevant_jobs_found", 0),
                "IrrelevantJobs": feedback.get("irrelevant_jobs_found", 0),
                "Notes": feedback.get("notes", "")
            }
            logger.debug(f"Would create a record in Airtable 'Feedback' table: {record}")

    def retrieve_history(self):
        """
        Pulls historical feedback from your chosen data store.
        Return a dict, e.g. {source: {"relevant": X, "irrelevant": Y, ...}, ...}
        For demonstration, returns a stub.
        """
        logger.debug("Retrieving historical feedback (stub).")
        # In a real scenario, you’d read from Google Sheets or Airtable
        return {
            "https://somecompany.com": {"relevant": 10, "irrelevant": 3},
            "https://anotherco.com": {"relevant": 2, "irrelevant": 5},
        }

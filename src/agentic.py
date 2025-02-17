# src/agentic.py

import math
from src.logger import setup_logger

logger = setup_logger(__name__)

class AutonomousAgent:
    """
    Orchestrates a feedback loop that:
      1. Reads historical feedback (which sources are best).
      2. Adjusts search keywords or source order based on performance.
      3. Provides updated configuration to your main scripts.
    """

    def __init__(self, config, history_service):
        """
        :param config: The main config dict from config.yaml
        :param history_service: An instance of HistoryService
        """
        self.config = config
        self.history_service = history_service

        # Keep a local copy of historical data
        self.history = self.history_service.retrieve_history()
        logger.info("AutonomousAgent initialized with historical data.")

    def update_config(self):
        """
        Main entry point: update the config with new keywords, reorder sources, etc.
        """
        self._adjust_keywords()
        self._prioritize_sources()
        logger.info("Configuration updated based on feedback.")
        return self.config

    def _adjust_keywords(self):
        """
        Dynamically add/remove job title keywords based on historical data.
        Example: If we notice that "Project Manager" is showing up often in relevant results
        but not in the config, add it.
        """
        logger.info("Analyzing history to adjust keywords...")

        # Stub logic: Suppose we see "Project Manager" is relevant in a large fraction of postings
        # but it's missing from config["filters"]["job_titles"].
        job_titles = set(self.config.get("filters", {}).get("job_titles", []))
        if "Project Manager" not in job_titles:
            # Fake condition: if "somecompany.com" had more than 5 relevant hits
            # we might decide to add "Project Manager" to the keywords
            if self.history.get("https://somecompany.com", {}).get("relevant", 0) > 5:
                job_titles.add("Project Manager")
                logger.debug("Added 'Project Manager' to job_titles based on history.")

        self.config["filters"]["job_titles"] = list(job_titles)

    def _prioritize_sources(self):
        """
        Sort the list of company URLs or aggregator URLs based on historical performance.
        For instance, if aggregator X had a higher ratio of relevant to irrelevant jobs,
        push it to the front of the queue.
        """
        logger.info("Reordering sources based on historical success ratio.")

        # Suppose you have a dictionary of {company_url: {relevant: X, irrelevant: Y}}
        # We can compute a success ratio = relevant / (relevant + irrelevant + 1).
        # Then reorder the company URLs in descending order of success ratio.
        company_list_file = "Company_Websites.csv"  # or aggregator_companies.csv
        # In practice, you might store your company list in config or a DB, not just CSV.

        # This is just example logic. Real logic would parse your CSV,
        # compute a ratio, and then rewrite the CSV in a new order.
        # For now, let's do a stub:
        for source, metrics in self.history.items():
            rel = metrics.get("relevant", 0)
            irr = metrics.get("irrelevant", 0)
            ratio = rel / (rel + irr + 1)
            logger.debug(f"Source {source} ratio={ratio:.2f}")

        logger.debug("Stub: Did not actually reorder CSV. Implement if needed.")

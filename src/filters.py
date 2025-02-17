# src/filters.py

import re
from src.logger import setup_logger

logger = setup_logger(__name__)

def filter_jobs(jobs, filter_config):
    """
    :param jobs: List of job dicts.
    :param filter_config: A dict matching the "filters" part of config.yaml
    :return: Filtered list of jobs
    """
    if not filter_config:
        logger.debug("No filter config provided; returning all jobs.")
        return jobs

    job_titles = filter_config.get("job_titles", [])
    min_experience = filter_config.get("min_experience_years", 0)
    max_experience = filter_config.get("max_experience_years", 100)
    locations = filter_config.get("locations", [])
    job_type_filters = filter_config.get("job_type", [])

    filtered = []
    for job in jobs:
        title_ok = any(t.lower() in job["title"].lower() for t in job_titles)

        experience_ok = True
        if "experience" in job and job["experience"] is not None:
            if not (min_experience <= job["experience"] <= max_experience):
                experience_ok = False

        location_ok = True
        if locations:
            location_ok = any(loc.lower() in job["location"].lower() for loc in locations)

        job_type_ok = True
        if job_type_filters:
            job_type_ok = any(jt.lower() in job["job_type"].lower() for jt in job_type_filters)

        if title_ok and experience_ok and location_ok and job_type_ok:
            filtered.append(job)

    logger.info(f"Filtering complete. {len(jobs)} jobs in, {len(filtered)} jobs out.")
    return filtered

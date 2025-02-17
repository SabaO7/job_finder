# Job Finder Agent

## Overview
This repository helps you automatically scrape job postings for roles (e.g., “Product Manager”) from a list of companies or from Forbes’ “Canada’s Best Employers” list. It then filters those postings (by experience, location, etc.) and uploads them to either Google Sheets or Airtable.

## Features
- Scrape company websites to find careers/jobs pages.
- Parse job postings (title, location, description, etc.).
- Filter by job title, experience, location, job type, etc.
- Store results in Google Sheets or Airtable.

## Requirements
- Python 3.7+
- (Optional) A Google Cloud service account JSON file if using Google Sheets
- (Optional) An Airtable account & API key if using Airtable

## LLM (CrewAI) Integration

This project can optionally use [CrewAI](https://crewai.io/) (powered by OpenAI) to parse websites that have unusual or dynamic structures. When `use_llm` is set to `true` in `config.yaml`, the scraper will:
1. Attempt a **naive** parse of the careers/jobs pages.
2. If it **fails** to find any jobs, it will **fall back** to an LLM-based approach, which reads the entire HTML and attempts to extract job postings.

### Prerequisites

- An **OpenAI API key** with billing enabled (unless you have free credits).
- Installed the `crewai` library (and possibly `openai`), which is added in `requirements.txt`.

### Configuration

In `config.yaml`, set:

```yaml
use_llm: true
llm:
  openai_api_key: "YOUR_OPENAI_API_KEY"
  model_name: "gpt-3.5-turbo"

## Setup Instructions

### 1. Clone the Repo
```bash
git clone https://github.com/your-username/job-finder-agent.git
cd job-finder-agent
```

### 2. Create a Virtual Environment (Recommended)
```bash
python -m venv venv
source venv/bin/activate  # On Mac/Linux
# or: venv\Scripts\activate on Windows
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```
> **Note:** If you see an error related to `oauth2client`, try installing it explicitly:
```bash
pip install oauth2client
```
If you still get the import error from your editor (e.g., VS Code with Pylance), ensure your interpreter is set to the virtual environment where `oauth2client` is installed.

---

## 4. Obtain & Configure Google Sheets API Credentials _(Skip if not using Google Sheets)_
1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (or select an existing one).
3. Click **APIs & Services → Credentials**.
4. Click **Create Credentials → Service account** and follow the prompts.
5. Once created, go to **Keys → Add Key → Create new key → JSON**.
6. Save the JSON file in your repo (e.g., `job-finder-agent/credentials.json`).
7. Update `config.yaml`:
```yaml
google_sheets:
  spreadsheet_name: "Job Finder Results"
  worksheet_name: "Scraped Jobs"
  credentials_file: "credentials.json"
```
8. Share your Google Sheet with the service account email (found in the JSON file).

---

## 5. Obtain & Configure Airtable API Credentials _(Skip if not using Airtable)_
1. Sign up or log in to [Airtable](https://airtable.com).
2. Create a base (e.g., **Job Finder Results**).
3. Find your **Base ID** in Airtable’s API documentation.
4. Generate an **API Key** in your Airtable account settings.
5. Update `config.yaml`:
```yaml
airtable:
  base_id: "appXXXXXXXXXXXXXX"
  table_name: "ScrapedJobs"
  api_key: "YOUR_AIRTABLE_API_KEY"
```

---

## 6. Configure `config.yaml`
Edit the `config.yaml` file based on your needs:
```yaml
filters:
  job_titles:
    - "Product Manager"
    - "Associate Product Manager"
  min_experience_years: 0
  max_experience_years: 4
  locations:
    - "Kitchener"
    - "Remote"
  job_type:
    - "Full-Time"

output:
  use_google_sheets: true
  use_airtable: false
```

---

## 7. Run the Scraper
```bash
python main.py
```
The script will scrape company career pages, filter postings, and upload the results based on your configuration.

---

## 8. Scheduling the Script

### **8.1 Local Cron Job (Mac/Linux)**
To run daily at 9 AM:
```bash
crontab -e
```
Add:
```bash
0 9 * * * /path/to/venv/bin/python /path/to/job-finder-agent/main.py
```

### **8.2 GitHub Actions**
Create `.github/workflows/scrape.yml`:
```yaml
name: Daily Scrape

on:
  schedule:
    - cron: '0 9 * * *'  # Runs every day at 9 AM UTC
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -r requirements.txt
      - name: Run scraper
        run: |
          python main.py
```

> **Note:** Store credentials securely using GitHub Secrets.


---

# 9. Final Notes

1. **Edge Cases**:  
   - Websites with **SPA** frameworks (React, Angular) may need **Playwright** or **Selenium** to fully load. The LLM approach can still be used, but you must first capture the **rendered** HTML.  
   - The LLM approach tries to parse text from the site. If the site is heavily obfuscated or structured in ways the LLM can’t interpret, you might still get zero results.  
   - We only attempt LLM parsing after the naive approach yields no results. You could also **always** use LLM to refine the naive approach’s results, but that increases token usage (cost).

2. **API Keys & Security**:  
   - Because you’re storing your OpenAI key in `config.yaml`, consider ignoring that file in `.gitignore` or using environment variables.  
   - For GitHub Actions, use **GitHub Secrets** to store your `OPENAI_API_KEY`, then inject it into the `config.yaml` at runtime or parse it in code.

3. **Filtering**:  
   - The LLM approach returns job data in a standard dict. We still run everything through `filter_jobs()` so the user’s preferences (e.g., job titles, min/max years of experience) apply uniformly.

This completes the **fully updated** codebase that includes an **LLM “Agent”** approach via CrewAI for advanced scraping. You can now handle more complex or unusual sites, beyond what the naive HTML parsing can do.


---

## Troubleshooting

### Authentication Errors for Google Sheets:
- Ensure your service account email has **Editor** access to the Google Sheet.
- Verify the path to `credentials.json` in `config.yaml`.

### Permission Denied in Airtable:
- Check that your **API Key** and **Base ID** are correct.
- Ensure your Airtable account has the correct permissions.

### No Jobs Found:
- Some websites use dynamic content that basic scraping won’t catch.
- Consider using **headless browsers** like Selenium or Playwright.

### Captchas / Bot Blocks:
- Respect `robots.txt`.
- Use official APIs when available.

---

## Contributing
Feel free to:
- Open **issues** or **pull requests** for bug fixes or improvements.
- Fork and adapt the code for other job roles, locations, or additional integrations.

---

## License
This project is open-source under the **MIT License**.

---

## That’s it! 🚀
- **Scrape job listings from company websites or Forbes.**
- **Filter by role, experience, and location.**
- **Store results in Google Sheets or Airtable.**

**Happy job hunting!** 🎯


import os
import time
import requests
from bs4 import BeautifulSoup

from playwright.sync_api import sync_playwright
# Typically "stealth_sync" is the function to call, not "stealth(page)"
# If your library provides a different function name, adjust here.
from playwright_stealth import stealth_sync

from src.logger import setup_logger

logger = setup_logger(__name__)

# Optional: import your LLM fallback
try:
    from src.services.crewai_llm_service import CrewAILLMService
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    logger.warning("CrewAI LLM not installed. Final fallback won't work.")

class CompanyListsScraper:
    """
    Scrapes aggregator sites for (company_name, company_url) pairs via:
      1) Naive requests
      2) Playwright with stealth
      3) LLM fallback (CrewAI)

    The aggregator_main.py collects toggles & calls `scrape_all_sites(...)`.
    """

    def __init__(self, proxy_url=None):
        """
        :param proxy_url:  e.g. "http://user:pass@proxyserver:port"
                           If provided, we route naive requests & Playwright traffic
                           through this proxy. Might help circumvent IP-based blocks.
        """
        self.proxy_url = proxy_url

        self.sites = {
            "latka": {
                "url": "https://getlatka.com/companies/countries/canada/cities/waterloo",
                "selector": "div.company-row div.company-name a",
                "url_selector": "div.company-row div.company-name a",
                "wait_selector": "div.company-row",
                "popup_selectors": ["div.popup-close", "button[aria-label='Close']", "button.close"],
                "use_custom_ua": True
            },
            "apmlist": {
                "url": "https://apmlist.com/",
                "selector": "table tbody tr td:nth-child(1) a",
                "url_selector": "table tbody tr td:nth-child(1) a",
                "wait_selector": "table tbody tr",
                "popup_selectors": [],
                "use_custom_ua": False
            },
            "growthlist": {
                "url": "https://growthlist.co/canada-startups/",
                "selector": "table.wp-block-table tbody tr td:first-child a",
                "url_selector": "table.wp-block-table tbody tr td:first-child a",
                "wait_selector": "table.wp-block-table tbody tr",
                "popup_selectors": ["div.popup-close", "button.close"],
                "use_custom_ua": False
            }
        }

        # LLM fallback
        self.llm_service = None
        if LLM_AVAILABLE:
            openai_key = os.getenv("OPENAI_API_KEY", "")
            try:
                self.llm_service = CrewAILLMService({
                    "openai_api_key": openai_key,
                    "model_name": "gpt-3.5-turbo",
                    "role": "Aggregator LLM Agent",
                    "goal": "Extract company names from aggregator HTML",
                    "backstory": "You are an AI that identifies companies from aggregator pages."
                })
                logger.info("LLM fallback is available for aggregator scraping if all else fails.")
            except Exception as e:
                logger.warning(f"Failed to init LLM: {e}")

    def scrape_all_sites(self, latka=True, apmlist=True, growthlist=True):
        """
        Returns a list of (aggregator_key, company_name, company_url).
        The aggregator_main will pass toggles for each aggregator site.
        """
        final_list = []
        toggles = [
            ("latka", latka),
            ("apmlist", apmlist),
            ("growthlist", growthlist),
        ]
        for key, do_scrape in toggles:
            if do_scrape and key in self.sites:
                logger.info(f"Starting scraping for {key}")
                data = self._scrape_one_site(key)  # => list of (company_name, company_url)
                for (c_name, c_url) in data:
                    final_list.append((key, c_name, c_url))
        return final_list

    def _scrape_one_site(self, key):
        """
        Fallback chain for a single aggregator site:
          1) naive
          2) playwright stealth
          3) LLM fallback
        Returns list of (company_name, company_url).
        """
        info = self.sites[key]
        url            = info["url"]
        selector_name  = info["selector"]
        selector_url   = info["url_selector"]
        wait_selector  = info["wait_selector"]
        popup_selectors= info["popup_selectors"]
        use_custom_ua  = info["use_custom_ua"]

        # 1) naive
        naive_data = self._naive_scrape(url, selector_name, selector_url, use_custom_ua)
        if naive_data:
            logger.info(f"[Naive][{key}] Found {len(naive_data)} items.")
            return naive_data

        # 2) playwright stealth
        pw_data = self._playwright_scrape(
            url=url,
            selector_name=selector_name,
            selector_url=selector_url,
            wait_selector=wait_selector,
            popup_selectors=popup_selectors,
            use_custom_ua=use_custom_ua
        )
        if pw_data:
            logger.info(f"[Playwright][{key}] Found {len(pw_data)} items.")
            return pw_data

        # 3) LLM fallback
        if self.llm_service:
            logger.info(f"[LLM Fallback][{key}] Trying LLM parse.")
            llm_data = self._llm_fallback(url)
            if llm_data:
                logger.info(f"[LLM][{key}] Found {len(llm_data)} items.")
                return llm_data

        logger.warning(f"[All Methods Failed][{key}] No data extracted.")
        return []

    ###############################
    # 1) NAIVE SCRAPER
    ###############################
    def _naive_scrape(self, url, selector_name, selector_url, use_custom_ua):
        items = []

        # custom UA if needed
        headers = {}
        if use_custom_ua:
            headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/109.0.0.0 Safari/537.36"
            )

        # if you have a proxy
        proxies = {}
        if self.proxy_url:
            proxies = {"http": self.proxy_url, "https": self.proxy_url}

        try:
            resp = requests.get(url, headers=headers, proxies=proxies, timeout=20)
            if resp.status_code != 200:
                logger.warning(f"[Naive] {url} => status {resp.status_code}")
                return items

            soup = BeautifulSoup(resp.text, "lxml")
            name_elems = soup.select(selector_name)
            url_elems  = soup.select(selector_url) if selector_url else []

            max_len = max(len(name_elems), len(url_elems))
            for i in range(max_len):
                c_name = name_elems[i].get_text(strip=True) if i < len(name_elems) else ""
                c_url  = "N/A"
                if i < len(url_elems) and url_elems[i].has_attr("href"):
                    c_url = url_elems[i]["href"]

                if c_name:
                    items.append((c_name, c_url))

        except Exception as e:
            logger.error(f"[Naive] Error scraping {url}: {e}", exc_info=True)

        return items

    ###############################
    # 2) PLAYWRIGHT STEALTH
    ###############################
    def _playwright_scrape(self, url, selector_name, selector_url,
                           wait_selector, popup_selectors, use_custom_ua):
        items = []
        try:
            with sync_playwright() as p:
                launch_args = {"headless": True}
                if self.proxy_url:
                    # e.g. "http://user:pass@someproxy:port"
                    launch_args["proxy"] = {"server": self.proxy_url}

                browser = p.chromium.launch(**launch_args)
                context = browser.new_context()
                page = context.new_page()

                # stealth (with stealth_sync)
                stealth_sync(page)

                if use_custom_ua:
                    page.set_extra_http_headers({
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/109.0.0.0 Safari/537.36"
                        )
                    })

                logger.info(f"[Playwright] Navigating to {url} with stealth/proxy...")
                page.goto(url, timeout=90000, wait_until="domcontentloaded")

                # Close potential popups
                for sel in popup_selectors:
                    try:
                        popup = page.wait_for_selector(sel, timeout=5000)
                        if popup and popup.is_visible():
                            logger.info(f"[Playwright] Closing popup: {sel}")
                            popup.click()
                            page.wait_for_timeout(1000)
                    except:
                        pass

                # Check for cloudflare
                if "cloudflare" in page.content().lower():
                    logger.warning("[Playwright] Cloudflare detected, waiting 10s.")
                    page.wait_for_timeout(10000)
                    page.reload(wait_until="domcontentloaded")

                # Scroll multiple times
                for _ in range(5):
                    page.mouse.wheel(0, 3000)
                    page.wait_for_timeout(2000)

                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=30000)
                        logger.info(f"[Playwright] Found {wait_selector}")
                    except:
                        logger.warning(f"[Playwright] {wait_selector} not found, continuing...")

                content = page.content()
                browser.close()

            # parse
            soup = BeautifulSoup(content, "lxml")
            names = soup.select(selector_name)
            urls  = soup.select(selector_url) if selector_url else []

            max_len = max(len(names), len(urls))
            for i in range(max_len):
                c_name = names[i].get_text(strip=True) if i < len(names) else ""
                c_url  = "N/A"
                if i < len(urls) and urls[i].has_attr("href"):
                    c_url = urls[i]["href"]
                if c_name:
                    items.append((c_name, c_url))

        except Exception as e:
            logger.error(f"[Playwright] Error scraping {url}: {e}", exc_info=True)

        return items

    ###############################
    # 3) LLM FALLBACK
    ###############################
    def _llm_fallback(self, url):
        """
        If naive & Playwright fail, parse raw HTML with LLM to find 'company' lines.
        Returns list of (company_name, company_url).
        """
        results = []
        if not self.llm_service:
            return results

        try:
            proxies = {}
            if self.proxy_url:
                proxies = {"http": self.proxy_url, "https": self.proxy_url}

            resp = requests.get(url, proxies=proxies, timeout=20)
            if resp.status_code == 200:
                # pass only 1 argument to parse_jobs_with_llm => (resp.text)
                parse_data = self.llm_service.parse_jobs_with_llm(resp.text)
                for d in parse_data:
                    c_name = d.get("title", "")
                    c_url  = d.get("url", url)
                    if c_name:
                        results.append((c_name, c_url))
        except Exception as e:
            logger.error(f"[LLM fallback] Error scraping {url}: {e}", exc_info=True)

        return results

import logging
import os
import re
import time
from typing import Optional

from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchWindowException
from selenium.webdriver import ActionChains, Keys
from selenium.webdriver.chrome.options import Options

class TradingViewScraperError(Exception):
    """Custom exception for TradingView scraper errors."""
    pass


class TradingViewScraper:
    """
    A scraper for capturing TradingView chart screenshot links using Selenium.
    Manages WebDriver setup, authentication, and screenshot capture.
    """
    # --- Constants ---
    TRADINGVIEW_BASE_URL = "https://www.tradingview.com"
    TRADINGVIEW_CHART_BASE_URL = "https://in.tradingview.com/chart/"
    DEFAULT_CHART_PAGE_ID = "SAaseURe"
    SESSION_ID_COOKIE = "sessionid"
    SESSION_ID_SIGN_COOKIE = "sessionid_sign"
    SESSION_ID_ENV_VAR = "TRADINGVIEW_SESSION_ID"
    SESSION_ID_SIGN_ENV_VAR = "TRADINGVIEW_SESSION_ID_SIGN"
    CLIPBOARD_READ_SCRIPT = "return navigator.clipboard.readText();"
    DEFAULT_WINDOW_SIZE = "1920,1080"
    MAX_RETRY_ATTEMPTS = 5 # Number of retries for clipboard read
    NAV_WAIT_TIME = 10 # Time to wait after navigation (consider explicit waits)
    COOKIE_WAIT_TIME = 2 # Time to wait after navigating for cookies
    CLIPBOARD_WAIT_TIME = 3 # Time to wait after Alt+S for clipboard

    def __init__(self, default_ticker: str = "BYBIT:BTCUSDT.P", default_interval: str = '15', headless: bool = True, window_size: str = DEFAULT_WINDOW_SIZE, chart_page_id: str = DEFAULT_CHART_PAGE_ID):
        """Initializes the scraper configuration."""
        self.headless = headless
        self.window_size = window_size
        self.chart_page_id = chart_page_id
        self.default_ticker = default_ticker
        self.default_interval = default_interval
        self.driver = None
        # self.wait = None

        self.logger = logging.getLogger(__name__)
        # Ensure logger is configured if run as script
        if not self.logger.handlers:
             logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


    def _setup_driver(self):
        """Configures and initializes the Chrome WebDriver."""
        self.logger.info("Initializing WebDriver...")
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--force-dark-mode')
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument(f"--window-size={self.window_size}")

        prefs = {
            "profile.content_settings.exceptions.clipboard": {
                f"[*.]tradingview.com,*": {"setting": 1}
            }
        }
        chrome_options.add_experimental_option("prefs", prefs)

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.logger.info("WebDriver initialized successfully.")
        except WebDriverException as e:
            self.logger.error(f"Failed to initialize WebDriver: {e}")
            raise TradingViewScraperError("WebDriver initialization failed") from e

    def _set_auth_cookies(self) -> bool:
        """Sets authentication cookies from environment variables."""
        session_id_value = os.getenv(self.SESSION_ID_ENV_VAR)
        session_id_sign_value = os.getenv(self.SESSION_ID_SIGN_ENV_VAR)

        if not session_id_value or not session_id_sign_value:
            self.logger.warning(f"TradingView session cookies not found. Ensure {self.SESSION_ID_ENV_VAR} and {self.SESSION_ID_SIGN_ENV_VAR} are set in environment.")
            return False # Indicate that auth cookies were not set

        if not self.driver:
             self.logger.error("Driver not initialized before setting cookies.")
             return False

        try:
            self.logger.info(f"Navigating to {self.TRADINGVIEW_BASE_URL} to set cookies...")
            self.driver.get(self.TRADINGVIEW_BASE_URL)
            time.sleep(self.COOKIE_WAIT_TIME) # Allow page load

            self.logger.info("Adding authentication cookies...")
            if session_id_value:
                self.driver.add_cookie({
                    'name': self.SESSION_ID_COOKIE,
                    'value': session_id_value,
                    'domain': '.tradingview.com',
                    'path': '/',
                    'secure': True,
                    'httpOnly': True
                })
            if session_id_sign_value:
                self.driver.add_cookie({
                    'name': self.SESSION_ID_SIGN_COOKIE,
                    'value': session_id_sign_value,
                    'domain': '.tradingview.com',
                    'path': '/',
                    'secure': True,
                    'httpOnly': True
                })
            self.logger.info("Authentication cookies added (if found in environment).")
            return True
        except (WebDriverException, TimeoutException) as e:
            self.logger.error(f"Error setting cookies or navigating to base URL: {e}")
            return False # Indicate failure

    def _navigate_and_wait(self, url: str):
        """Navigates to a URL and waits for a fixed duration."""
        if not self.driver:
            raise TradingViewScraperError("Driver not available for navigation.")
        try:
            self.logger.info(f"Navigating to chart URL: {url}")
            self.driver.get(url)
            # Replace with WebDriverWait for specific element if possible
            self.logger.info(f"Waiting {self.NAV_WAIT_TIME}s for page load...")
            time.sleep(self.NAV_WAIT_TIME)
            self.logger.info("Wait complete.")
        except (WebDriverException, TimeoutException) as e:
            self.logger.error(f"Failed to navigate to {url}: {e}")
            raise TradingViewScraperError(f"Navigation to {url} failed") from e


    def _trigger_screenshot_and_get_link(self) -> Optional[str]:
        """Triggers screenshot shortcut (Alt+S) and reads clipboard."""
        if not self.driver:
            raise TradingViewScraperError("Driver not available for triggering screenshot.")

        clipboard_content = None
        attempts = 0
        while attempts <= self.MAX_RETRY_ATTEMPTS and not clipboard_content:
            if attempts > 0:
                self.logger.info(f"Retrying Alt+S and clipboard read (Attempt {attempts + 1}/{self.MAX_RETRY_ATTEMPTS + 1})...")

            try:
                self.logger.info("Attempting to trigger screenshot shortcut (Alt+S)...")
                ActionChains(self.driver).key_down(Keys.ALT).send_keys('s').key_up(Keys.ALT).perform()
                self.logger.info(f"Waiting {self.CLIPBOARD_WAIT_TIME}s for clipboard population...")
                time.sleep(self.CLIPBOARD_WAIT_TIME)

                self.logger.info("Attempting to read clipboard via JavaScript...")
                clipboard_content = self.driver.execute_script(self.CLIPBOARD_READ_SCRIPT)

                if clipboard_content and isinstance(clipboard_content, str) and clipboard_content.strip():
                    self.logger.info("Successfully retrieved content from clipboard.")
                    return clipboard_content.strip()
                else:
                    self.logger.warning("Clipboard was empty or returned non-string/empty content.")
                    clipboard_content = None # Ensure loop continues if content invalid
            except (WebDriverException, TimeoutException) as e:
                self.logger.error(f"Error during screenshot trigger or clipboard read: {e}")
                # Decide if retry makes sense for this error type
                break # Stop retrying on general WebDriver errors
            attempts += 1

        if not clipboard_content:
            self.logger.error("Failed to retrieve screenshot link from clipboard after retries.")
        return None


    def get_screenshot_link(self, ticker: str, interval: str) -> Optional[str]:
        """
        Captures a TradingView chart screenshot link using Selenium.

        Args:
            ticker: The ticker symbol (e.g., "BYBIT:BTCUSDT.P", "NASDAQ:AAPL").
                    Should not be None or empty.
            interval: The chart interval (e.g., '1', '15', '60', 'D', 'W').
                      Should not be None or empty.

        Returns:
            The raw TradingView share URL string (e.g., https://www.tradingview.com/x/...)
            if successful, otherwise None.
        """
        if not self.driver:
            raise TradingViewScraperError("Driver not initialized. Use within a 'with' statement.")
        if not ticker or not interval:
             raise ValueError("Ticker and Interval must be provided.")

        try:
            # Attempt to set auth cookies, proceed even if it fails but log warning
            if not self._set_auth_cookies():
                self.logger.warning("Proceeding without guaranteed authentication (cookies not set).")

            chart_base_url = f"{self.TRADINGVIEW_CHART_BASE_URL}{self.chart_page_id}/"
            url = f"{chart_base_url}?symbol={ticker}&interval={interval}"

            self._navigate_and_wait(url)

            clipboard_link = self._trigger_screenshot_and_get_link()
            return clipboard_link

        except TradingViewScraperError:
            # Re-raise known scraper errors
            raise
        except (WebDriverException, TimeoutException) as e:
            self.logger.error(f"An unexpected WebDriver error occurred: {e}")
            raise TradingViewScraperError("Screenshot capture failed due to WebDriver error") from e
        except Exception as e:
            self.logger.error(f"An unexpected general error occurred: {e}", exc_info=True)
            raise TradingViewScraperError("An unexpected error occurred during screenshot capture") from e

    @staticmethod
    def convert_link_to_image_url(input_string: Optional[str]) -> Optional[str]:
        """Converts TradingView share links (e.g., /x/) to direct snapshot image links."""
        if not input_string:
            return None

        logger = logging.getLogger(__name__)

        # Regex to find links like 'https://www.tradingview.com/x/...' or 'https://in.tradingview.com/x/...'
        pattern = r'https://(?:www\.|in\.)?tradingview\.com/x/([a-zA-Z0-9]+)/?'

        output_string = input_string
        found_match = False
        for match in re.finditer(pattern, input_string):
            match_id = match.group(1)
            matched_url = match.group(0) # The full URL that was matched
            new_link = f'https://s3.tradingview.com/snapshots/{match_id[0].lower()}/{match_id}.png'

            # Replace only the specific matched URL to handle multiple links correctly
            if matched_url in output_string:
                output_string = output_string.replace(matched_url, new_link)
                logger.info(f"Converted {matched_url} to {new_link}")
                found_match = True
            else:
                 # This case should be rare if the match came from the input string
                 logger.warning(f"Pattern matched ID {match_id} ({matched_url}), but couldn't find exact link to replace in the current output string.")

        if not found_match and re.search(r'tradingview\.com/x/', input_string):
             logger.warning(f"Input string contained 'tradingview.com/x/' but regex pattern '{pattern}' did not match. Returning original.")
        elif not found_match:
             logger.debug("No TradingView share links found to convert.")


        return output_string


    def close(self):
        """Safely quits the WebDriver."""
        if self.driver:
            try:
                self.logger.info("Quitting WebDriver...")
                self.driver.quit()
                self.logger.info("WebDriver quit successfully.")
                self.driver = None
            except (WebDriverException, NoSuchWindowException) as e:
                self.logger.warning(f"Error quitting WebDriver (might be already closed): {e}")

    # --- Context Manager Support ---
    def __enter__(self):
        """Initializes the WebDriver when entering the context."""
        self._setup_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Closes the WebDriver when exiting the context."""
        self.close()


# --- Main Execution Example ---
if __name__ == "__main__":
    # Configure logging for script execution
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(dotenv_path):
         load_dotenv(dotenv_path=dotenv_path)
         logger.info(".env file loaded.")
    else:
         logger.warning(".env file not found, authentication might fail.")


    # --- Configuration for this specific run ---
    example_ticker = "BYBIT:ETHUSDT.P" # Or override the default
    desired_tf = '5' # Or override the default
    run_headless = True
    # chart_id_override = "YOUR_SPECIFIC_CHART_ID" # Optional

    logger.info(f"--- Starting TradingView Scraper for {example_ticker} ({desired_tf}) ---")

    raw_link = None
    image_url = None

    try:
        # Instantiate the scraper, potentially overriding defaults if needed
        # Defaults from __init__ are used if not specified here.
        with TradingViewScraper(
            headless=run_headless
            # default_ticker=example_ticker, # Example of overriding
            # default_interval=desired_tf,
            # chart_page_id=chart_id_override
        ) as scraper:
            logger.info(f"Attempting to capture screenshot link...")
            # Call get_screenshot_link with the specific ticker/interval for this run
            raw_link = scraper.get_screenshot_link(ticker=example_ticker, interval=desired_tf)

            if raw_link:
                logger.info(f"Raw clipboard data received: {raw_link}")
                image_url = TradingViewScraper.convert_link_to_image_url(raw_link)
                if image_url and image_url != raw_link :
                    logger.info(f"Converted image link: {image_url}")
                    print(f"\\nSuccess! Final Image Link:")
                    print(image_url)
                elif image_url == raw_link:
                     logger.warning("Received link did not appear to be a standard share link or conversion failed.")
                     print(f"\\nReceived link (no conversion applied):")
                     print(raw_link)
                else:
                    logger.error("Conversion returned None unexpectedly.")
                    print(f"\\nReceived link (conversion failed):")
                    print(raw_link)

            else:
                logger.error("Failed to capture screenshot link from clipboard.")
                print("\\nOperation failed: Could not retrieve link from clipboard.")

    except TradingViewScraperError as e:
        logger.error(f"Scraping failed: {e}")
        print(f"\\nOperation failed: {e}")
    except ValueError as e:
         logger.error(f"Configuration error: {e}")
         print(f"\\nOperation failed due to configuration error: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during the process: {e}", exc_info=True)
        print(f"\\nAn unexpected error occurred. Check logs for details.")

    logger.info(f"--- TradingView Scraper finished ---")

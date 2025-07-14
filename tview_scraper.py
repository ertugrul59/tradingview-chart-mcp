import logging
import os
import re
import time
import base64
import platform
import json
import shutil
import subprocess
from typing import Optional

from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import (
    WebDriverException,
    TimeoutException,
    NoSuchWindowException,
)
from selenium.webdriver import ActionChains, Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

load_dotenv()

# Configure WebDriver Manager to suppress logs
webdriver_manager_logger = logging.getLogger("WDM")
webdriver_manager_logger.setLevel(logging.WARNING)  # Only show warnings and errors


class TradingViewScraperError(Exception):
    """Custom exception for TradingView scraper errors."""

    pass


class TradingViewClipboardServerError(TradingViewScraperError):
    """Exception for server errors detected in clipboard content (for clipboard retry)."""

    def __init__(self, message, response_data=None):
        super().__init__(message)
        self.response_data = response_data


class TradingViewServerError(TradingViewScraperError):
    """Exception for TradingView server errors that should be retried."""

    def __init__(self, message, response_data=None):
        super().__init__(message)
        self.response_data = response_data


class TradingViewScraper:
    """
    A scraper for capturing TradingView chart screenshot links using Selenium.
    Manages WebDriver setup, authentication, and screenshot capture.
    """

    # --- Constants ---
    TRADINGVIEW_BASE_URL = "https://www.tradingview.com"
    TRADINGVIEW_CHART_BASE_URL = "https://in.tradingview.com/chart/"
    DEFAULT_CHART_PAGE_ID = "XHDbt5Yy"
    SESSION_ID_COOKIE = "sessionid"
    SESSION_ID_SIGN_COOKIE = "sessionid_sign"
    SESSION_ID_ENV_VAR = "TRADINGVIEW_SESSION_ID"
    SESSION_ID_SIGN_ENV_VAR = "TRADINGVIEW_SESSION_ID_SIGN"
    CLIPBOARD_READ_SCRIPT = "return navigator.clipboard.readText();"
    DEFAULT_WINDOW_SIZE = "1920,1080"
    MAX_CLIPBOARD_ATTEMPTS = 5  # Number of retries for clipboard read
    CLIPBOARD_RETRY_INTERVAL = 1  # seconds between attempts (traditional method)
    # Ultra-optimized intelligent waiting - much faster than previous versions
    MAX_CHART_WAIT_TIME = 6  # Maximum time for chart elements (reduced from 8s)
    # Optimized clipboard handling with method-specific timeouts
    MAX_CLIPBOARD_WAIT_TIME = (
        3  # Maximum time for text clipboard polling (reduced from 4s)
    )
    SAVE_SHORTCUT_IMAGE_DELAY = (
        0.3  # Ultra-short delay for image clipboard (reduced from 0.5s)
    )
    ACTION_DELAY = 0.3  # Reduced action delay (reduced from 0.5s)
    ASYNC_SCRIPT_TIMEOUT = (
        10  # Reduced timeout for async clipboard operations (reduced from 15s)
    )

    def __init__(
        self,
        default_ticker: str = "BYBIT:BTCUSDT.P",
        default_interval: str = "15",
        headless: bool = True,
        window_size: str = DEFAULT_WINDOW_SIZE,
        chart_page_id: str = DEFAULT_CHART_PAGE_ID,
        use_save_shortcut: bool = True,
    ):
        """Initializes the scraper configuration."""
        self.headless = headless
        self.window_size = window_size
        self.chart_page_id = chart_page_id
        self.default_ticker = default_ticker
        self.default_interval = default_interval
        self.use_save_shortcut = use_save_shortcut
        self.driver = None
        self.wait = None

        self.logger = logging.getLogger(__name__)
        # Ensure logger is configured if run as script
        if not self.logger.handlers:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )

        # Validate Chrome installation on Windows
        if platform.system() == "Windows":
            self._validate_chrome_installation()

    def _setup_driver(self):
        """Configures and initializes the Chrome WebDriver with optimized settings."""
        self.logger.info("Initializing WebDriver...")
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")

        # Performance optimizations
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")  # Faster in headless
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-features=TranslateUI")
        chrome_options.add_argument("--disable-ipc-flooding-protection")
        chrome_options.add_argument("--force-dark-mode")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument(f"--window-size={self.window_size}")

        # Faster page loading
        chrome_options.add_argument("--aggressive-cache-discard")
        chrome_options.add_argument("--memory-pressure-off")

        # Add clipboard permissions for image reading
        chrome_options.add_argument("--enable-clipboard-read-write")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")

        # Suppress GPU and graphics warnings
        chrome_options.add_argument("--disable-gpu-sandbox")
        chrome_options.add_argument("--disable-d3d11")
        chrome_options.add_argument("--disable-accelerated-2d-canvas")
        chrome_options.add_argument("--disable-accelerated-jpeg-decoding")
        chrome_options.add_argument("--disable-accelerated-mjpeg-decode")
        chrome_options.add_argument("--disable-accelerated-video-decode")
        chrome_options.add_argument("--disable-accelerated-video-encode")
        chrome_options.add_argument("--disable-gl-drawing-for-tests")
        chrome_options.add_argument("--disable-gl-extensions")
        chrome_options.add_argument("--disable-vulkan")
        chrome_options.add_argument("--disable-angle")
        chrome_options.add_argument("--disable-webgl")
        chrome_options.add_argument("--disable-webgl2")
        chrome_options.add_argument("--disable-3d-apis")
        chrome_options.add_argument("--use-gl=swiftshader")

        # Suppress DevTools and remote debugging warnings
        chrome_options.add_argument("--disable-dev-tools")
        chrome_options.add_argument("--disable-remote-debugging-port")
        chrome_options.add_argument("--disable-remote-extensions")
        chrome_options.add_argument("--disable-remote-fonts")

        # Suppress Google APIs/GCM registration errors
        chrome_options.add_argument("--disable-background-networking")
        chrome_options.add_argument("--disable-background-mode")
        chrome_options.add_argument("--disable-sync")
        chrome_options.add_argument("--disable-features=MediaRouter")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--disable-features=ChromeWhatsNewUI")
        chrome_options.add_argument("--disable-features=OptimizationHints")
        chrome_options.add_argument("--disable-features=Translate")
        chrome_options.add_argument("--disable-features=AudioServiceOutOfProcess")
        chrome_options.add_argument("--disable-features=VizHitTestSurfaceLayer")
        chrome_options.add_argument("--disable-features=VizHitTestDrawQuad")
        chrome_options.add_argument("--disable-client-side-phishing-detection")
        chrome_options.add_argument("--disable-default-apps")
        chrome_options.add_argument("--disable-hang-monitor")
        chrome_options.add_argument("--disable-prompt-on-repost")
        chrome_options.add_argument("--disable-domain-reliability")
        chrome_options.add_argument("--disable-component-update")
        chrome_options.add_argument("--disable-cloud-import")
        chrome_options.add_argument("--disable-field-trial-config")

        # Suppress TensorFlow Lite warnings
        chrome_options.add_argument("--disable-features=AutofillAblationStudy")
        chrome_options.add_argument("--disable-features=AutofillServerCommunication")
        chrome_options.add_argument("--disable-features=VoiceInteractionFramework")
        chrome_options.add_argument("--disable-features=AutofillKeyboardAccessory")
        chrome_options.add_argument("--disable-features=AutofillVirtualViewStructure")
        chrome_options.add_argument(
            "--disable-features=AutofillAddressProfileSavePrompt"
        )
        chrome_options.add_argument(
            "--disable-features=AutofillEnableProfileDeduplication"
        )
        chrome_options.add_argument(
            "--disable-features=AutofillEnableUpdatePromptForCards"
        )
        chrome_options.add_argument(
            "--disable-features=AutofillEnableOfferNotificationForPromoCodeOffers"
        )
        chrome_options.add_argument(
            "--disable-features=AutofillEnableOfferNotificationCrossTabTracking"
        )
        chrome_options.add_argument("--disable-features=AutofillEnableCardProductName")
        chrome_options.add_argument("--disable-features=AutofillEnableCardArtImage")
        chrome_options.add_argument("--disable-features=AutofillEnableCardMetadata")
        chrome_options.add_argument(
            "--disable-features=AutofillEnableCardProductNameFix"
        )
        chrome_options.add_argument("--disable-features=AutofillEnableCardArtImageFix")
        chrome_options.add_argument("--disable-features=AutofillEnableCardMetadataFix")
        chrome_options.add_argument(
            "--disable-features=AutofillEnableOfferNotificationForPromoCodeOffersFix"
        )
        chrome_options.add_argument(
            "--disable-features=AutofillEnableOfferNotificationCrossTabTrackingFix"
        )

        # Suppress logs and warnings
        chrome_options.add_argument("--log-level=3")  # Only fatal errors
        chrome_options.add_argument("--silent")
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_argument("--disable-gpu-log")
        chrome_options.add_argument("--disable-logging-redirect")

        prefs = {
            "profile.content_settings.exceptions.clipboard": {
                "[*.]tradingview.com,*": {"setting": 1}  # Allow clipboard access
            },
            # Additional clipboard permissions
            "profile.default_content_setting_values.clipboard": 1,
            "profile.content_settings.exceptions.clipboard": {
                "https://www.tradingview.com,*": {"setting": 1},
                "https://in.tradingview.com,*": {"setting": 1},
                "[*.]tradingview.com,*": {"setting": 1},
            },
            # Performance optimizations
            "profile.default_content_setting_values.notifications": 2,  # Block notifications
            "profile.default_content_settings.popups": 0,  # Block popups
            "profile.managed_default_content_settings.images": 1,  # Allow images (needed for charts)
        }
        chrome_options.add_experimental_option("prefs", prefs)

        # Get ChromeDriver path with Windows-specific fixes
        chromedriver_path = self._get_chromedriver_path()

        try:
            self.driver = webdriver.Chrome(
                service=ChromeService(chromedriver_path),
                options=chrome_options,
            )
            # Set optimized timeouts
            self.driver.set_script_timeout(self.ASYNC_SCRIPT_TIMEOUT)
            self.driver.implicitly_wait(1)  # Short implicit wait
            self.wait = WebDriverWait(self.driver, self.MAX_CHART_WAIT_TIME)
            self.logger.info(
                f"WebDriver initialized successfully with optimized settings."
            )
        except WebDriverException as e:
            self.logger.error(f"Failed to initialize WebDriver: {e}")
            raise TradingViewScraperError("WebDriver initialization failed") from e

    def _get_chromedriver_path(self):
        """Get ChromeDriver path with Windows-specific fixes."""
        try:
            # First, try the standard ChromeDriverManager
            chromedriver_path = ChromeDriverManager().install()

            # Check if the path is valid on Windows
            if platform.system() == "Windows":
                # Common issue: ChromeDriverManager returns incorrect path
                if not chromedriver_path.endswith(".exe"):
                    # Try to find the actual .exe file
                    chromedriver_dir = os.path.dirname(chromedriver_path)
                    possible_paths = [
                        os.path.join(chromedriver_dir, "chromedriver.exe"),
                        os.path.join(
                            chromedriver_dir, "chromedriver-win32", "chromedriver.exe"
                        ),
                        os.path.join(
                            chromedriver_dir, "chromedriver-win64", "chromedriver.exe"
                        ),
                    ]

                    for path in possible_paths:
                        if os.path.exists(path) and os.access(path, os.X_OK):
                            self.logger.info(f"Found ChromeDriver at: {path}")
                            return path

                # If still not found, try clearing cache and reinstalling
                self.logger.warning(
                    "ChromeDriver not found, clearing cache and reinstalling..."
                )
                self._clear_chromedriver_cache()
                chromedriver_path = ChromeDriverManager().install()

                # Check again
                if not chromedriver_path.endswith(".exe"):
                    chromedriver_dir = os.path.dirname(chromedriver_path)
                    for path in possible_paths:
                        if os.path.exists(path) and os.access(path, os.X_OK):
                            self.logger.info(
                                f"Found ChromeDriver after cache clear at: {path}"
                            )
                            return path

                # Last resort: try system PATH
                system_chromedriver = shutil.which("chromedriver")
                if system_chromedriver:
                    self.logger.info(
                        f"Using system ChromeDriver: {system_chromedriver}"
                    )
                    return system_chromedriver

                raise TradingViewScraperError(
                    "ChromeDriver executable not found. Please install ChromeDriver manually."
                )

            # For non-Windows systems, use the path as-is
            return chromedriver_path

        except Exception as e:
            self.logger.error(f"Error getting ChromeDriver path: {e}")
            raise TradingViewScraperError(f"Failed to get ChromeDriver path: {e}")

    def _clear_chromedriver_cache(self):
        """Clear ChromeDriver cache on Windows."""
        try:
            if platform.system() == "Windows":
                # ChromeDriverManager cache location
                cache_dir = os.path.expanduser("~/.wdm")
                if os.path.exists(cache_dir):
                    import shutil

                    shutil.rmtree(cache_dir)
                    self.logger.info("ChromeDriver cache cleared.")
        except Exception as e:
            self.logger.warning(f"Failed to clear ChromeDriver cache: {e}")

    def _validate_chrome_installation(self):
        """Validate that Chrome is properly installed."""
        try:
            if platform.system() == "Windows":
                # Check common Chrome installation paths
                chrome_paths = [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                    os.path.expanduser(
                        r"~\AppData\Local\Google\Chrome\Application\chrome.exe"
                    ),
                ]

                for path in chrome_paths:
                    if os.path.exists(path):
                        self.logger.info(f"Chrome found at: {path}")
                        return True

                # Try to get Chrome version
                try:
                    result = subprocess.run(
                        ["chrome", "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0:
                        self.logger.info(f"Chrome version: {result.stdout.strip()}")
                        return True
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass

                self.logger.warning(
                    "Chrome browser not found. Please install Google Chrome."
                )
                return False

            return True  # Assume Chrome is available on non-Windows systems

        except Exception as e:
            self.logger.warning(f"Error validating Chrome installation: {e}")
            return True  # Don't fail the process for validation errors

    def _set_auth_cookies_optimized(self, chart_url: str) -> bool:
        """Sets authentication cookies directly on chart URL for faster performance."""
        session_id_value = os.getenv(self.SESSION_ID_ENV_VAR)
        session_id_sign_value = os.getenv(self.SESSION_ID_SIGN_ENV_VAR)

        if not session_id_value or not session_id_sign_value:
            self.logger.warning(
                f"TradingView session cookies not found. Ensure {self.SESSION_ID_ENV_VAR} and {self.SESSION_ID_SIGN_ENV_VAR} are set in environment."
            )
            return False

        if not self.driver:
            self.logger.error("Driver not initialized before setting cookies.")
            return False

        try:
            # Navigate directly to chart URL (faster than base domain + redirect)
            self.logger.info(f"Navigating directly to chart URL for cookie setting...")
            self.driver.get(chart_url)

            # Set cookies immediately without additional wait
            self.logger.info("Adding authentication cookies...")
            if session_id_value:
                self.driver.add_cookie(
                    {
                        "name": self.SESSION_ID_COOKIE,
                        "value": session_id_value,
                        "domain": ".tradingview.com",
                        "path": "/",
                        "secure": True,
                        "httpOnly": True,
                    }
                )
            if session_id_sign_value:
                self.driver.add_cookie(
                    {
                        "name": self.SESSION_ID_SIGN_COOKIE,
                        "value": session_id_sign_value,
                        "domain": ".tradingview.com",
                        "path": "/",
                        "secure": True,
                        "httpOnly": True,
                    }
                )

            # Refresh to apply cookies
            self.logger.info("Refreshing page to apply cookies...")
            self.driver.refresh()
            self.logger.info("Authentication cookies applied successfully.")
            return True

        except (WebDriverException, TimeoutException) as e:
            self.logger.error(f"Error setting cookies: {e}")
            return False

    def _navigate_and_wait(self, url: str):
        """Navigates to a URL and waits for chart to be ready using advanced intelligent waiting."""
        if not self.driver:
            raise TradingViewScraperError("Driver not available for navigation.")
        try:
            self.logger.info(f"Navigating to chart URL: {url}")
            self.driver.get(url)

            # Advanced optimized intelligent waiting for chart readiness
            self.logger.info("Waiting for chart to be ready...")
            start_time = time.time()

            # Wait for essential chart elements with parallel detection
            try:
                # Use more specific and faster selectors for TradingView
                self.logger.info("Checking for chart infrastructure...")
                self.wait.until(
                    EC.any_of(
                        # Primary chart indicators (fastest to appear)
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "#header-toolbar-chart-styles")
                        ),
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".tv-header")),
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "[data-name='legend-source-item']")
                        ),
                        # Fallback selectors
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, ".chart-container, .tv-chart-container")
                        ),
                    )
                )
                self.logger.info("Chart infrastructure found.")

                # Parallel check for chart rendering elements
                self.logger.info("Checking for chart rendering...")
                chart_elements_ready = False
                max_element_wait = 2  # Very short wait for elements
                element_wait_start = time.time()

                while (
                    not chart_elements_ready
                    and (time.time() - element_wait_start) < max_element_wait
                ):
                    try:
                        # Check multiple element types in parallel
                        canvas_elements = self.driver.find_elements(
                            By.CSS_SELECTOR, "canvas"
                        )
                        chart_widgets = self.driver.find_elements(
                            By.CSS_SELECTOR,
                            ".chart-widget, .tv-chart-widget, [data-name='chart-widget']",
                        )
                        price_elements = self.driver.find_elements(
                            By.CSS_SELECTOR,
                            ".tv-symbol-header, [data-name='legend-source-item']",
                        )

                        # Quick readiness check
                        if (len(canvas_elements) > 0 or len(chart_widgets) > 0) and len(
                            price_elements
                        ) > 0:
                            chart_elements_ready = True
                            break

                    except Exception:
                        pass

                    time.sleep(0.1)  # Very fast polling

                if chart_elements_ready:
                    self.logger.info("Chart rendering elements found.")
                else:
                    self.logger.info(
                        "Chart elements not fully detected, proceeding anyway."
                    )

                # Method-specific optimization
                if self.use_save_shortcut:
                    # Ultra-minimal wait for save shortcut method
                    self.logger.info(
                        "Save shortcut method - ultra-fast readiness check..."
                    )

                    # Just ensure no major loading indicators
                    loading_check_start = time.time()
                    max_loading_check = 1.5  # Very short

                    while (time.time() - loading_check_start) < max_loading_check:
                        try:
                            loading_indicators = self.driver.find_elements(
                                By.CSS_SELECTOR,
                                ".tv-spinner--shown, .loading, [data-role='spinner']",
                            )

                            if not loading_indicators:
                                break
                        except Exception:
                            pass

                        time.sleep(0.1)

                    elapsed = time.time() - start_time
                    self.logger.info(
                        f"Chart ready for capture in {elapsed:.1f}s (ultra-fast save shortcut)"
                    )

                else:
                    # Traditional method with minimal data check
                    self.logger.info("Traditional method - minimal data check...")
                    chart_ready = False
                    max_data_wait = 2  # Reduced from 5 seconds
                    data_wait_start = time.time()

                    while (
                        not chart_ready
                        and (time.time() - data_wait_start) < max_data_wait
                    ):
                        try:
                            # Quick parallel check
                            price_elements = self.driver.find_elements(
                                By.CSS_SELECTOR,
                                "[data-name='legend-source-item'], .tv-symbol-header, .js-button-text",
                            )
                            canvas_elements = self.driver.find_elements(
                                By.CSS_SELECTOR, "canvas"
                            )
                            loading_indicators = self.driver.find_elements(
                                By.CSS_SELECTOR,
                                ".tv-spinner--shown, .loading, [data-role='spinner']",
                            )

                            if (
                                len(price_elements) > 0
                                and len(canvas_elements) > 0
                                and not loading_indicators
                            ):
                                chart_ready = True
                                break
                        except Exception:
                            pass

                        time.sleep(0.1)  # Very fast polling

                    elapsed = time.time() - start_time
                    if chart_ready:
                        self.logger.info(
                            f"Chart ready in {elapsed:.1f}s (optimized traditional)"
                        )
                    else:
                        self.logger.info(
                            f"Chart readiness timeout after {elapsed:.1f}s, proceeding anyway"
                        )

            except TimeoutException:
                # Ultra-short fallback
                elapsed = time.time() - start_time
                self.logger.warning(
                    f"Chart elements not found after {elapsed:.1f}s, using minimal fallback..."
                )
                time.sleep(0.5)  # Minimal fallback wait
                elapsed = time.time() - start_time
                self.logger.info(f"Total wait time: {elapsed:.1f}s (minimal fallback)")

        except (WebDriverException, TimeoutException) as e:
            self.logger.error(f"Failed to navigate to {url}: {e}")
            raise TradingViewScraperError(f"Navigation to {url} failed") from e

    def _trigger_screenshot_and_get_link(self) -> Optional[str]:
        """Triggers screenshot shortcut (Alt+S) and reads clipboard with intelligent waiting."""
        if not self.driver:
            raise TradingViewScraperError(
                "Driver not available for triggering screenshot."
            )

        clipboard_content = None
        for attempt in range(self.MAX_CLIPBOARD_ATTEMPTS):
            self.logger.info(
                f"Attempting to get clipboard content (attempt {attempt + 1}/{self.MAX_CLIPBOARD_ATTEMPTS})..."
            )

            try:
                self.logger.info("Attempting to trigger screenshot shortcut (Alt+S)...")
                ActionChains(self.driver).key_down(Keys.ALT).send_keys("s").key_up(
                    Keys.ALT
                ).perform()

                # Intelligent wait for clipboard instead of fixed 3s
                self.logger.info("Waiting for clipboard to be populated...")
                clipboard_ready = False
                max_clipboard_wait = 5  # Maximum 5 seconds instead of fixed 3s
                clipboard_wait_start = time.time()

                while (
                    not clipboard_ready
                    and (time.time() - clipboard_wait_start) < max_clipboard_wait
                ):
                    try:
                        test_content = self.driver.execute_script(
                            self.CLIPBOARD_READ_SCRIPT
                        )
                        if (
                            test_content
                            and isinstance(test_content, str)
                            and test_content.strip()
                        ):
                            clipboard_content = test_content.strip()
                            clipboard_ready = True
                            elapsed = time.time() - clipboard_wait_start
                            self.logger.info(f"Clipboard populated in {elapsed:.1f}s")
                            break
                    except WebDriverException:
                        pass  # Continue waiting

                    time.sleep(0.2)  # Check every 200ms

                if not clipboard_ready:
                    # Final attempt
                    self.logger.info("Final attempt to read clipboard...")
                    try:
                        clipboard_content = self.driver.execute_script(
                            self.CLIPBOARD_READ_SCRIPT
                        )
                    except WebDriverException as e:
                        self.logger.warning(f"Failed to read clipboard: {e}")
                        clipboard_content = None

                if (
                    clipboard_content
                    and isinstance(clipboard_content, str)
                    and clipboard_content.strip()
                ):
                    self.logger.info("Successfully retrieved content from clipboard.")
                    return clipboard_content.strip()
                else:
                    self.logger.warning(
                        "Clipboard was empty or returned non-string/empty content."
                    )
                    clipboard_content = None  # Ensure loop continues if content invalid
            except (WebDriverException, TimeoutException) as e:
                self.logger.error(
                    f"Error during screenshot trigger or clipboard read: {e}"
                )
                # Decide if retry makes sense for this error type
                break  # Stop retrying on general WebDriver errors

            # Wait before retrying
            if attempt < self.MAX_CLIPBOARD_ATTEMPTS - 1:
                self.logger.info(
                    f"Clipboard empty/no content yet, waiting {self.CLIPBOARD_RETRY_INTERVAL}s before retrying..."
                )
                time.sleep(self.CLIPBOARD_RETRY_INTERVAL)

        if not clipboard_content:
            self.logger.error(
                "Failed to retrieve screenshot link from clipboard after retries."
            )
        return None

    def _get_clipboard_content(self) -> Optional[str]:
        """Get clipboard content with intelligent retry logic optimized for save shortcut method."""
        if not self.driver:
            raise TradingViewScraperError("Driver not available for clipboard reading.")

        clipboard_content = None
        for attempt in range(self.MAX_CLIPBOARD_ATTEMPTS):
            self.logger.info(
                f"Attempting to get clipboard content (attempt {attempt + 1}/{self.MAX_CLIPBOARD_ATTEMPTS})..."
            )
            try:
                # Send the save shortcut key combination
                self._send_save_shortcut()

                # Optimization: For save shortcut method, skip text clipboard and go directly to image
                if self.use_save_shortcut:
                    self.logger.info(
                        "Save shortcut method - going directly to image clipboard reading..."
                    )
                    # Ultra-short delay for clipboard to be populated with image
                    time.sleep(self.SAVE_SHORTCUT_IMAGE_DELAY)  # Use optimized constant

                    # Try to read image directly
                    image_data = self._read_image_from_clipboard()
                    if image_data:
                        self.logger.info(
                            "Successfully retrieved image data from clipboard."
                        )
                        return self._convert_clipboard_to_image_url(image_data)
                    else:
                        self.logger.warning(
                            "No image data found in clipboard, will retry..."
                        )

                else:
                    # Traditional method: intelligent text clipboard polling
                    self.logger.info("Traditional method - polling text clipboard...")
                    clipboard_ready = False
                    max_clipboard_wait = (
                        self.MAX_CLIPBOARD_WAIT_TIME
                    )  # Use optimized constant
                    clipboard_wait_start = time.time()

                    while (
                        not clipboard_ready
                        and (time.time() - clipboard_wait_start) < max_clipboard_wait
                    ):
                        try:
                            # Try to read text from clipboard
                            test_content = self.driver.execute_script(
                                "return navigator.clipboard.readText();"
                            )
                            if test_content and test_content.strip():
                                clipboard_content = test_content
                                clipboard_ready = True
                                elapsed = time.time() - clipboard_wait_start
                                self.logger.info(
                                    f"Clipboard populated in {elapsed:.1f}s"
                                )
                                break
                        except WebDriverException:
                            pass  # Continue waiting

                        time.sleep(0.1)  # Very fast polling (reduced from 0.2s)

                    if not clipboard_ready:
                        # Final attempt after max wait
                        try:
                            clipboard_content = self.driver.execute_script(
                                "return navigator.clipboard.readText();"
                            )
                            self.logger.info(
                                f'Text clipboard content: {"[empty]" if not clipboard_content else "[content received]"}'
                            )
                        except WebDriverException as e:
                            self.logger.warning(
                                f"Failed to read text from clipboard: {e}"
                            )
                            clipboard_content = None

                    # Check if we got valid text content
                    if clipboard_content and clipboard_content.strip():
                        # Check for server error JSON in clipboard content
                        try:
                            response = json.loads(clipboard_content)
                            if (
                                isinstance(response, dict)
                                and "code" in response
                                and "msg" in response
                                and response.get("success") is False
                            ):
                                error_code = response.get("code")
                                error_msg = response.get("msg")
                                retryable_codes = [
                                    "40001",
                                    40001,
                                    "50000",
                                    50000,
                                    "502",
                                    502,
                                    "503",
                                    503,
                                ]
                                if (
                                    error_code in retryable_codes
                                    or "Server Error" in str(error_msg)
                                ):
                                    self.logger.warning(
                                        f"🔄 Detected retryable server error in clipboard: {clipboard_content}"
                                    )
                                    raise TradingViewClipboardServerError(
                                        f"Server error in clipboard: {error_msg} (code: {error_code})",
                                        response,
                                    )
                        except (json.JSONDecodeError, TypeError):
                            pass  # Not JSON, treat as normal content

                        self.logger.info(
                            "Successfully retrieved text content from clipboard."
                        )
                        return clipboard_content

                    # If still no content, try alternative shortcuts for traditional method
                    if not clipboard_content or not clipboard_content.strip():
                        self.logger.info(
                            "No content found, trying alternative shortcuts..."
                        )
                        if self._try_alternative_shortcuts():
                            # Try reading text clipboard again after alternative shortcut
                            try:
                                alt_clipboard_content = self.driver.execute_script(
                                    "return navigator.clipboard.readText();"
                                )
                                if (
                                    alt_clipboard_content
                                    and alt_clipboard_content.strip()
                                ):
                                    self.logger.info(
                                        "Alternative shortcut produced text content."
                                    )
                                    return alt_clipboard_content
                            except WebDriverException as e:
                                self.logger.warning(
                                    f"Failed to read clipboard after alternative shortcut: {e}"
                                )

            except TradingViewClipboardServerError as e:
                self.logger.warning(
                    f"[Clipboard] Server error detected in clipboard, will retry: {e}"
                )
            except WebDriverException as js_err:
                self.logger.warning(f"Error during clipboard operation: {js_err}")

            # Wait before retrying (shorter intervals)
            if attempt < self.MAX_CLIPBOARD_ATTEMPTS - 1:
                retry_delay = (
                    0.5 if self.use_save_shortcut else self.CLIPBOARD_RETRY_INTERVAL
                )
                self.logger.info(
                    f"Clipboard empty/no content yet, waiting {retry_delay}s before retrying..."
                )
                time.sleep(retry_delay)

        self.logger.error("Failed to get clipboard content after multiple attempts.")
        raise TradingViewScraperError(
            "Failed to get clipboard content after multiple attempts"
        )

    def _send_save_shortcut(self):
        """Send the appropriate save shortcut key combination."""
        if not self.driver:
            raise TradingViewScraperError("Driver not available for sending shortcuts.")

        try:
            # Determine the correct key combination based on platform
            if platform.system() == "Darwin":  # macOS
                self.logger.info("Sending Shift+Cmd+S key combination...")
                ActionChains(self.driver).key_down(Keys.SHIFT).key_down(
                    Keys.COMMAND
                ).send_keys("s").key_up(Keys.COMMAND).key_up(Keys.SHIFT).perform()
            else:  # Windows/Linux
                self.logger.info("Sending Shift+Ctrl+S key combination...")
                ActionChains(self.driver).key_down(Keys.SHIFT).key_down(
                    Keys.CONTROL
                ).send_keys("s").key_up(Keys.CONTROL).key_up(Keys.SHIFT).perform()

            self.logger.info("Shift+Ctrl/Command+S sent.")

        except Exception as e:
            self.logger.error(f"Error sending save shortcut: {e}")
            raise

    def _try_alternative_shortcuts(self):
        """Try alternative keyboard shortcuts for capturing charts."""
        shortcuts = [
            (
                "Ctrl+Alt+S",
                lambda: ActionChains(self.driver)
                .key_down(Keys.CONTROL)
                .key_down(Keys.ALT)
                .send_keys("s")
                .key_up(Keys.ALT)
                .key_up(Keys.CONTROL)
                .perform(),
            ),
            (
                "Ctrl+S",
                lambda: ActionChains(self.driver)
                .key_down(Keys.CONTROL)
                .send_keys("s")
                .key_up(Keys.CONTROL)
                .perform(),
            ),
            (
                "Alt+Shift+S",
                lambda: ActionChains(self.driver)
                .key_down(Keys.ALT)
                .key_down(Keys.SHIFT)
                .send_keys("s")
                .key_up(Keys.SHIFT)
                .key_up(Keys.ALT)
                .perform(),
            ),
        ]

        for shortcut_name, shortcut_action in shortcuts:
            try:
                self.logger.info(f"Trying alternative shortcut: {shortcut_name}")
                shortcut_action()
                time.sleep(2)
                return True
            except WebDriverException as e:
                self.logger.warning(f"Failed to send {shortcut_name}: {e}")
                continue
        return False

    def _read_image_from_clipboard(self) -> Optional[bytes]:
        """Read image data from clipboard using JavaScript with optimized performance."""
        if not self.driver:
            raise TradingViewScraperError(
                "Driver not available for reading image from clipboard."
            )

        try:
            # Quick check if clipboard API is available
            has_clipboard_api = self.driver.execute_script(
                """
                return navigator.clipboard && typeof navigator.clipboard.read === 'function';
            """
            )

            if not has_clipboard_api:
                self.logger.warning(
                    "Clipboard API not available or read method not supported."
                )
                return None

            self.logger.info("Reading image data from clipboard...")

            # Optimized async script with ultra-short timeout for maximum performance
            image_data_url = self.driver.execute_async_script(
                """
                var callback = arguments[arguments.length - 1];
                var timeoutId;
                
                // Ultra-short timeout for maximum performance (3s instead of 5s)
                timeoutId = setTimeout(function() {
                    console.log('Clipboard read timeout after 3 seconds');
                    callback(null);
                }, 3000);
                
                async function readClipboardImage() {
                    try {
                        console.log('Starting clipboard read...');
                        const items = await navigator.clipboard.read();
                        console.log('Got clipboard items:', items.length);
                        
                        for (const item of items) {
                            console.log('Item types:', item.types);
                            for (const type of item.types) {
                                if (type.startsWith('image/')) {
                                    console.log('Found image type:', type);
                                    const blob = await item.getType(type);
                                    console.log('Got blob, size:', blob.size);
                                    
                                    // Use fastest blob reading approach
                                    const reader = new FileReader();
                                    reader.onload = function() {
                                        console.log('FileReader loaded, result length:', reader.result.length);
                                        clearTimeout(timeoutId);
                                        callback(reader.result);
                                    };
                                    reader.onerror = function(error) {
                                        console.error('FileReader error:', error);
                                        clearTimeout(timeoutId);
                                        callback(null);
                                    };
                                    reader.readAsDataURL(blob);
                                    return; // Exit early since we found an image
                                }
                            }
                        }
                        console.log('No image found in clipboard');
                        clearTimeout(timeoutId);
                        callback(null);
                    } catch (error) {
                        console.error('Clipboard read error:', error);
                        clearTimeout(timeoutId);
                        callback(null);
                    }
                }
                
                readClipboardImage();
            """
            )

            if image_data_url and image_data_url.startswith("data:image/"):
                self.logger.info(
                    f"Successfully read image data from clipboard (length: {len(image_data_url)})"
                )
                # Convert data URL to bytes for consistency with Coinglass pattern
                header, data = image_data_url.split(",", 1)
                image_bytes = base64.b64decode(data)
                return image_bytes
            else:
                self.logger.warning(
                    "No image data found in clipboard or invalid format."
                )
                return None

        except WebDriverException as e:
            self.logger.warning(f"Failed to read image from clipboard: {e}")
            return None

    def _convert_clipboard_to_image_url(self, image_data: bytes) -> str:
        """Convert clipboard image data to base64 data URL."""
        try:
            self.logger.info("Converting clipboard content to image URL...")

            # Convert to base64 data URL
            base64_encoded = base64.b64encode(image_data).decode("utf-8")
            data_url = f"data:image/png;base64,{base64_encoded}"

            self.logger.info(
                f"response_string >>> {data_url[:100]}{'...' if len(data_url) > 100 else ''}"
            )
            self.logger.info("Detected base64 image data URL from clipboard.")

            return data_url

        except Exception as e:
            self.logger.error(f"Error converting clipboard content to image URL: {e}")
            raise TradingViewScraperError(f"Failed to convert clipboard content: {e}")

    def get_chart_image_url(self, ticker: str, interval: str) -> Optional[str]:
        """
        Captures a TradingView chart image directly to clipboard and returns base64 data URL.

        Args:
            ticker: The ticker symbol (e.g., "BYBIT:BTCUSDT.P", "NASDAQ:AAPL").
            interval: The chart interval (e.g., '1', '15', '60', 'D', 'W').

        Returns:
            Base64 data URL string if successful, otherwise None.
        """
        self.logger.info(
            f"=== Starting chart capture for {ticker} (timeframe: {interval}) ==="
        )
        if not self.driver:
            raise TradingViewScraperError(
                "Driver not initialized. Use within a 'with' statement."
            )
        if not ticker or not interval:
            raise ValueError("Ticker and Interval must be provided.")

        try:
            # Attempt to set auth cookies
            if not self._set_auth_cookies_optimized(
                f"{self.TRADINGVIEW_CHART_BASE_URL}{self.chart_page_id}/?symbol={ticker}&interval={interval}"
            ):
                self.logger.warning(
                    "Proceeding without guaranteed authentication (cookies not set)."
                )

            # Navigate to chart
            self._navigate_and_wait(
                f"{self.TRADINGVIEW_CHART_BASE_URL}{self.chart_page_id}/?symbol={ticker}&interval={interval}"
            )

            # Clear browser clipboard before reading
            self.logger.info("Attempting to clear browser clipboard before reading...")
            try:
                self.driver.execute_script("navigator.clipboard.writeText('');")
                self.logger.info("Browser clipboard cleared.")
                time.sleep(self.ACTION_DELAY)
            except WebDriverException as clear_err:
                self.logger.warning(f"Could not clear browser clipboard: {clear_err}")

            # Get clipboard content (image data)
            self.logger.info("Starting clipboard content retrieval...")
            image_url = self._get_clipboard_content()

            if image_url and (
                image_url.startswith("https://s3.tradingview.com/snapshots/")
                or image_url.startswith("data:image/")
            ):
                self.logger.info(
                    f"[Result] Successfully obtained image URL: {image_url[:100]}{'...' if len(image_url) > 100 else ''}"
                )
            else:
                self.logger.warning(
                    f"[Result] Unexpected image URL or format: {image_url}"
                )

            self.logger.info(
                f"=== Finished chart capture for {ticker} (timeframe: {interval}) ==="
            )
            return image_url

        except TradingViewScraperError as e:
            self.logger.error(f"Scraping failed: {e}")
            return None  # Or re-raise if preferred
        except Exception as e:
            self.logger.error(f"An unexpected error occurred: {e}", exc_info=True)
            return None  # Or re-raise

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
            raise TradingViewScraperError(
                "Driver not initialized. Use within a 'with' statement."
            )
        if not ticker or not interval:
            raise ValueError("Ticker and Interval must be provided.")

        try:
            # Attempt to set auth cookies, proceed even if it fails but log warning
            if not self._set_auth_cookies_optimized(
                f"{self.TRADINGVIEW_CHART_BASE_URL}{self.chart_page_id}/?symbol={ticker}&interval={interval}"
            ):
                self.logger.warning(
                    "Proceeding without guaranteed authentication (cookies not set)."
                )

            self._navigate_and_wait(
                f"{self.TRADINGVIEW_CHART_BASE_URL}{self.chart_page_id}/?symbol={ticker}&interval={interval}"
            )

            clipboard_link = self._trigger_screenshot_and_get_link()
            return clipboard_link

        except TradingViewScraperError:
            # Re-raise known scraper errors
            raise
        except (WebDriverException, TimeoutException) as e:
            self.logger.error(f"An unexpected WebDriver error occurred: {e}")
            raise TradingViewScraperError(
                "Screenshot capture failed due to WebDriver error"
            ) from e
        except Exception as e:
            self.logger.error(
                f"An unexpected general error occurred: {e}", exc_info=True
            )
            raise TradingViewScraperError(
                "An unexpected error occurred during screenshot capture"
            ) from e

    @staticmethod
    def convert_link_to_image_url(input_string: Optional[str]) -> Optional[str]:
        """Converts TradingView share links (e.g., /x/) to direct snapshot image links."""
        if not input_string:
            return None

        logger = logging.getLogger(__name__)

        # Regex to find links like 'https://www.tradingview.com/x/...' or 'https://in.tradingview.com/x/...'
        pattern = r"https://(?:www\.|in\.)?tradingview\.com/x/([a-zA-Z0-9]+)/?"

        output_string = input_string
        found_match = False
        for match in re.finditer(pattern, input_string):
            match_id = match.group(1)
            matched_url = match.group(0)  # The full URL that was matched
            new_link = f"https://s3.tradingview.com/snapshots/{match_id[0].lower()}/{match_id}.png"

            # Replace only the specific matched URL to handle multiple links correctly
            if matched_url in output_string:
                output_string = output_string.replace(matched_url, new_link)
                logger.info(f"Converted {matched_url} to {new_link}")
                found_match = True
            else:
                # This case should be rare if the match came from the input string
                logger.warning(
                    f"Pattern matched ID {match_id} ({matched_url}), but couldn't find exact link to replace in the current output string."
                )

        if not found_match and re.search(r"tradingview\.com/x/", input_string):
            logger.warning(
                f"Input string contained 'tradingview.com/x/' but regex pattern '{pattern}' did not match. Returning original."
            )
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
                self.logger.warning(
                    f"Error quitting WebDriver (might be already closed): {e}"
                )
            except (ConnectionError, OSError, KeyboardInterrupt) as e:
                self.logger.warning(
                    f"Connection error during WebDriver quit (ignoring): {e}"
                )
                self.driver = None  # Mark as closed even if quit failed
            except Exception as e:
                self.logger.warning(
                    f"Unexpected error during WebDriver quit (ignoring): {e}"
                )
                self.driver = None  # Mark as closed even if quit failed

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
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

    # --- Configuration for this specific run ---
    example_ticker = "BYBIT:ETHUSDT.P"  # Or override the default
    desired_tf = "5"  # Or override the default
    run_headless = True
    # chart_id_override = "YOUR_SPECIFIC_CHART_ID" # Optional

    logger.info(
        f"--- Starting TradingView Scraper for {example_ticker} ({desired_tf}) ---"
    )

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
            raw_link = scraper.get_screenshot_link(
                ticker=example_ticker, interval=desired_tf
            )

            if raw_link:
                logger.info(f"Raw clipboard data received: {raw_link}")
                image_url = TradingViewScraper.convert_link_to_image_url(raw_link)
                if image_url and image_url != raw_link:
                    logger.info(f"Converted image link: {image_url}")
                    print(f"\\nSuccess! Final Image Link:")
                    print(image_url)
                elif image_url == raw_link:
                    logger.warning(
                        "Received link did not appear to be a standard share link or conversion failed."
                    )
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
        logger.error(
            f"An unexpected error occurred during the process: {e}", exc_info=True
        )
        print(f"\\nAn unexpected error occurred. Check logs for details.")

    logger.info(f"--- TradingView Scraper finished ---")

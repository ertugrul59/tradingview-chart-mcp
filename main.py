import os
import importlib.util
import sys
import asyncio # Added for await
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP, Context
from mcp.types import ErrorData as Error # Import ErrorData and alias it as Error

# --- Dynamically load tview_scraper.py ---
scraper_module = None
TradingViewScraper = None
TradingViewScraperError = None

try:
    scraper_path = os.path.join(os.path.dirname(__file__), 'tview-scraper.py')
    if not os.path.exists(scraper_path):
        raise FileNotFoundError("tview-scraper.py not found in the same directory as main.py")

    spec = importlib.util.spec_from_file_location("tview_scraper", scraper_path)
    if spec and spec.loader:
        scraper_module = importlib.util.module_from_spec(spec)
        sys.modules["tview_scraper"] = scraper_module
        spec.loader.exec_module(scraper_module)
        TradingViewScraper = getattr(scraper_module, 'TradingViewScraper')
        TradingViewScraperError = getattr(scraper_module, 'TradingViewScraperError')
        print("Successfully loaded tview_scraper module.")
    else:
        raise ImportError("Could not create module spec for tview_scraper.py")
except (FileNotFoundError, ImportError, AttributeError, Exception) as e:
    print(f"Fatal Error: Could not load tview_scraper module: {e}")
    exit(1)
# --- End Dynamic Load ---

# Load .env file if it exists. Environment variables set directly (e.g., by MCP client) take precedence.
load_dotenv()

# --- Configuration ---
# Read from environment variables (which may have been loaded from .env or set directly)
TRADINGVIEW_SESSION_ID = os.getenv("TRADINGVIEW_SESSION_ID")
TRADINGVIEW_SESSION_ID_SIGN = os.getenv("TRADINGVIEW_SESSION_ID_SIGN")

# Check if required credentials are set (via environment variables or .env file)
if not TRADINGVIEW_SESSION_ID or not TRADINGVIEW_SESSION_ID_SIGN:
    print("Error: TRADINGVIEW_SESSION_ID and TRADINGVIEW_SESSION_ID_SIGN must be set.")
    print("       Provide them either via environment variables (e.g., in MCP client config)")
    print("       or in a .env file in the project directory for local execution.")
    exit(1)

# Optional Scraper Configuration with defaults
HEADLESS = os.getenv("MCP_SCRAPER_HEADLESS", "True").lower() == "true"
WINDOW_WIDTH = int(os.getenv("MCP_SCRAPER_WINDOW_WIDTH", "1920"))
WINDOW_HEIGHT = int(os.getenv("MCP_SCRAPER_WINDOW_HEIGHT", "1080"))
# Use default chart page ID from scraper if env var is empty or not set
CHART_PAGE_ID_ENV = os.getenv("MCP_SCRAPER_CHART_PAGE_ID", "")
CHART_PAGE_ID = CHART_PAGE_ID_ENV if CHART_PAGE_ID_ENV else TradingViewScraper.DEFAULT_CHART_PAGE_ID

WINDOW_SIZE = (WINDOW_WIDTH, WINDOW_HEIGHT)

# --- MCP Server Definition (using FastMCP) ---
# Renamed variable to avoid conflict with potential future 'mcp' module imports
mcp_server = FastMCP(
    "TradingView Chart Image",
    # lifespan=app_lifespan, # Add lifespan management if needed
    # dependencies=["selenium", "python-dotenv"] # Optional
)

# --- Tool Definition ---
@mcp_server.tool() # Use the FastMCP instance as decorator
async def get_tradingview_chart_image(ticker: str, interval: str, ctx: Context) -> str: # Make function async
    """
    Fetches the direct image URL for a TradingView chart snapshot.

    Args:
        ticker: The TradingView ticker symbol (e.g., "BYBIT:BTCUSDT.P", "NASDAQ:AAPL").
        interval: The chart time interval (e.g., '1', '5', '15', '60', '240', 'D', 'W').
        ctx: MCP Context (automatically passed by FastMCP).

    Returns:
        The direct TradingView snapshot image URL (e.g., https://s3.tradingview.com/snapshots/.../...png).

    Raises:
        Error: If the scraper fails or invalid input is provided.
    """
    await ctx.info(f"Attempting to get chart image for {ticker} interval {interval}") # Added await
    try:
        # Use the scraper as a context manager
        # Note: Assuming TradingViewScraper itself and its methods used here
        # (get_screenshot_link, convert_link_to_image_url) are synchronous.
        # If they become async, they will need `await` too.
        with TradingViewScraper(
            # Remove session_id and session_id_sign, they are read from env vars by the scraper
            headless=HEADLESS,
            window_size=f"{WINDOW_WIDTH},{WINDOW_HEIGHT}", # Pass as formatted string
            chart_page_id=CHART_PAGE_ID
        ) as scraper:
            screenshot_link = scraper.get_screenshot_link(ticker, interval)
            if not screenshot_link:
                 raise TradingViewScraperError("Scraper did not return a screenshot link from clipboard.")
            image_url = scraper.convert_link_to_image_url(screenshot_link)
            if not image_url:
                 raise TradingViewScraperError("Failed to convert screenshot link to image URL.")
            await ctx.info(f"Successfully obtained image URL for {ticker} ({interval}): {image_url}") # Added await
            return image_url
    except TradingViewScraperError as e:
        await ctx.error(f"Scraper Error: {e}") # Added await
        raise Exception(f"Scraper Error: {e}") # Simplified exception
    except ValueError as e:
        await ctx.error(f"Input Error: {e}") # Added await
        raise Exception(f"Input Error: {e}") # Simplified exception
    except Exception as e:
        await ctx.error(f"Unexpected error in get_tradingview_chart_image: {e}") # Added await, removed exc_info=True
        raise Exception(f"Unexpected error: {e}") # Simplified exception


# --- Prompt Definitions ---
@mcp_server.prompt("Get the {interval} minute chart for {ticker}")
async def get_chart_prompt_minutes(ticker: str, interval: str, ctx: Context): # Make function async
    await ctx.info(f"Executing prompt: Get the {interval} minute chart for {ticker}") # Added await
    # Need to await the async tool function
    return await get_tradingview_chart_image(ticker=ticker, interval=interval, ctx=ctx)

@mcp_server.prompt("Show me the daily chart for {ticker}")
async def get_chart_prompt_daily(ticker: str, ctx: Context): # Make function async
    await ctx.info(f"Executing prompt: Show me the daily chart for {ticker}") # Added await
    # Need to await the async tool function
    return await get_tradingview_chart_image(ticker=ticker, interval='D', ctx=ctx)

@mcp_server.prompt("Fetch TradingView chart image for {ticker} on the {interval} timeframe")
async def get_chart_prompt_timeframe(ticker: str, interval: str, ctx: Context): # Make function async
    await ctx.info(f"Executing prompt: Fetch TradingView chart image for {ticker} on the {interval} timeframe") # Added await
    interval_map = {
        "daily": "D",
        "weekly": "W",
        "monthly": "M", # Assuming 'M' is supported, adjust if needed
        "1 minute": "1",
        "5 minute": "5",
        "15 minute": "15",
        "1 hour": "60", # Assuming '60' is supported, adjust if needed (e.g., '1H')
        "4 hour": "240", # Assuming '240' is supported, adjust if needed (e.g., '4H')
    }
    # Use provided interval directly if it doesn't match common names or is already a code
    mcp_interval = interval_map.get(interval.lower(), interval)
    await ctx.info(f"Mapped interval '{interval}' to '{mcp_interval}'") # Added await
    # Need to await the async tool function
    return await get_tradingview_chart_image(ticker=ticker, interval=mcp_interval, ctx=ctx)

# --- Run the Server ---
if __name__ == "__main__":
    print("Starting TradingView Chart Image MCP Server...")
    print(f" - Headless: {HEADLESS}")
    print(f" - Window Size: {WINDOW_SIZE}")
    print(f" - Chart Page ID: {CHART_PAGE_ID}")
    # Run using stdio transport, similar to the weather example
    mcp_server.run(transport='stdio')

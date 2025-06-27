import os
import sys
import logging
import argparse
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP, Context
from mcp.types import ErrorData as Error

# Import scraper components directly
from tview_scraper import TradingViewScraper, TradingViewScraperError

def setup_logging(log_dir=None, log_level='INFO'):
    """Configure logging for the TradingView MCP server."""
    logger = logging.getLogger(__name__)
    
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'tradingview_mcp_server.log')
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(name)s - %(message)s'
        ))
        file_handler.setLevel(getattr(logging, log_level))
        logger.addHandler(file_handler)
        print(f"[LOG_INIT] Logging to file: {log_file} at level {log_level}")
    
    return logger

def validate_environment():
    """Validate required environment variables."""
    session_id = os.getenv("TRADINGVIEW_SESSION_ID")
    session_id_sign = os.getenv("TRADINGVIEW_SESSION_ID_SIGN")
    
    if not session_id or not session_id_sign:
        print("Error: TRADINGVIEW_SESSION_ID and TRADINGVIEW_SESSION_ID_SIGN must be set.")
        print("       Provide them either via environment variables (e.g., in MCP client config)")
        print("       or in a .env file in the project directory for local execution.")
        sys.exit(1)
    
    return session_id, session_id_sign

def get_scraper_config():
    """Get scraper configuration from environment variables."""
    return {
        'headless': os.getenv("MCP_SCRAPER_HEADLESS", "True").lower() == "true",
        'window_width': int(os.getenv("MCP_SCRAPER_WINDOW_WIDTH", "1920")),
        'window_height': int(os.getenv("MCP_SCRAPER_WINDOW_HEIGHT", "1080")),
        'use_save_shortcut': os.getenv("MCP_SCRAPER_USE_SAVE_SHORTCUT", "True").lower() == "true",
        'chart_page_id': os.getenv("MCP_SCRAPER_CHART_PAGE_ID", "")
    }

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="TradingView Chart MCP Server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], 
                       default="stdio", help="Transport mode")
    parser.add_argument("--port", type=int, default=8003, help="Port for HTTP transport")
    parser.add_argument("--host", default="localhost", help="Host for HTTP transport")
    parser.add_argument("--log-dir", type=str, help="Directory for log files")
    parser.add_argument("--log-level", type=str, default="INFO", 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], help="Logging level")
    return parser.parse_args()

# Parse arguments first so we can use them everywhere
args = parse_arguments()

# Initialize components with parsed arguments
logger = setup_logging(args.log_dir, args.log_level)
load_dotenv()

# Validate environment and get credentials  
TRADINGVIEW_SESSION_ID, TRADINGVIEW_SESSION_ID_SIGN = validate_environment()

# Get scraper configuration
config = get_scraper_config()
HEADLESS = config['headless']
WINDOW_WIDTH = config['window_width'] 
WINDOW_HEIGHT = config['window_height']
USE_SAVE_SHORTCUT = config['use_save_shortcut']
CHART_PAGE_ID = config['chart_page_id'] if config['chart_page_id'] else TradingViewScraper.DEFAULT_CHART_PAGE_ID
WINDOW_SIZE = (WINDOW_WIDTH, WINDOW_HEIGHT)

# Create MCP server
mcp_server = FastMCP("TradingView Chart Image")

@mcp_server.tool()
async def get_tradingview_chart_image(ticker: str, interval: str, ctx: Context) -> str:
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
    await ctx.info(f"Attempting to get chart image for {ticker} interval {interval}")
    
    try:
        with TradingViewScraper(
            headless=HEADLESS,
            window_size=f"{WINDOW_WIDTH},{WINDOW_HEIGHT}",
            chart_page_id=CHART_PAGE_ID,
            use_save_shortcut=USE_SAVE_SHORTCUT
        ) as scraper:
            if USE_SAVE_SHORTCUT:
                image_url = scraper.get_chart_image_url(ticker, interval)
                if not image_url:
                    raise TradingViewScraperError("Scraper did not return an image URL.")
            else:
                screenshot_link = scraper.get_screenshot_link(ticker, interval)
                if not screenshot_link:
                    raise TradingViewScraperError("Scraper did not return a screenshot link from clipboard.")
                image_url = scraper.convert_link_to_image_url(screenshot_link)
                if not image_url:
                    raise TradingViewScraperError("Failed to convert screenshot link to image URL.")
            
            await ctx.info(f"Successfully obtained image URL for {ticker} ({interval}): {image_url[:100]}{'...' if len(image_url) > 100 else ''}")
            return image_url
            
    except TradingViewScraperError as e:
        await ctx.error(f"Scraper Error: {e}")
        raise Exception(f"Scraper Error: {e}")
    except ValueError as e:
        await ctx.error(f"Input Error: {e}")
        raise Exception(f"Input Error: {e}")
    except Exception as e:
        await ctx.error(f"Unexpected error in get_tradingview_chart_image: {e}")
        raise Exception(f"Unexpected error: {e}")

@mcp_server.prompt("Get the {interval} minute chart for {ticker}")
async def get_chart_prompt_minutes(ticker: str, interval: str, ctx: Context):
    await ctx.info(f"Executing prompt: Get the {interval} minute chart for {ticker}")
    return await get_tradingview_chart_image(ticker=ticker, interval=interval, ctx=ctx)

@mcp_server.prompt("Show me the daily chart for {ticker}")
async def get_chart_prompt_daily(ticker: str, ctx: Context):
    await ctx.info(f"Executing prompt: Show me the daily chart for {ticker}")
    return await get_tradingview_chart_image(ticker=ticker, interval='D', ctx=ctx)

@mcp_server.prompt("Fetch TradingView chart image for {ticker} on the {interval} timeframe")
async def get_chart_prompt_timeframe(ticker: str, interval: str, ctx: Context):
    await ctx.info(f"Executing prompt: Fetch TradingView chart image for {ticker} on the {interval} timeframe")
    interval_map = {
        "daily": "D", "weekly": "W", "monthly": "M",
        "1 minute": "1", "5 minute": "5", "15 minute": "15",
        "1 hour": "60", "4 hour": "240",
    }
    mcp_interval = interval_map.get(interval.lower(), interval)
    await ctx.info(f"Mapped interval '{interval}' to '{mcp_interval}'")
    return await get_tradingview_chart_image(ticker=ticker, interval=mcp_interval, ctx=ctx)

if __name__ == "__main__":
    if os.getenv("MCP_DEBUG_STARTUP", "false").lower() == "true":
        logger.info("🚀 Starting TradingView Chart Image MCP Server...")
        logger.info(f"⚙️ Configuration:")
        logger.info(f"   - Transport mode: {args.transport}")
        logger.info(f"   - Headless: {HEADLESS}")
        logger.info(f"   - Window Size: {WINDOW_SIZE}")
        logger.info(f"   - Use Save Shortcut: {USE_SAVE_SHORTCUT}")
        if args.transport == "streamable-http":
            logger.info(f"   - HTTP Server: {args.host}:{args.port}")
    
    if args.transport == "streamable-http":
        logger.info(f"Starting TradingView MCP server on {args.host}:{args.port}")
        mcp_server.settings.host = args.host
        mcp_server.settings.port = args.port
        mcp_server.run(transport='streamable-http')
    else:
        mcp_server.run(transport='stdio')

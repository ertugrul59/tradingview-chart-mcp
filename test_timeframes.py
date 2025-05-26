#!/usr/bin/env python3

import os
import sys
import logging
import time
from dotenv import load_dotenv
import argparse

# Add current directory to path to import the scraper
sys.path.insert(0, os.path.dirname(__file__))

import importlib.util
import sys
import os

# Load the scraper module dynamically (same as main.py)
scraper_path = os.path.join(os.path.dirname(__file__), 'tview-scraper.py')
spec = importlib.util.spec_from_file_location("tview_scraper", scraper_path)
scraper_module = importlib.util.module_from_spec(spec)
sys.modules["tview_scraper"] = scraper_module
spec.loader.exec_module(scraper_module)

TradingViewScraper = getattr(scraper_module, 'TradingViewScraper')
TradingViewScraperError = getattr(scraper_module, 'TradingViewScraperError')

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_timeframes(headless=True, use_save_shortcut=False):
    """Test different timeframes to see which ones work.
    
    Note: The save shortcut method (Shift+Ctrl/Cmd+S) works well for TradingView in both headless 
    and non-headless modes, providing direct base64 image data URLs instead of HTTP URLs.
    """
    
    ticker = "BYBIT:BTCUSDT.P"
    # Test timeframes from TradingView: '1', '5', '15', '30', '60', '240', 'D', 'W', 'M'
    timeframes_to_test = [
        # None,    # Default (would use scraper default)
        '1',     # 1 minute
        '5',     # 5 minutes
        '15',    # 15 minutes
        '30',    # 30 minutes
        '60',    # 1 hour
        '240',   # 4 hours
        'D',     # Daily
        'W',     # Weekly
        # 'M',     # Monthly (uncomment if supported)
    ]
    
    results = {}
    
    for timeframe in timeframes_to_test:
        timeframe_str = timeframe or "default"
        logger.info(f"\n{'='*50}")
        logger.info(f"Testing timeframe: {timeframe_str}")
        logger.info(f"{'='*50}")
        
        try:
            with TradingViewScraper(headless=headless, use_save_shortcut=use_save_shortcut) as scraper:
                if use_save_shortcut:
                    # Use the new direct image capture method
                    image_url = scraper.get_chart_image_url(
                        ticker=ticker,
                        interval=timeframe
                    )
                else:
                    # Use the traditional screenshot link method
                    screenshot_link = scraper.get_screenshot_link(
                        ticker=ticker,
                        interval=timeframe
                    )
                    if screenshot_link:
                        image_url = scraper.convert_link_to_image_url(screenshot_link)
                    else:
                        image_url = None
                
                if image_url and (image_url.startswith("https://s3.tradingview.com/snapshots/") or image_url.startswith("data:image/")):
                    results[timeframe_str] = {"status": "SUCCESS", "url": image_url[:100] + "..." if len(image_url) > 100 else image_url}
                    logger.info(f"✅ SUCCESS for {timeframe_str}: {image_url[:100]}{'...' if len(image_url) > 100 else ''}")
                else:
                    results[timeframe_str] = {"status": "FAILED", "url": image_url}
                    logger.error(f"❌ FAILED for {timeframe_str}: {image_url}")
                    
        except TradingViewScraperError as e:
            results[timeframe_str] = {"status": "ERROR", "error": str(e)}
            logger.error(f"❌ ERROR for {timeframe_str}: {e}")
        except Exception as e:
            results[timeframe_str] = {"status": "UNEXPECTED_ERROR", "error": str(e)}
            logger.error(f"❌ UNEXPECTED ERROR for {timeframe_str}: {e}")
        
        # Small delay between tests
        time.sleep(2)
    
    # Print summary
    logger.info(f"\n{'='*50}")
    logger.info("SUMMARY OF RESULTS")
    logger.info(f"{'='*50}")
    
    for timeframe_str, result in results.items():
        status = result["status"]
        if status == "SUCCESS":
            logger.info(f"✅ {timeframe_str}: {status}")
        else:
            logger.error(f"❌ {timeframe_str}: {status} - {result.get('error', result.get('url', 'Unknown'))}")
    
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test TradingView timeframes with optional headless and save shortcut flags.")
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode (default: False)')
    parser.add_argument('--use-save-shortcut', action='store_true', help='Use Shift+Ctrl/Command+S instead of Alt+S')
    args = parser.parse_args()

    # Check for required credentials
    tv_session_id = os.getenv("TRADINGVIEW_SESSION_ID")
    tv_session_id_sign = os.getenv("TRADINGVIEW_SESSION_ID_SIGN")
    
    if not tv_session_id or not tv_session_id_sign:
        logger.error("TRADINGVIEW_SESSION_ID and TRADINGVIEW_SESSION_ID_SIGN environment variables must be set!")
        sys.exit(1)
    
    logger.info(f"TRADINGVIEW_SESSION_ID is set (length: {len(tv_session_id)})")
    logger.info(f"TRADINGVIEW_SESSION_ID_SIGN is set (length: {len(tv_session_id_sign)})")
    logger.info(f"Using save shortcut: {args.use_save_shortcut}")
    
    results = test_timeframes(headless=args.headless, use_save_shortcut=args.use_save_shortcut)
    logger.info("Testing completed!") 
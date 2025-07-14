#!/usr/bin/env python3
"""
Test TradingView MCP Performance Using Agent's MultiServerMCPClient
==================================================================

This script tests the optimized TradingView MCP server using the exact same
MultiServerMCPClient approach that the agent uses. This gives us realistic
performance measurements that match real agent usage.

Supports both sequential and concurrent testing modes to evaluate performance
under different load scenarios.

Usage:
    # Sequential testing (default)
    python test_mcp_agent_style.py --runs 5 --ticker BYBIT:BTCUSDT.P --interval 240

    # Concurrent testing (test server under load)
    python test_mcp_agent_style.py --concurrent 3 --ticker BYBIT:BTCUSDT.P --interval 240

    # Test different symbols and timeframes
    python test_mcp_agent_style.py --concurrent 4 --ticker NASDAQ:AAPL --interval 15

    # Test daily charts
    python test_mcp_agent_style.py --concurrent 4 --ticker BYBIT:ETHUSDT.P --interval D

Note: TradingView requires proper authentication to work.
"""

import asyncio
import time
import statistics
import argparse
import sys
import os
import warnings
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

# Suppress Windows asyncio cleanup warnings
if sys.platform == "win32":
    warnings.filterwarnings(
        "ignore", category=RuntimeWarning, message=".*Event loop is closed.*"
    )
    warnings.filterwarnings(
        "ignore", category=RuntimeWarning, message=".*coroutine.*was never awaited.*"
    )

# Add the project root to Python path so we can import from src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from src.core.config import create_mcp_client_config
except ImportError as e:
    print(f"❌ Import error: {e}")
    print(
        "   Make sure you're running from the project root with the virtual environment activated"
    )
    print("   and langchain-mcp-adapters is installed.")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TradingViewMCPAgentStyleTester:
    """Test TradingView MCP performance using the agent's exact approach"""

    def __init__(self):
        self.mcp_client = None
        self.mcp_tools = {}

    async def initialize_mcp_client(self) -> bool:
        """Initialize MCP client exactly like the agent does"""
        try:
            logger.info("🔥 Creating MCP client using agent's configuration...")

            # Get the exact same config the agent uses
            mcp_config = create_mcp_client_config()

            # Filter to only TradingView for testing
            tradingview_config = {
                "tradingview-chart-mcp": mcp_config["tradingview-chart-mcp"]
            }

            logger.info("📊 MCP Config for TradingView:")
            for key, value in tradingview_config["tradingview-chart-mcp"].items():
                if key == "env":
                    logger.info(f"   {key}: {list(value.keys())}")
                else:
                    logger.info(f"   {key}: {value}")

            # Create client with the same config as agent
            self.mcp_client = MultiServerMCPClient(tradingview_config)

            # Get tools like the agent does
            tools_list = await self.mcp_client.get_tools()
            self.mcp_tools = {tool.name: tool for tool in tools_list}

            logger.info("✅ MCP client initialized successfully!")
            logger.info(f"🔧 Available tools: {list(self.mcp_tools.keys())}")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize MCP client: {e}")
            return False

    async def test_single_chart(
        self, ticker: str, interval: str = "240"
    ) -> Dict[str, Any]:
        """Test single chart capture performance using agent's method"""
        if "get_tradingview_chart_image" not in self.mcp_tools:
            raise Exception("get_tradingview_chart_image tool not available")

        tool = self.mcp_tools["get_tradingview_chart_image"]
        logger.info(f"📊 Testing chart capture: {ticker} ({interval})")

        start_time = time.time()

        try:
            # Call tool exactly like the agent does
            result = await tool.ainvoke({"ticker": ticker, "interval": interval})

            end_time = time.time()
            duration = end_time - start_time

            # Parse result to check success and image size
            success = True
            image_size = 0
            error = None

            if isinstance(result, str):
                if result.startswith("data:image/"):
                    # Base64 image data
                    base64_part = result.split(",", 1)[1] if "," in result else ""
                    image_size = len(base64_part)
                elif result.startswith("https://s3.tradingview.com/snapshots/"):
                    # TradingView snapshot URL
                    image_size = len(result)  # URL length as proxy
                elif result.startswith("Error") or "failed" in result.lower():
                    success = False
                    error = result
            elif isinstance(result, dict):
                if "error" in result:
                    success = False
                    error = str(result.get("error"))
                elif "image_url" in result:
                    image_url = result["image_url"]
                    if image_url.startswith("data:image/"):
                        base64_part = (
                            image_url.split(",", 1)[1] if "," in image_url else ""
                        )
                        image_size = len(base64_part)
                    elif image_url.startswith("https://s3.tradingview.com/snapshots/"):
                        image_size = len(image_url)

            test_result = {
                "ticker": ticker,
                "interval": interval,
                "success": success,
                "duration": duration,
                "image_size": image_size,
                "has_image": image_size > 0,
                "timestamp": datetime.now().isoformat(),
                "error": error,
                "result_type": type(result).__name__,
                "result_preview": str(result)[:100]
                + ("..." if len(str(result)) > 100 else ""),
            }

            if success:
                logger.info(
                    f"✅ {ticker} ({interval}): {duration:.2f}s, {image_size:,} chars/bytes"
                )
            else:
                logger.error(f"❌ {ticker} ({interval}): Failed - {error}")

            return test_result

        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time

            logger.error(f"❌ {ticker} ({interval}): Exception - {e}")

            return {
                "ticker": ticker,
                "interval": interval,
                "success": False,
                "duration": duration,
                "image_size": 0,
                "has_image": False,
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "result_type": "Exception",
                "result_preview": str(e)[:100],
            }

    async def run_performance_test(
        self, ticker: str, interval: str, runs: int
    ) -> Dict[str, Any]:
        """Run multiple performance tests and calculate statistics"""
        logger.info(
            f"🚀 Starting agent-style performance test: {runs} runs of {ticker} ({interval})"
        )

        if not await self.initialize_mcp_client():
            raise Exception("Failed to initialize MCP client")

        results = []
        successful_results = []

        for i in range(runs):
            logger.info(f"📊 Run {i+1}/{runs}")
            result = await self.test_single_chart(ticker, interval)
            results.append(result)

            if result["success"]:
                successful_results.append(result)

            # Brief pause between runs
            if i < runs - 1:
                await asyncio.sleep(1)

        # Calculate statistics
        if successful_results:
            durations = [r["duration"] for r in successful_results]
            image_sizes = [r["image_size"] for r in successful_results]

            stats = {
                "ticker": ticker,
                "interval": interval,
                "total_runs": runs,
                "successful_runs": len(successful_results),
                "failed_runs": runs - len(successful_results),
                "success_rate": len(successful_results) / runs * 100,
                # Duration statistics
                "avg_duration": statistics.mean(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
                "median_duration": statistics.median(durations),
                "std_duration": (
                    statistics.stdev(durations) if len(durations) > 1 else 0
                ),
                # Image statistics
                "avg_image_size": statistics.mean(image_sizes) if image_sizes else 0,
                "min_image_size": min(image_sizes) if image_sizes else 0,
                "max_image_size": max(image_sizes) if image_sizes else 0,
                # Raw results
                "raw_results": results,
            }
        else:
            stats = {
                "ticker": ticker,
                "interval": interval,
                "total_runs": runs,
                "successful_runs": 0,
                "failed_runs": runs,
                "success_rate": 0,
                "error": "All runs failed",
                "raw_results": results,
            }

        return stats

    async def run_concurrent_test(
        self, ticker: str, interval: str, concurrent_requests: int
    ) -> Dict[str, Any]:
        """Run concurrent requests to test server performance under load"""
        logger.info(
            f"🚀 Starting concurrent test: {concurrent_requests} simultaneous requests for {ticker} ({interval})"
        )

        if not await self.initialize_mcp_client():
            raise Exception("Failed to initialize MCP client")

        # Create multiple tasks to run concurrently
        start_time = time.time()

        # Create tasks for concurrent execution
        tasks = []
        for i in range(concurrent_requests):
            task = self.test_single_chart(ticker, interval)
            tasks.append(task)

        logger.info(f"🔥 Launching {concurrent_requests} concurrent requests...")

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()
        total_duration = end_time - start_time

        # Process results
        successful_results = []
        failed_results = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_results.append(
                    {
                        "request_id": i + 1,
                        "success": False,
                        "error": str(result),
                        "duration": 0,
                    }
                )
            elif isinstance(result, dict) and result.get("success", False):
                result["request_id"] = i + 1
                successful_results.append(result)
            else:
                result["request_id"] = i + 1
                failed_results.append(result)

        # Calculate statistics
        if successful_results:
            durations = [r["duration"] for r in successful_results]
            image_sizes = [
                r["image_size"]
                for r in successful_results
                if r.get("image_size", 0) > 0
            ]

            stats = {
                "test_type": "concurrent",
                "ticker": ticker,
                "interval": interval,
                "concurrent_requests": concurrent_requests,
                "total_duration": total_duration,
                "successful_requests": len(successful_results),
                "failed_requests": len(failed_results),
                "success_rate": len(successful_results) / concurrent_requests * 100,
                # Duration statistics
                "avg_request_duration": statistics.mean(durations),
                "min_request_duration": min(durations),
                "max_request_duration": max(durations),
                "median_request_duration": statistics.median(durations),
                "std_request_duration": (
                    statistics.stdev(durations) if len(durations) > 1 else 0
                ),
                # Throughput metrics
                "requests_per_second": concurrent_requests / total_duration,
                "avg_throughput": len(successful_results) / total_duration,
                # Image statistics
                "avg_image_size": statistics.mean(image_sizes) if image_sizes else 0,
                "min_image_size": min(image_sizes) if image_sizes else 0,
                "max_image_size": max(image_sizes) if image_sizes else 0,
                # Raw results
                "successful_results": successful_results,
                "failed_results": failed_results,
            }
        else:
            stats = {
                "test_type": "concurrent",
                "ticker": ticker,
                "interval": interval,
                "concurrent_requests": concurrent_requests,
                "total_duration": total_duration,
                "successful_requests": 0,
                "failed_requests": len(failed_results),
                "success_rate": 0,
                "error": "All concurrent requests failed",
                "failed_results": failed_results,
            }

        return stats

    async def cleanup(self):
        """Clean up MCP client resources"""
        if self.mcp_client:
            try:
                logger.info("🧹 Cleaning up MCP client...")
                # Use the proper aclose method for async cleanup
                if hasattr(self.mcp_client, "aclose"):
                    await self.mcp_client.aclose()
                elif hasattr(self.mcp_client, "close"):
                    self.mcp_client.close()

                self.mcp_client = None
                self.mcp_tools = {}

                # Give asyncio a moment to clean up properly
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.warning(f"⚠️ Error during cleanup: {e}")

        # Simplified cleanup - don't try to cancel tasks as it can cause recursion issues
        logger.info("🧹 MCP client cleanup completed")


def print_performance_report(stats: Dict[str, Any]):
    """Print detailed performance report"""
    print("\n" + "=" * 80)
    print("🚀 AGENT-STYLE TRADINGVIEW MCP PERFORMANCE REPORT (BROWSER POOLING)")
    print("=" * 80)

    if stats["successful_runs"] == 0:
        print(f"❌ All {stats['total_runs']} runs failed!")
        print(f"Error: {stats.get('error', 'Unknown error')}")
        if stats.get("raw_results"):
            print("\n📊 Failed Results:")
            for i, result in enumerate(stats["raw_results"], 1):
                print(f"   Run {i}: {result.get('error', 'Unknown error')}")
        return

    print(f"📊 Test Configuration:")
    print(f"   Ticker: {stats['ticker']}")
    print(f"   Interval: {stats['interval']}")
    print(f"   Total Runs: {stats['total_runs']}")
    print(f"   Successful: {stats['successful_runs']}")
    print(f"   Success Rate: {stats['success_rate']:.1f}%")

    print(f"\n⏱️ Performance Statistics:")
    print(f"   Average Duration: {stats['avg_duration']:.2f}s")
    print(f"   Median Duration:  {stats['median_duration']:.2f}s")
    print(f"   Min Duration:     {stats['min_duration']:.2f}s")
    print(f"   Max Duration:     {stats['max_duration']:.2f}s")
    print(f"   Std Deviation:    {stats['std_duration']:.2f}s")

    print(f"\n📦 Image Statistics:")
    if stats["avg_image_size"] > 0:
        if stats["avg_image_size"] > 10000:  # Likely base64 data
            print(
                f"   Average Size: {stats['avg_image_size']:,.0f} chars ({stats['avg_image_size']/1024:.1f} KB base64)"
            )
        else:  # Likely URL length
            print(f"   Average Size: {stats['avg_image_size']:,.0f} chars (URL length)")
        print(
            f"   Size Range:   {stats['min_image_size']:,} - {stats['max_image_size']:,} chars"
        )
    else:
        print("   No image data captured")

    # Performance rating based on optimization goals
    avg_duration = stats["avg_duration"]
    if avg_duration < 4:
        rating = "🟢 EXCELLENT (Browser pooling optimized)"
    elif avg_duration < 6:
        rating = "🟡 GOOD (Minor improvements possible)"
    elif avg_duration < 8:
        rating = "🟠 ACCEPTABLE (Needs optimization)"
    else:
        rating = "🔴 NEEDS IMPROVEMENT (Pooling not working?)"

    print(f"\n📈 Performance Rating: {rating}")

    # Compare to our target
    print(f"\n🎯 Browser Pooling Optimization Status:")
    if avg_duration <= 6.0:
        print("   ✅ Meeting browser pooling optimization targets!")
    else:
        print("   ⚠️ Below target - check browser pooling configuration")

    print("=" * 80)


def print_concurrent_report(stats: Dict[str, Any]):
    """Print detailed concurrent performance report"""
    print("\n" + "=" * 80)
    print("🚀 CONCURRENT TRADINGVIEW MCP PERFORMANCE REPORT (BROWSER POOLING)")
    print("=" * 80)

    if stats["successful_requests"] == 0:
        print(f"❌ All {stats['concurrent_requests']} concurrent requests failed!")
        print(f"Total Duration: {stats['total_duration']:.2f}s")
        if stats.get("failed_results"):
            print("\n📊 Failed Results:")
            for result in stats["failed_results"][:5]:  # Show first 5 failures
                print(
                    f"   Request {result.get('request_id', '?')}: {result.get('error', 'Unknown error')}"
                )
        return

    print(f"📊 Test Configuration:")
    print(f"   Ticker: {stats['ticker']}")
    print(f"   Interval: {stats['interval']}")
    print(f"   Concurrent Requests: {stats['concurrent_requests']}")
    print(f"   Successful Requests: {stats['successful_requests']}")
    print(f"   Failed Requests: {stats['failed_requests']}")
    print(f"   Success Rate: {stats['success_rate']:.1f}%")

    print(f"\n⏱️ Timing Statistics:")
    print(f"   Total Duration: {stats['total_duration']:.2f}s")
    print(f"   Avg Request Duration: {stats['avg_request_duration']:.2f}s")
    print(f"   Min Request Duration: {stats['min_request_duration']:.2f}s")
    print(f"   Max Request Duration: {stats['max_request_duration']:.2f}s")
    print(f"   Std Deviation: {stats['std_request_duration']:.2f}s")

    print(f"\n🚀 Throughput Metrics:")
    print(f"   Requests per Second: {stats['requests_per_second']:.2f} req/s")
    print(f"   Successful Throughput: {stats['avg_throughput']:.2f} req/s")
    if stats["concurrent_requests"] > 1:
        speedup = (
            stats["concurrent_requests"]
            / stats["total_duration"]
            * stats["avg_request_duration"]
        )
        print(f"   Parallel Efficiency: {speedup:.1f}x")

    print(f"\n📦 Image Statistics:")
    if stats["avg_image_size"] > 0:
        if stats["avg_image_size"] > 10000:  # Likely base64 data
            print(
                f"   Average Size: {stats['avg_image_size']:,.0f} chars ({stats['avg_image_size']/1024:.1f} KB base64)"
            )
        else:  # Likely URL length
            print(f"   Average Size: {stats['avg_image_size']:,.0f} chars (URL length)")
        print(
            f"   Size Range: {stats['min_image_size']:,} - {stats['max_image_size']:,} chars"
        )
    else:
        print("   No image data captured")

    # Performance rating for concurrent requests
    avg_duration = stats["avg_request_duration"]
    success_rate = stats["success_rate"]

    if success_rate == 100 and avg_duration < 5:
        rating = "🟢 EXCELLENT (Great concurrent performance)"
    elif success_rate >= 90 and avg_duration < 7:
        rating = "🟡 GOOD (Minor issues under load)"
    elif success_rate >= 75:
        rating = "🟠 ACCEPTABLE (Some degradation under load)"
    else:
        rating = "🔴 NEEDS IMPROVEMENT (Poor concurrent handling)"

    print(f"\n📈 Concurrent Performance Rating: {rating}")

    # Compare to sequential performance
    print(f"\n🎯 Concurrent Analysis:")
    if stats["success_rate"] == 100:
        print("   ✅ Perfect reliability under concurrent load!")
    elif stats["success_rate"] >= 90:
        print("   ⚠️ Minor reliability issues under load")
    else:
        print("   ❌ Significant issues handling concurrent requests")

    print("=" * 80)


async def main():
    parser = argparse.ArgumentParser(
        description="Test TradingView MCP Performance using Agent Style"
    )
    parser.add_argument(
        "--ticker", default="BYBIT:BTCUSDT.P", help="Ticker symbol to test"
    )
    parser.add_argument(
        "--interval", default="240", help="Chart interval (240, 15, D, etc.)"
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Number of test runs (for sequential testing)",
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        help="Number of concurrent requests (enables concurrent mode)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    tester = TradingViewMCPAgentStyleTester()

    try:
        if args.concurrent:
            # Run concurrent test
            stats = await tester.run_concurrent_test(
                args.ticker, args.interval, args.concurrent
            )
            print_concurrent_report(stats)

            # Save results to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tradingview_concurrent_performance_test_{timestamp}.json"

            import json

            with open(filename, "w") as f:
                json.dump(stats, f, indent=2, default=str)

            print(f"\n💾 Detailed results saved to: {filename}")

            # Quick analysis for concurrent tests
            if stats["successful_requests"] > 0:
                avg_time = stats["avg_request_duration"]
                throughput = stats["avg_throughput"]
                print(f"\n🔍 Concurrent Analysis:")
                print(f"   Avg Request Time: {avg_time:.2f}s")
                print(f"   Throughput: {throughput:.2f} req/s")
                print(f"   Success Rate: {stats['success_rate']:.1f}%")

                if stats["success_rate"] == 100:
                    print("   🎉 Perfect concurrent performance!")
                elif stats["success_rate"] >= 90:
                    print("   ✅ Very good concurrent handling")
                else:
                    print("   ⚠️ Consider reducing concurrent load")
        else:
            # Run sequential test
            stats = await tester.run_performance_test(
                args.ticker, args.interval, args.runs
            )
            print_performance_report(stats)

            # Save results to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tradingview_agent_style_performance_test_{timestamp}.json"

            import json

            with open(filename, "w") as f:
                json.dump(stats, f, indent=2, default=str)

            print(f"\n💾 Detailed results saved to: {filename}")

            # Quick comparison with our targets
            if stats["successful_runs"] > 0:
                avg_time = stats["avg_duration"]
                print(f"\n🔍 Quick Analysis:")
                print(f"   Current: {avg_time:.2f}s average")
                print(f"   Target:  <6.0s (Browser pooling optimized)")

                if avg_time <= 6.0:
                    print("   🎉 Browser pooling optimization is working well!")
                else:
                    print("   📝 Consider checking browser pooling configuration")

    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        sys.exit(1)
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    # Better asyncio handling for Windows
    if sys.platform == "win32":
        # Use SelectorEventLoop on Windows to avoid ProactorEventLoop issues
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Use a more robust asyncio pattern for Windows
    loop = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        sys.exit(1)
    finally:
        if loop:
            try:
                # Cancel all pending tasks properly
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()

                # Wait for cancellation to complete
                if pending:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )

                # Close the loop properly
                loop.close()
            except Exception as e:
                logger.warning(f"⚠️ Error during final cleanup: {e}")
                # Force close
                if loop and not loop.is_closed():
                    loop.close()

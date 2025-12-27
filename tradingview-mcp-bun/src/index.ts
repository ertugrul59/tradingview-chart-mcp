import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { TradingViewScraper } from "./scraper.js";

// Initialize Scraper
const scraper = new TradingViewScraper();

// Connect to browser instance on startup
// Note: In a real server, we might want to lazy load or handle reconnection
console.error("Starting TradingView MCP Server..."); // Stderr for logs, Stdout for MCP transport

try {
    await scraper.init();
    console.error("Browser initialized successfully.");
} catch (error) {
    console.error("Failed to initialize browser:", error);
    process.exit(1);
}

// Create MCP Server
const server = new McpServer({
    name: "tradingview-chart-mcp",
    version: "1.0.0",
});

// Initialize Stats
let requestCount = 0;
const startTime = Date.now();

server.registerTool(
    "get_chart_image",
    {
        inputSchema: {
            ticker: z.string().describe("The TradingView ticker symbol (e.g. BYBIT:BTCUSDT.P, NASDAQ:AAPL)"),
            interval: z.string().describe("The chart time interval (e.g. 1, 5, 15, 60, 240, D, W)"),
        }
    },
    async ({ ticker, interval }) => {
        try {
            requestCount++;
            console.error(`Received request: ${ticker} on ${interval}`);
            const base64Image = await scraper.getChartImage(ticker, interval);

            return {
                content: [
                    {
                        type: "image",
                        data: base64Image,
                        mimeType: "image/png",
                    },
                ],
            };
        } catch (err: any) {
            console.error(`Error processing request: ${err.message}`);
            return {
                content: [
                    {
                        type: "text",
                        text: `Failed to get chart: ${err.message}`,
                    },
                ],
                isError: true,
            };
        }
    }
);

server.registerTool(
    "get_performance_stats",
    {},
    async () => {
        const uptime = Math.floor((Date.now() - startTime) / 1000);
        return {
            content: [{
                type: "text",
                text: `🚀 Bun TradingView MCP Stats\n• Requests Processed: ${requestCount}\n• Uptime: ${uptime}s\n• Engine: Playwright (Bun)\n• Status: Healthy`
            }]
        };
    }
);

// Graceful cleanup
process.on("SIGINT", async () => {
    console.error("Shutting down...");
    await scraper.close();
    process.exit(0);
});

// Start Transport
const transport = new StdioServerTransport();
await server.connect(transport);
console.error("MCP Server running on stdio transport.");

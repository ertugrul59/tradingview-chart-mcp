# MCP Server - TradingView Chart Image Scraper

[![smithery badge](https://smithery.ai/badge/@ertugrul59/tradingview-chart-mcp)](https://smithery.ai/server/@ertugrul59/tradingview-chart-mcp)

This MCP server provides tools to fetch TradingView chart images based on ticker and interval.

## Setup

1.  **Create Virtual Environment:**
    ```bash
    # Navigate to the project directory
    cd tradingview-chart-mcp
    # Create the venv (use python3 if python is not linked)
    python3 -m venv .venv
    ```
2.  **Activate Virtual Environment:**

    - **macOS/Linux:**
      ```bash
      source .venv/bin/activate
      ```
    - **Windows (Git Bash/WSL):**
      ```bash
      source .venv/Scripts/activate
      ```
    - **Windows (Command Prompt):**
      ```bash
      .venv\\Scripts\\activate.bat
      ```
    - **Windows (PowerShell):**
      ```bash
      .venv\\Scripts\\Activate.ps1
      ```
      _(Note: You might need to adjust PowerShell execution policy: `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`)_

    Your terminal prompt should now indicate you are in the `(.venv)`.

3.  **Install Dependencies (inside venv):**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure Environment (for Local Testing):**
    - Copy `.env.example` to `.env`.
    - Fill in your `TRADINGVIEW_SESSION_ID` and `TRADINGVIEW_SESSION_ID_SIGN` in the `.env` file. You can obtain these from your browser's cookies after logging into TradingView.
    - This `.env` file is used when running the server directly (e.g., `python main.py`) for local testing.
    - Adjust optional scraper settings (`MCP_SCRAPER_HEADLESS`, etc.) in `.env` if needed for local runs.
5.  **Ensure ChromeDriver:** Make sure `chromedriver` is installed and accessible in your system's PATH, or configure the `tview-scraper.py` accordingly if it allows specifying a path.

## Running the Server

Ensure your virtual environment is activated (`source .venv/bin/activate` or equivalent).

```bash
python main.py
```

## Deactivating the Virtual Environment

When you are finished, you can deactivate the environment:

```bash
deactivate
```

## Usage

Once the server is running (within the activated venv), you can interact with it using an MCP client, targeting the `TradingView Chart Image` server name.

**Available Tools:**

- `get_tradingview_chart_image(ticker: str, interval: str)`: Fetches the direct image URL for a TradingView chart.

**Example Prompts:**

- "Get the 15 minute chart for NASDAQ:AAPL"
- "Show me the daily chart for BYBIT:BTCUSDT.P"
- "Fetch TradingView chart image for COINBASE:ETHUSD on the 60 timeframe"

## 🔌 Using with MCP Clients (Claude Desktop / Cursor)

This server supports two ways of providing configuration:

1.  **Via `.env` file (for local testing):** When running `python main.py` directly, the server will load credentials and settings from a `.env` file in the project directory.
2.  **Via Client Environment Variables (Recommended for Integration):** When run by an MCP client (like Claude/Cursor), you should configure the client to inject the required environment variables directly. **These will override any values found in a `.env` file.**

### Claude Desktop

1.  Open your Claude Desktop configuration file:
    - **Windows:** `%APPDATA%\\Claude\\claude_desktop_config.json`
    - **macOS:** `~/Library/Application\ Support/Claude/claude_desktop_config.json`
2.  Add or merge the following within the `mcpServers` object. Provide your credentials in the `env` block:

    ```json
    {
      "mcpServers": {
        "tradingview-chart-mcp": {
          "command": "/absolute/path/to/your/tradingview-chart-mcp/.venv/bin/python3",
          "args": ["/absolute/path/to/your/tradingview-chart-mcp/main.py"],
          "env": {
            "TRADINGVIEW_SESSION_ID": "YOUR_SESSION_ID_HERE",
            "TRADINGVIEW_SESSION_ID_SIGN": "YOUR_SESSION_ID_SIGN_HERE"
            // Optional: Add MCP_SCRAPER_* variables here too if needed
            // "MCP_SCRAPER_HEADLESS": "False"
          }
        }
        // ... other servers if any ...
      }
    }
    ```

3.  Replace the placeholder paths (`command`, `args`) with your actual absolute paths.
4.  Replace `YOUR_SESSION_ID_HERE` and `YOUR_SESSION_ID_SIGN_HERE` with your actual TradingView credentials.
5.  Restart Claude Desktop.

### Cursor

1.  Go to: `Settings -> Cursor Settings -> MCP -> Edit User MCP Config (~/.cursor/mcp.json)`.
2.  Add or merge the following within the `mcpServers` object. Provide your credentials in the `env` block:

    ```json
    {
      "mcpServers": {
        "tradingview-chart-mcp": {
          "command": "/absolute/path/to/your/tradingview-chart-mcp/.venv/bin/python3",
          "args": ["/absolute/path/to/your/tradingview-chart-mcp/main.py"],
          "env": {
            "TRADINGVIEW_SESSION_ID": "YOUR_SESSION_ID_HERE",
            "TRADINGVIEW_SESSION_ID_SIGN": "YOUR_SESSION_ID_SIGN_HERE"
            // Optional: Add MCP_SCRAPER_* variables here too if needed
            // "MCP_SCRAPER_HEADLESS": "False"
          }
        }
        // ... other servers if any ...
      }
    }
    ```

3.  Replace the placeholder paths (`command`, `args`) with your actual absolute paths.
4.  Replace `YOUR_SESSION_ID_HERE` and `YOUR_SESSION_ID_SIGN_HERE` with your actual TradingView credentials.
5.  Restart Cursor.

### Installing via Smithery

To install TradingView Chart Image Scraper for Claude Desktop automatically via [Smithery](https://smithery.ai/server/@ertugrul59/tradingview-chart-mcp):

```bash
npx -y @smithery/cli install @ertugrul59/tradingview-chart-mcp --client claude
```

## Configuration

### Environment Variables

The following environment variables can be set to configure the scraper:

- `TRADINGVIEW_SESSION_ID`: Your TradingView session ID (required)
- `TRADINGVIEW_SESSION_ID_SIGN`: Your TradingView session ID signature (required)
- `MCP_SCRAPER_HEADLESS`: Run browser in headless mode (default: `True`)
- `MCP_SCRAPER_WINDOW_WIDTH`: Browser window width (default: `1920`)
- `MCP_SCRAPER_WINDOW_HEIGHT`: Browser window height (default: `1080`)
- `MCP_SCRAPER_USE_SAVE_SHORTCUT`: Use clipboard image capture instead of screenshot links (default: `True`)
- `MCP_SCRAPER_CHART_PAGE_ID`: Custom chart page ID (optional)

### Save Shortcut Feature

The `MCP_SCRAPER_USE_SAVE_SHORTCUT` feature allows you to capture chart images directly to the clipboard as base64 data URLs instead of getting screenshot links. This eliminates the need to download images from URLs.

**Benefits:**

- Faster chart capture (no HTTP requests needed)
- More reliable (no dependency on TradingView's CDN)
- Works offline once the chart is loaded
- Direct base64 data URLs for immediate use

**How it works:**

- When enabled (`True`): Uses `Shift+Ctrl+S` (or `Shift+Cmd+S` on Mac) to capture chart image directly to clipboard
- When disabled (`False`): Uses traditional `Alt+S` to get screenshot links, then converts to image URLs

**Configuration:**

```bash
# Enable clipboard image capture (DEFAULT)
MCP_SCRAPER_USE_SAVE_SHORTCUT=True

# Disable and use traditional screenshot links
MCP_SCRAPER_USE_SAVE_SHORTCUT=False
```

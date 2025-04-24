# MCP Server - TradingView Chart Image Scraper

This MCP server provides tools to fetch TradingView chart images based on ticker and interval.

## Setup

1.  **Create Virtual Environment:**
    ```bash
    # Navigate to the project directory
    cd tradingview-chart-mcp
    # Create the venv (use python3 if python is not linked)
    python3 -m venv venv
    ```
2.  **Activate Virtual Environment:**

    - **macOS/Linux:**
      ```bash
      source venv/bin/activate
      ```
    - **Windows (Git Bash/WSL):**
      ```bash
      source venv/Scripts/activate
      ```
    - **Windows (Command Prompt):**
      ```bash
      venv\Scripts\activate.bat
      ```
    - **Windows (PowerShell):**
      ```bash
      venv\Scripts\Activate.ps1
      ```
      _(Note: You might need to adjust PowerShell execution policy: `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`)_

    Your terminal prompt should now indicate you are in the `(venv)`.

3.  **Install Dependencies (inside venv):**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure Environment:**
    - Copy `.env.example` to `.env`.
    - Fill in your `TRADINGVIEW_SESSION_ID` and `TRADINGVIEW_SESSION_ID_SIGN` in the `.env` file. You can obtain these from your browser's cookies after logging into TradingView.
    - Adjust optional scraper settings (`MCP_SCRAPER_HEADLESS`, `MCP_SCRAPER_WINDOW_WIDTH`, etc.) in `.env` if needed.
5.  **Ensure ChromeDriver:** Make sure `chromedriver` is installed and accessible in your system's PATH, or configure the `tview-scraper.py` accordingly if it allows specifying a path.

## Running the Server

Ensure your virtual environment is activated (`source venv/bin/activate` or equivalent).

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

To use this server with MCP clients like Claude Desktop or Cursor, you need to configure them to run the `main.py` script using the Python interpreter **from the virtual environment you created** and provide your TradingView credentials via environment variables.

**Important:**

- Replace the placeholder paths below with the **absolute paths** on your system. You can often get the absolute path by navigating to the directory in your terminal and running `pwd` (print working directory).
- Provide your actual `TRADINGVIEW_SESSION_ID` and `TRADINGVIEW_SESSION_ID_SIGN` in the `env` block.

### Claude Desktop

1.  Open your Claude Desktop configuration file:
    - **Windows:** `%APPDATA%\\Claude\\claude_desktop_config.json`
    - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
2.  Add or merge the following within the `mcpServers` object:

    ```json
    {
      "mcpServers": {
        "tradingview-chart-mcp": {
          "command": "/absolute/path/to/your/tradingview-chart-mcp/venv/bin/python3",
          "args": ["/absolute/path/to/your/tradingview-chart-mcp/main.py"],
          "env": {
            "TRADINGVIEW_SESSION_ID": "YOUR_SESSION_ID_HERE",
            "TRADINGVIEW_SESSION_ID_SIGN": "YOUR_SESSION_ID_SIGN_HERE"
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
2.  Add or merge the following within the `mcpServers` object:

    ```json
    {
      "mcpServers": {
        "tradingview-chart-mcp": {
          "command": "/absolute/path/to/your/tradingview-chart-mcp/venv/bin/python3",
          "args": ["/absolute/path/to/your/tradingview-chart-mcp/main.py"],
          "env": {
            "TRADINGVIEW_SESSION_ID": "YOUR_SESSION_ID_HERE",
            "TRADINGVIEW_SESSION_ID_SIGN": "YOUR_SESSION_ID_SIGN_HERE"
          }
        }
        // ... other servers if any ...
      }
    }
    ```

3.  Replace the placeholder paths (`command`, `args`) with your actual absolute paths.
4.  Replace `YOUR_SESSION_ID_HERE` and `YOUR_SESSION_ID_SIGN_HERE` with your actual TradingView credentials.
5.  Restart Cursor.

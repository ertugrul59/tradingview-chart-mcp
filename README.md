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

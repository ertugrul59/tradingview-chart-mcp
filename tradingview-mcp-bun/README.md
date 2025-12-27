# 📈 TradingView Chart MCP Server (Bun Edition)

A high-performance **Model Context Protocol (MCP)** server that scrapes TradingView charts and allows your AI assistant (Claude, OpenCode, etc.) to "see" market data.

Built with **Bun** 🥟 and **Playwright** 🎭 for superior speed and stability compared to the Python/Selenium original.

## ✨ Features

- **🚀 Ultra Fast**: Native TypeScript execution with Bun.
- **👁️ Vision Ready**: Returns charts as high-resolution images, enabling AI visual analysis.
- **🔐 Robust Auth**: Supports session cookies for real-time data and premium chart layouts.
- **📊 Smart Waiting**: Automatically detects when chart candles are fully loaded.
- **🧱 Docker Ready**: Production-grade Dockerfile included.

---

## 🛠️ Prerequisites

- **Bun**: [Install Bun](https://bun.sh/) (`curl -fsSL https://bun.sh/install | bash`)
- **Git**

---

## 📥 Installation

1.  **Clone the repository** (if you haven't already):
    ```bash
    git clone <repo-url>
    cd tradingview-mcp-bun
    ```

2.  **Install Dependencies**:
    ```bash
    bun install
    ```

3.  **Install Browsers**:
    This downloads the headless Chromium browser used by Playwright.
    ```bash
    bunx playwright install chromium
    ```

---

## ⚙️ Configuration

1.  **Create your Environment File**:
    ```bash
    cp .env.example .env
    ```

2.  **Update `.env` with your details**:

| Variable | Description | Recommended |
| :--- | :--- | :--- |
| `TRADINGVIEW_SESSION_ID` | Your `sessionid` cookie from tradingview.com. **Required** for reliable data. | `abcd...` |
| `TRADINGVIEW_SESSION_ID_SIGN` | Your `sessionid_sign` cookie. Adds extra auth stability. | `abcd...` |
| `MCP_SCRAPER_CHART_PAGE_ID` | Load a specific saved chart layout (found in URL: `/chart/YOUR_ID/`). | `XHDbt5Yy` |
| `MCP_SCRAPER_HEADLESS` | Run browser in background (`True`) or visible (`False`) for debugging. | `True` |

### 🍪 How to get your Cookies
1.  Go to [TradingView.com](https://www.tradingview.com) and log in.
2.  Open Developer Tools (`F12` or `Right Click` -> `Inspect`).
3.  Go to the **Application** tab -> **Cookies** (left sidebar).
4.  Click `https://www.tradingview.com`.
5.  Find `sessionid` and `sessionid_sign` values and copy them into your `.env`.

---

## 🚀 Usage

### Option 1: Run Locally (with MCP Client)
This server communicates via `stdio`. You generally don't run it "alone" but connect an MCP Client to it.

**Command to configure in your Client (Claude / OpenCode):**
```bash
bun run /absolute/path/to/tradingview-mcp-bun/src/index.ts
```

### Option 2: Test Manually (MCP Inspector)
The [MCP Inspector](https://github.com/modelcontextprotocol/inspector) lets you test the tools in your browser without an AI.

```bash
npx @modelcontextprotocol/inspector bun run src/index.ts
```

### Option 3: Docker 🐳
Run the server in a container (useful for deployment).

1.  **Build**:
    ```bash
    docker build -t tradingview-mcp .
    ```
2.  **Run**:
    ```bash
    docker run -i --init --rm --env-file .env tradingview-mcp
    ```

---

## 🧰 Available Tools

The server exposes user-friendly tools to your AI:

### `get_chart_image`
Fetches a snapshot of a crypto or stock chart.
*   **ticker**: The symbol (e.g., `BYBIT:BTCUSDT.P`, `NASDAQ:AAPL`, `OANDA:XAUUSD`).
*   **interval**: Timeframe (e.g., `1`, `5`, `15`, `60`, `240` (4h), `D` (Daily), `W` (Weekly)).

**Example Prompt:**
> "Show me the 15-minute chart for BTCUSDT on Bybit."

### `get_performance_stats`
Checks the health of the scraper.
*   Returns **Uptime**, **Request Count**, and **Engine Status**.

---

## ❓ Troubleshooting

**Q: The chart is blank or shows "Delayed Data".**
A: You likely aren't authenticated. Make sure `TRADINGVIEW_SESSION_ID` is set in your `.env`. Without it, TradingView blocks automated traffic or shows delayed data warnings.

**Q: It's crashing with explicit waits.**
A: If your internet is slow, increase the internal timeouts in `src/scraper.ts`.

**Q: "Executable doesn't exist" error.**
A: Run `bunx playwright install chromium` to force download the browser binary.

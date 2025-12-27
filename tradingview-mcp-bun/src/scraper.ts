import { chromium, type Browser, type BrowserContext, type Page } from 'playwright';
import * as fs from 'fs';
import * as path from 'path';
import { config, VIEWPORT } from './config.js';

export class TradingViewScraper {
    private browser: Browser | null = null;
    private context: BrowserContext | null = null;

    // Constants
    private static readonly AUTH_FILE = 'auth.json';

    async init() {
        console.log('Initializing Playwright Browser...');
        console.log(`Config: Headless=${config.HEADLESS}, Viewport=${VIEWPORT.width}x${VIEWPORT.height}, ChartID=${config.CHART_PAGE_ID || 'Default'}`);

        this.browser = await chromium.launch({
            headless: config.HEADLESS,
            args: ['--no-sandbox', '--disable-blink-features=AutomationControlled']
        });

        // Check if auth file exists
        let storageState: string | undefined = undefined;
        if (fs.existsSync(TradingViewScraper.AUTH_FILE)) {
            console.log(`Loading auth state from ${TradingViewScraper.AUTH_FILE}`);
            storageState = TradingViewScraper.AUTH_FILE;
        } else if (config.SESSION_ID) {
            console.log('Using TRADINGVIEW_SESSION_ID from environment');
            storageState = undefined;
        } else {
            console.warn(`Warning: No auth found (${TradingViewScraper.AUTH_FILE} or TRADINGVIEW_SESSION_ID). You may see delayed data or nag screens.`);
        }

        // Create a context with your session cookies
        this.context = await this.browser.newContext({
            viewport: VIEWPORT,
            deviceScaleFactor: 2, // Retina quality screenshots
            storageState: storageState
        });

        // Manual cookie injection if using Env Var
        if (!storageState && config.SESSION_ID) {
            const cookies = [{
                name: 'sessionid',
                value: config.SESSION_ID,
                domain: '.tradingview.com',
                path: '/'
            }];

            // Add signature if present (Important for robust auth)
            if (config.SESSION_ID_SIGN) {
                cookies.push({
                    name: 'sessionid_sign',
                    value: config.SESSION_ID_SIGN,
                    domain: '.tradingview.com',
                    path: '/'
                });
            }

            await this.context.addCookies(cookies);
        }

        // Grant permissions just in case
        await this.context.grantPermissions(['clipboard-read', 'clipboard-write']);
    }

    async getChartImage(ticker: string, interval: string): Promise<string> {
        if (!this.context) await this.init();
        const page = await this.context!.newPage();

        try {
            console.log(`Navigating to chart for ${ticker} (${interval})...`);

            // Construct Base URL based on Chart Page ID
            let baseUrl = 'https://www.tradingview.com/chart/';
            if (config.CHART_PAGE_ID) {
                baseUrl += `${config.CHART_PAGE_ID}/`;
            }

            // "symbol" and "interval" URL params are supported by TradingView
            const url = `${baseUrl}?symbol=${ticker}&interval=${interval}`;

            await page.goto(url, {
                waitUntil: 'domcontentloaded' // Faster than 'networkidle'
            });

            // Wait for the chart canvas to actually render
            // We look for the main chart container or canvas
            const chartSelector = 'div[class*="chart-container"]';
            console.log('Waiting for chart container...');
            try {
                await page.waitForSelector(chartSelector, { timeout: 15000 });
            } catch (e) {
                console.warn("Chart container selector timed out, trying loose canvas check...");
                await page.waitForSelector('canvas', { timeout: 5000 });
            }

            // 1. Hide Floating Toolbars & Toasts
            // 2. Hide "Trial" or "Plan" upgrades
            await page.addStyleTag({
                content: `
        .tv-floating-toolbar, 
        .toast-container,
        .tv-dialog,
        [data-role="toast-container"],
        [class*="floating-toolbar"],
        #header-toolbar-screenshot,
        .layout__area--left
        { display: none !important; }
      `});

            // Smart Wait: Wait for chart bars to actually exist
            try {
                // Wait for at least one candle/bar to appear
                await page.waitForSelector('.tv-lightweight-charts', { state: 'visible', timeout: 5000 });
            } catch {
                // Fallback if selector fails or class name changed
                await page.waitForTimeout(2000);
            }

            console.log('Taking screenshot...');
            // Take the screenshot (Buffer)
            const buffer = await page.screenshot({
                fullPage: false,
                type: 'png'
            });

            console.log('Screenshot captured successfully.');
            // Convert Buffer -> Base64 String
            return buffer.toString('base64');

        } catch (e) {
            console.error("Scrape failed:", e);
            throw e;
        } finally {
            await page.close();
        }
    }

    async close() {
        if (this.browser) {
            await this.browser.close();
            this.browser = null;
            this.context = null;
        }
    }
}

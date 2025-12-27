import dotenv from 'dotenv';
dotenv.config();

export const config = {
    // Auth
    SESSION_ID: process.env.TRADINGVIEW_SESSION_ID || '',
    SESSION_ID_SIGN: process.env.TRADINGVIEW_SESSION_ID_SIGN || '',

    // Scraper Configuration
    HEADLESS: (process.env.MCP_SCRAPER_HEADLESS || 'True').toLowerCase() === 'true',
    WINDOW_WIDTH: parseInt(process.env.MCP_SCRAPER_WINDOW_WIDTH || '2560', 10),
    WINDOW_HEIGHT: parseInt(process.env.MCP_SCRAPER_WINDOW_HEIGHT || '1440', 10),
    CHART_PAGE_ID: process.env.MCP_SCRAPER_CHART_PAGE_ID || '', // "XHDbt5Yy" is common default but empty loads generic

    // Feature Flags / Toggles
    DEBUG: (process.env.MCP_DEBUG || 'false').toLowerCase() === 'true',
};

// Computed property for viewport
export const VIEWPORT = {
    width: config.WINDOW_WIDTH,
    height: config.WINDOW_HEIGHT
};

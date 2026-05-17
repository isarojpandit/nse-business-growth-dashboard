NSE_HOME_URL = "https://www.nseindia.com/"

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}

NSE_BUSINESS_GROWTH_URLS = {
    "business_growth_home": (
        "https://www.nseindia.com/static/national-stock-exchange/"
        "nse-volume-business-growth"
    ),
    "capital_market": (
        "https://www.nseindia.com/market-data/business-growth-cm-segment"
    ),
    "equity_derivatives": (
        "https://www.nseindia.com/market-data/business-growth-fo-segment"
    ),
    "currency_derivatives": (
        "https://www.nseindia.com/market-data/business-growth-cd-segment"
    ),
    "interest_rate_derivatives": (
        "https://www.nseindia.com/market-data/business-growth-interest-rate-derivative"
    ),
}
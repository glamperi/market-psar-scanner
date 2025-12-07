"""
Options data fetcher with multiple sources:
1. Schwab API (if credentials available) - primary
2. yfinance (default)
3. Yahoo Finance HTML scraping (fallback)
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import re

# Check for Schwab credentials
SCHWAB_CLIENT_ID = os.getenv('SCHWAB_CLIENT_ID')
SCHWAB_CLIENT_SECRET = os.getenv('SCHWAB_CLIENT_SECRET')
SCHWAB_REFRESH_TOKEN = os.getenv('SCHWAB_REFRESH_TOKEN')

_schwab_access_token = None
_schwab_token_expiry = None


def _get_schwab_token() -> Optional[str]:
    """Get Schwab access token using refresh token."""
    global _schwab_access_token, _schwab_token_expiry
    
    if not all([SCHWAB_CLIENT_ID, SCHWAB_CLIENT_SECRET, SCHWAB_REFRESH_TOKEN]):
        return None
    
    # Return cached token if still valid
    if _schwab_access_token and _schwab_token_expiry and datetime.now() < _schwab_token_expiry:
        return _schwab_access_token
    
    try:
        url = "https://api.schwabapi.com/v1/oauth/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "refresh_token",
            "refresh_token": SCHWAB_REFRESH_TOKEN,
            "client_id": SCHWAB_CLIENT_ID,
            "client_secret": SCHWAB_CLIENT_SECRET
        }
        
        response = requests.post(url, headers=headers, data=data, timeout=10)
        if response.status_code == 200:
            token_data = response.json()
            _schwab_access_token = token_data.get('access_token')
            expires_in = token_data.get('expires_in', 1800)  # Default 30 min
            _schwab_token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)
            return _schwab_access_token
    except Exception as e:
        print(f"  Schwab token error: {e}")
    
    return None


def _fetch_options_schwab(ticker: str, min_days: int = 14, max_days: int = 45) -> Optional[Dict]:
    """Fetch options data from Schwab API."""
    token = _get_schwab_token()
    if not token:
        return None
    
    try:
        # Calculate date range
        today = datetime.now().date()
        from_date = (today + timedelta(days=min_days)).strftime('%Y-%m-%d')
        to_date = (today + timedelta(days=max_days)).strftime('%Y-%m-%d')
        
        url = f"https://api.schwabapi.com/marketdata/v1/chains"
        params = {
            "symbol": ticker,
            "contractType": "PUT",
            "fromDate": from_date,
            "toDate": to_date,
            "strikeCount": 20
        }
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return _parse_schwab_options(data, ticker)
    except Exception as e:
        print(f"  Schwab API error for {ticker}: {e}")
    
    return None


def _parse_schwab_options(data: Dict, ticker: str) -> Optional[Dict]:
    """Parse Schwab options response."""
    try:
        put_exp_map = data.get('putExpDateMap', {})
        if not put_exp_map:
            return None
        
        # Get first expiration
        first_exp = list(put_exp_map.keys())[0]
        exp_date = first_exp.split(':')[0]  # Format: "2025-01-17:45"
        
        strikes_data = put_exp_map[first_exp]
        
        # Collect all puts
        puts = []
        for strike_str, options in strikes_data.items():
            strike = float(strike_str)
            opt = options[0] if options else {}
            puts.append({
                'strike': strike,
                'bid': opt.get('bid', 0),
                'ask': opt.get('ask', 0),
                'delta': opt.get('delta', 0),
                'lastPrice': opt.get('last', 0)
            })
        
        return {
            'expiration': exp_date,
            'puts': puts,
            'source': 'schwab'
        }
    except Exception as e:
        return None


def _fetch_options_yfinance(ticker: str, min_days: int = 14, max_days: int = 28) -> Optional[Dict]:
    """Fetch options data from yfinance."""
    try:
        import yfinance as yf
        
        stock = yf.Ticker(ticker)
        expirations = stock.options
        if not expirations:
            return None
        
        today = datetime.now().date()
        target_exp = None
        
        # Find expiration in target range
        for exp_str in expirations:
            exp_date = datetime.strptime(exp_str, '%Y-%m-%d').date()
            days_to_exp = (exp_date - today).days
            if min_days <= days_to_exp <= max_days:
                target_exp = exp_str
                break
        
        if not target_exp:
            # Fallback to first available >= min_days
            for exp_str in expirations:
                exp_date = datetime.strptime(exp_str, '%Y-%m-%d').date()
                if (exp_date - today).days >= min_days:
                    target_exp = exp_str
                    break
        
        if not target_exp:
            return None
        
        chain = stock.option_chain(target_exp)
        puts = chain.puts
        if puts.empty:
            return None
        
        puts_list = []
        for _, row in puts.iterrows():
            puts_list.append({
                'strike': row.get('strike', 0),
                'bid': row.get('bid', 0) or 0,
                'ask': row.get('ask', 0) or 0,
                'lastPrice': row.get('lastPrice', 0) or 0
            })
        
        return {
            'expiration': target_exp,
            'puts': puts_list,
            'source': 'yfinance'
        }
        
    except Exception as e:
        error_msg = str(e)
        if 'Too Many Requests' not in error_msg:
            pass  # Silent for rate limits
        return None


def _fetch_options_yahoo_scrape(ticker: str, min_days: int = 14, max_days: int = 28) -> Optional[Dict]:
    """Fetch options by scraping Yahoo Finance HTML."""
    try:
        import pandas as pd
        
        # First get available expirations
        url = f"https://finance.yahoo.com/quote/{ticker}/options"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None
        
        html = response.text
        
        # Check for rate limiting
        if 'Too Many Requests' in html or response.status_code == 429:
            return None
        
        # Find expiration dates in the page
        date_pattern = r'[?&]date=(\d{10})'
        timestamps = re.findall(date_pattern, html)
        
        if not timestamps:
            # Try alternative pattern
            date_pattern2 = r'"expirationDates":\[([^\]]+)\]'
            exp_match = re.search(date_pattern2, html)
            if exp_match:
                timestamps = re.findall(r'(\d{10})', exp_match.group(1))
        
        # If no timestamps found, return None (consent page blocks scraping)
        if not timestamps:
            return None
        
        today = datetime.now().date()
        target_timestamp = None
        target_exp = None
        
        unique_timestamps = sorted(set(timestamps))
        
        for ts in unique_timestamps:
            try:
                exp_date = datetime.fromtimestamp(int(ts)).date()
                days_to_exp = (exp_date - today).days
                if min_days <= days_to_exp <= max_days:
                    target_timestamp = ts
                    target_exp = exp_date.strftime('%Y-%m-%d')
                    break
            except (ValueError, OSError):
                continue
        
        if not target_timestamp:
            for ts in unique_timestamps:
                try:
                    exp_date = datetime.fromtimestamp(int(ts)).date()
                    if (exp_date - today).days >= min_days:
                        target_timestamp = ts
                        target_exp = exp_date.strftime('%Y-%m-%d')
                        break
                except (ValueError, OSError):
                    continue
        
        if not target_timestamp:
            return None
        
        # Fetch the specific expiration page
        url_with_date = f"https://finance.yahoo.com/quote/{ticker}/options?date={target_timestamp}"
        response = requests.get(url_with_date, headers=headers, timeout=15)
        if response.status_code != 200:
            return None
        
        # Parse tables
        try:
            tables = pd.read_html(response.text)
            
            if not tables:
                return None
            
            # Find puts table - second table with Strike column
            puts_df = None
            found_first = False
            
            for df in tables:
                cols_lower = [str(c).lower() for c in df.columns]
                if 'strike' in cols_lower:
                    if found_first:
                        puts_df = df
                        break
                    found_first = True
            
            if puts_df is None and len(tables) >= 2:
                puts_df = tables[1]
            
            if puts_df is None or puts_df.empty:
                return None
            
            puts_list = []
            for _, row in puts_df.iterrows():
                try:
                    strike = None
                    bid = 0
                    ask = 0
                    last = 0
                    
                    for col in row.index:
                        col_lower = str(col).lower()
                        val = row[col]
                        
                        if 'strike' in col_lower:
                            strike = float(str(val).replace(',', ''))
                        elif col_lower == 'bid':
                            bid = float(str(val).replace(',', '').replace('-', '0'))
                        elif col_lower == 'ask':
                            ask = float(str(val).replace(',', '').replace('-', '0'))
                        elif 'last' in col_lower or col_lower == 'price':
                            last = float(str(val).replace(',', '').replace('-', '0'))
                    
                    if strike and strike > 0:
                        puts_list.append({
                            'strike': strike,
                            'bid': bid,
                            'ask': ask,
                            'lastPrice': last
                        })
                except (ValueError, TypeError):
                    continue
            
            if not puts_list:
                return None
            
            return {
                'expiration': target_exp,
                'puts': puts_list,
                'source': 'yahoo_scrape'
            }
            
        except Exception as e:
            return None
            
    except Exception as e:
        return None


def _fetch_options_yahoo_selenium(ticker: str, min_days: int = 14, max_days: int = 28) -> Optional[Dict]:
    """Fetch options using Selenium - parse tables directly."""
    try:
        import pandas as pd
        from io import StringIO
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        import time
        
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")  # New headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-images")  # Faster loading
        chrome_options.add_argument("--blink-settings=imagesEnabled=false")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        driver.set_page_load_timeout(30)  # Increased for CI
        
        try:
            url = f"https://finance.yahoo.com/quote/{ticker}/options"
            driver.get(url)
            time.sleep(5)
            
            html = driver.page_source
            
            # Parse tables directly - default page shows nearest expiration
            tables = pd.read_html(StringIO(html))
            if not tables or len(tables) < 2:
                return None
            
            # Second table is puts
            puts_df = tables[1]
            
            if puts_df.empty or 'Strike' not in puts_df.columns:
                return None
            
            # Extract expiration from contract name (e.g., 'MRK251212P00055000')
            target_exp = None
            if 'Contract Name' in puts_df.columns and len(puts_df) > 0:
                contract = str(puts_df.iloc[0]['Contract Name'])
                ticker_len = len(ticker)
                if len(contract) > ticker_len + 6:
                    date_str = contract[ticker_len:ticker_len+6]
                    try:
                        year = 2000 + int(date_str[0:2])
                        month = int(date_str[2:4])
                        day = int(date_str[4:6])
                        target_exp = f"{year}-{month:02d}-{day:02d}"
                    except:
                        target_exp = datetime.now().strftime('%Y-%m-%d')
            
            if not target_exp:
                target_exp = datetime.now().strftime('%Y-%m-%d')
            
            puts_list = []
            for _, row in puts_df.iterrows():
                try:
                    strike = float(row.get('Strike', 0))
                    bid = row.get('Bid', 0)
                    ask = row.get('Ask', 0)
                    last = row.get('Last Price', 0)
                    
                    # Handle '-' values
                    bid = float(bid) if bid != '-' and pd.notna(bid) else 0
                    ask = float(ask) if ask != '-' and pd.notna(ask) else 0
                    last = float(last) if last != '-' and pd.notna(last) else 0
                    
                    if strike and strike > 0:
                        puts_list.append({
                            'strike': strike,
                            'bid': bid,
                            'ask': ask,
                            'lastPrice': last
                        })
                except:
                    continue
            
            if not puts_list:
                return None
            
            return {
                'expiration': target_exp,
                'puts': puts_list,
                'source': 'yahoo_selenium'
            }
            
        finally:
            driver.quit()
            
    except Exception as e:
        # Silent fail - let other sources try
        return None


def fetch_options_chain(ticker: str, min_days: int = 14, max_days: int = 28, debug: bool = False) -> Optional[Dict]:
    """
    Fetch options chain using best available source.
    
    Order of preference:
    1. Schwab API (if credentials available)
    2. yfinance 
    3. Yahoo Finance HTML scraping
    4. Yahoo Finance Selenium (handles consent page)
    
    Returns:
        Dict with 'expiration', 'puts', 'source' or None if all fail
    """
    # Try Schwab first if credentials exist
    if SCHWAB_CLIENT_ID:
        if debug:
            print(f"    [{ticker}] Trying Schwab API...")
        result = _fetch_options_schwab(ticker, min_days, max_days)
        if result:
            if debug:
                print(f"    [{ticker}] ✓ Schwab API success")
            return result
        if debug:
            print(f"    [{ticker}] ✗ Schwab API failed")
    
    # Try yfinance
    if debug:
        print(f"    [{ticker}] Trying yfinance...")
    result = _fetch_options_yfinance(ticker, min_days, max_days)
    if result:
        if debug:
            print(f"    [{ticker}] ✓ yfinance success")
        return result
    if debug:
        print(f"    [{ticker}] ✗ yfinance failed, trying Yahoo scrape...")
    
    # Fallback to Yahoo scraping
    result = _fetch_options_yahoo_scrape(ticker, min_days, max_days)
    if result:
        if debug:
            print(f"    [{ticker}] ✓ Yahoo scrape success (source: {result.get('source', 'unknown')})")
        return result
    if debug:
        print(f"    [{ticker}] ✗ All sources failed")
    
    # Note: _fetch_options_yahoo_selenium() exists but is not called by default
    # Enable manually if needed for debugging consent page issues
    
    return None


def get_options_source_status() -> str:
    """Return which options source is available."""
    if SCHWAB_CLIENT_ID and SCHWAB_CLIENT_SECRET and SCHWAB_REFRESH_TOKEN:
        return "Schwab API"
    return "yfinance + Yahoo scrape fallback"

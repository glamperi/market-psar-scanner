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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
        
        html = response.text
        
        # Find expiration dates in the page
        # They appear as Unix timestamps in the URL pattern: ?date=1234567890
        date_pattern = r'\?date=(\d{10})'
        timestamps = re.findall(date_pattern, html)
        
        if not timestamps:
            return None
        
        today = datetime.now().date()
        target_timestamp = None
        target_exp = None
        
        for ts in sorted(set(timestamps)):
            exp_date = datetime.fromtimestamp(int(ts)).date()
            days_to_exp = (exp_date - today).days
            if min_days <= days_to_exp <= max_days:
                target_timestamp = ts
                target_exp = exp_date.strftime('%Y-%m-%d')
                break
        
        if not target_timestamp:
            # Fallback to first >= min_days
            for ts in sorted(set(timestamps)):
                exp_date = datetime.fromtimestamp(int(ts)).date()
                if (exp_date - today).days >= min_days:
                    target_timestamp = ts
                    target_exp = exp_date.strftime('%Y-%m-%d')
                    break
        
        if not target_timestamp:
            return None
        
        # Fetch the specific expiration page
        url_with_date = f"https://finance.yahoo.com/quote/{ticker}/options?date={target_timestamp}"
        response = requests.get(url_with_date, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
        
        # Parse tables
        try:
            tables = pd.read_html(response.text)
            # Usually puts are in the second table
            puts_df = None
            for df in tables:
                cols = [str(c).lower() for c in df.columns]
                if 'strike' in cols and any('put' in c or 'bid' in c for c in cols):
                    puts_df = df
                    break
            
            if puts_df is None and len(tables) >= 2:
                puts_df = tables[1]  # Second table is usually puts
            
            if puts_df is None:
                return None
            
            puts_list = []
            for _, row in puts_df.iterrows():
                try:
                    strike = float(str(row.get('Strike', 0)).replace(',', ''))
                    bid = float(str(row.get('Bid', 0)).replace(',', '').replace('-', '0'))
                    ask = float(str(row.get('Ask', 0)).replace(',', '').replace('-', '0'))
                    last = float(str(row.get('Last Price', 0)).replace(',', '').replace('-', '0'))
                    
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


def fetch_options_chain(ticker: str, min_days: int = 14, max_days: int = 28) -> Optional[Dict]:
    """
    Fetch options chain using best available source.
    
    Order of preference:
    1. Schwab API (if credentials available)
    2. yfinance 
    3. Yahoo Finance HTML scraping
    
    Returns:
        Dict with 'expiration', 'puts', 'source' or None if all fail
    """
    # Try Schwab first if credentials exist
    if SCHWAB_CLIENT_ID:
        result = _fetch_options_schwab(ticker, min_days, max_days)
        if result:
            return result
    
    # Try yfinance
    result = _fetch_options_yfinance(ticker, min_days, max_days)
    if result:
        return result
    
    # Fallback to Yahoo scraping
    result = _fetch_options_yahoo_scrape(ticker, min_days, max_days)
    if result:
        return result
    
    return None


def get_options_source_status() -> str:
    """Return which options source is available."""
    if SCHWAB_CLIENT_ID and SCHWAB_CLIENT_SECRET and SCHWAB_REFRESH_TOKEN:
        return "Schwab API"
    return "yfinance + Yahoo scrape fallback"

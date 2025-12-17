"""
Options Data Module - Schwab API Integration
=============================================
Fetches real-time options chain data from Schwab API.

SETUP:
1. Set environment variables:
   export SCHWAB_APP_KEY="your-app-key"
   export SCHWAB_APP_SECRET="your-app-secret"

2. Place schwab_tokens.json in the scanner root directory with:
   {
     "access_token": "...",
     "refresh_token": "...",
     "expires_at": "2025-12-16T13:15:39.778469",
     "token_type": "Bearer"
   }

The module will auto-refresh tokens and save them back to the JSON file.
"""

import os
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import base64

# =============================================================================
# CONFIGURATION - Uses same env vars as your other Schwab program
# =============================================================================

SCHWAB_APP_KEY = os.getenv('SCHWAB_APP_KEY') or os.getenv('SCHWAB_CLIENT_ID')
SCHWAB_APP_SECRET = os.getenv('SCHWAB_APP_SECRET') or os.getenv('SCHWAB_CLIENT_SECRET')

# Token file location - check multiple paths
TOKEN_FILE_PATHS = [
    'schwab_tokens.json',                    # Current directory
    os.path.expanduser('~/schwab_tokens.json'),  # Home directory
    os.path.join(os.path.dirname(__file__), '..', 'schwab_tokens.json'),  # Scanner root
]

SCHWAB_TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
SCHWAB_OPTIONS_URL = "https://api.schwabapi.com/marketdata/v1/chains"

# Cached token
_schwab_access_token = None
_schwab_token_expiry = None
_token_file_path = None


def _find_token_file() -> Optional[str]:
    """Find the schwab_tokens.json file."""
    global _token_file_path
    
    if _token_file_path and os.path.exists(_token_file_path):
        return _token_file_path
    
    for path in TOKEN_FILE_PATHS:
        if os.path.exists(path):
            _token_file_path = path
            return path
    
    return None


def _load_tokens() -> Optional[Dict]:
    """Load tokens from JSON file."""
    token_file = _find_token_file()
    if not token_file:
        return None
    
    try:
        with open(token_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading tokens: {e}")
        return None


def _save_tokens(tokens: Dict) -> bool:
    """Save tokens back to JSON file."""
    token_file = _find_token_file()
    if not token_file:
        # Create in current directory
        token_file = 'schwab_tokens.json'
    
    try:
        with open(token_file, 'w') as f:
            json.dump(tokens, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving tokens: {e}")
        return False


def _is_token_expired(tokens: Dict) -> bool:
    """Check if access token is expired."""
    if not tokens or 'expires_at' not in tokens:
        return True
    
    try:
        expires_at = datetime.fromisoformat(tokens['expires_at'].replace('Z', '+00:00').replace('+00:00', ''))
        # Add 5 minute buffer
        return datetime.now() >= (expires_at - timedelta(minutes=5))
    except:
        return True


def _refresh_access_token(refresh_token: str) -> Optional[Dict]:
    """Refresh the access token using refresh token."""
    if not SCHWAB_APP_KEY or not SCHWAB_APP_SECRET:
        print("Missing SCHWAB_APP_KEY or SCHWAB_APP_SECRET environment variables")
        return None
    
    try:
        # Create Basic auth header
        credentials = f"{SCHWAB_APP_KEY}:{SCHWAB_APP_SECRET}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
        
        response = requests.post(SCHWAB_TOKEN_URL, headers=headers, data=data, timeout=30)
        
        if response.status_code == 200:
            token_data = response.json()
            
            # Calculate expiry (typically 30 minutes)
            expires_in = token_data.get('expires_in', 1800)
            expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            return {
                "access_token": token_data.get('access_token'),
                "refresh_token": token_data.get('refresh_token', refresh_token),  # May return new refresh token
                "expires_at": expires_at.isoformat(),
                "token_type": token_data.get('token_type', 'Bearer')
            }
        else:
            print(f"Token refresh failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Token refresh error: {e}")
        return None


def get_schwab_access_token() -> Optional[str]:
    """
    Get a valid Schwab access token.
    
    Automatically refreshes if expired and saves new tokens to file.
    """
    global _schwab_access_token, _schwab_token_expiry
    
    # Check cached token first
    if _schwab_access_token and _schwab_token_expiry:
        if datetime.now() < _schwab_token_expiry:
            return _schwab_access_token
    
    # Load tokens from file
    tokens = _load_tokens()
    
    if not tokens:
        print("No schwab_tokens.json found. Run authentication first.")
        return None
    
    # Check if token is still valid
    if not _is_token_expired(tokens):
        _schwab_access_token = tokens.get('access_token')
        try:
            _schwab_token_expiry = datetime.fromisoformat(tokens['expires_at'].replace('Z', '+00:00').replace('+00:00', ''))
        except:
            _schwab_token_expiry = datetime.now() + timedelta(minutes=25)
        return _schwab_access_token
    
    # Token expired - refresh it
    print("Schwab token expired, refreshing...")
    refresh_token = tokens.get('refresh_token')
    
    if not refresh_token:
        print("No refresh token available. Re-authentication required.")
        return None
    
    new_tokens = _refresh_access_token(refresh_token)
    
    if new_tokens:
        # Save new tokens
        _save_tokens(new_tokens)
        
        # Cache in memory
        _schwab_access_token = new_tokens.get('access_token')
        try:
            _schwab_token_expiry = datetime.fromisoformat(new_tokens['expires_at'])
        except:
            _schwab_token_expiry = datetime.now() + timedelta(minutes=25)
        
        print("Schwab token refreshed successfully")
        return _schwab_access_token
    else:
        print("Failed to refresh token. Re-authentication may be required.")
        return None


def get_options_chain(ticker: str, strike_count: int = 10) -> Optional[Dict]:
    """
    Fetch options chain from Schwab API.
    
    Args:
        ticker: Stock symbol
        strike_count: Number of strikes above/below current price
    
    Returns:
        Options chain data or None
    """
    access_token = get_schwab_access_token()
    
    if not access_token:
        return None
    
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        params = {
            "symbol": ticker.upper(),
            "contractType": "PUT",
            "strikeCount": strike_count,
            "includeUnderlyingQuote": "true",
            "strategy": "SINGLE"
        }
        
        response = requests.get(SCHWAB_OPTIONS_URL, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            # Token might have expired mid-session, try refresh
            global _schwab_access_token, _schwab_token_expiry
            _schwab_access_token = None
            _schwab_token_expiry = None
            
            # Retry once
            access_token = get_schwab_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.get(SCHWAB_OPTIONS_URL, headers=headers, params=params, timeout=30)
                if response.status_code == 200:
                    return response.json()
        
        print(f"Options chain request failed for {ticker}: {response.status_code}")
        return None
        
    except Exception as e:
        print(f"Options chain error for {ticker}: {e}")
        return None


def get_put_spread_recommendation(ticker: str, current_price: float, atr_percent: float = 5.0) -> Optional[Dict]:
    """
    Get put spread recommendation for a short candidate.
    
    Args:
        ticker: Stock symbol
        current_price: Current stock price
        atr_percent: ATR percentage for strike selection
    
    Returns:
        Dict with buy_strike, sell_strike, expiration, spread_cost, max_profit
    """
    chain = get_options_chain(ticker)
    
    if not chain:
        return None
    
    try:
        put_map = chain.get('putExpDateMap', {})
        
        if not put_map:
            return None
        
        # Find expiration 20-45 days out
        today = datetime.now()
        target_min = today + timedelta(days=20)
        target_max = today + timedelta(days=45)
        
        best_exp = None
        best_exp_date = None
        
        for exp_key in put_map.keys():
            # Parse expiration date (format: "2025-01-17:5")
            exp_date_str = exp_key.split(':')[0]
            try:
                exp_date = datetime.strptime(exp_date_str, '%Y-%m-%d')
                if target_min <= exp_date <= target_max:
                    if best_exp is None or exp_date < best_exp_date:
                        best_exp = exp_key
                        best_exp_date = exp_date
            except:
                continue
        
        if not best_exp:
            # Fall back to first available expiration
            best_exp = list(put_map.keys())[0]
            best_exp_date = datetime.strptime(best_exp.split(':')[0], '%Y-%m-%d')
        
        strikes_data = put_map[best_exp]
        
        # Find strikes
        # Buy put: slightly ITM (5-10% above current price)
        # Sell put: OTM (10-20% below current price)
        buy_target = current_price * 1.05  # 5% ITM
        sell_target = current_price * 0.85  # 15% OTM
        
        buy_strike = None
        buy_premium = None
        sell_strike = None
        sell_premium = None
        
        for strike_str, options in strikes_data.items():
            strike = float(strike_str)
            if options and len(options) > 0:
                opt = options[0]
                mid_price = (opt.get('bid', 0) + opt.get('ask', 0)) / 2
                
                # Find buy strike (closest to buy_target, above current price)
                if strike >= current_price:
                    if buy_strike is None or abs(strike - buy_target) < abs(buy_strike - buy_target):
                        buy_strike = strike
                        buy_premium = mid_price
                
                # Find sell strike (closest to sell_target, below current price)
                if strike < current_price:
                    if sell_strike is None or abs(strike - sell_target) < abs(sell_strike - sell_target):
                        sell_strike = strike
                        sell_premium = mid_price
        
        if not buy_strike or not sell_strike or not buy_premium:
            return None
        
        spread_cost = buy_premium - (sell_premium or 0)
        max_profit = (buy_strike - sell_strike) - spread_cost
        
        days_to_expiry = (best_exp_date - today).days
        
        return {
            'buy_strike': buy_strike,
            'sell_strike': sell_strike,
            'expiration': best_exp_date.strftime('%Y-%m-%d'),
            'days_to_expiry': days_to_expiry,
            'spread_cost': spread_cost,
            'max_profit': max_profit,
            'buy_premium': buy_premium,
            'sell_premium': sell_premium
        }
        
    except Exception as e:
        print(f"Put spread calculation error for {ticker}: {e}")
        return None


def is_schwab_available() -> bool:
    """Check if Schwab API is configured and available."""
    if not SCHWAB_APP_KEY or not SCHWAB_APP_SECRET:
        return False
    
    token_file = _find_token_file()
    if not token_file:
        return False
    
    return True


# =============================================================================
# STANDALONE TEST
# =============================================================================
if __name__ == "__main__":
    print("Schwab Options Data Module Test")
    print("=" * 50)
    
    print(f"\nConfiguration:")
    print(f"  SCHWAB_APP_KEY: {'Set' if SCHWAB_APP_KEY else 'NOT SET'}")
    print(f"  SCHWAB_APP_SECRET: {'Set' if SCHWAB_APP_SECRET else 'NOT SET'}")
    print(f"  Token file: {_find_token_file() or 'NOT FOUND'}")
    
    if is_schwab_available():
        print("\n✓ Schwab API is configured")
        
        # Test token refresh
        token = get_schwab_access_token()
        if token:
            print("✓ Access token obtained")
            
            # Test options chain
            print("\nTesting options chain for AAPL...")
            chain = get_options_chain("AAPL")
            if chain:
                print("✓ Options chain retrieved")
                
                # Test put spread
                spread = get_put_spread_recommendation("AAPL", 250.0)
                if spread:
                    print(f"✓ Put spread: Buy ${spread['buy_strike']} / Sell ${spread['sell_strike']}")
                    print(f"  Expiration: {spread['expiration']}")
                    print(f"  Cost: ${spread['spread_cost']:.2f}")
            else:
                print("✗ Failed to get options chain")
        else:
            print("✗ Failed to get access token")
    else:
        print("\n✗ Schwab API not configured")
        print("\nSetup required:")
        print("  1. export SCHWAB_APP_KEY='your-app-key'")
        print("  2. export SCHWAB_APP_SECRET='your-app-secret'")
        print("  3. Place schwab_tokens.json in scanner directory")

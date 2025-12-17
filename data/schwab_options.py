"""
Schwab API Options Data Module

Provides reliable options chain data from Schwab API.
Falls back to yfinance if Schwab is not configured.

Setup:
1. Create app at https://developer.schwab.com (Market Data Production only)
2. Set callback URL to: https://127.0.0.1:8182
3. Wait for "Ready For Use" status
4. Run initial auth to get refresh token
5. Add to .env or export:
   SCHWAB_APP_KEY=your-app-key
   SCHWAB_APP_SECRET=your-app-secret
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import pandas as pd

# Try to import schwabdev
try:
    import schwabdev
    SCHWAB_AVAILABLE = True
except ImportError:
    SCHWAB_AVAILABLE = False

# Try to import yfinance as fallback
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False


def _find_tokens_file() -> str:
    """Find schwab_tokens.json in common locations."""
    # Check multiple possible locations
    search_paths = [
        'schwab_tokens.json',  # Current directory
        os.path.join(os.path.dirname(__file__), '..', 'schwab_tokens.json'),  # Parent (scanner root)
        os.path.join(os.path.dirname(__file__), 'schwab_tokens.json'),  # Same dir as this file
        os.path.expanduser('~/schwab_tokens.json'),  # Home directory
        os.path.expanduser('~/Dev/Python/Investing/market-psar-scanner/schwab_tokens.json'),  # Full path
    ]
    
    for path in search_paths:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            print(f"📁 Found tokens file: {abs_path}")
            return abs_path
    
    # Default to current directory (will be created on auth)
    return 'schwab_tokens.json'


class SchwabOptions:
    """Schwab API client for options data."""
    
    def __init__(self):
        self.client = None
        self.initialized = False
        self._init_client()
    
    def _init_client(self):
        """Initialize Schwab client if credentials are available."""
        if not SCHWAB_AVAILABLE:
            print("⚠️  schwabdev not installed. Run: pip install schwabdev")
            return
        
        # Support both naming conventions (APP_KEY takes priority)
        client_id = os.environ.get('SCHWAB_APP_KEY') or os.environ.get('SCHWAB_CLIENT_ID')
        client_secret = os.environ.get('SCHWAB_APP_SECRET') or os.environ.get('SCHWAB_CLIENT_SECRET')
        callback_url = os.environ.get('SCHWAB_CALLBACK_URL', 'https://127.0.0.1:8182/callback')
        
        # Find tokens file
        tokens_file = os.environ.get('SCHWAB_TOKENS_FILE') or _find_tokens_file()
        
        if not client_id or not client_secret:
            print("⚠️  Schwab credentials not set. Using yfinance fallback.")
            print("    Set SCHWAB_APP_KEY and SCHWAB_APP_SECRET environment variables.")
            return
        
        try:
            self.client = schwabdev.Client(
                app_key=client_id,
                app_secret=client_secret,
                callback_url=callback_url,
                tokens_file=tokens_file
            )
            self.initialized = True
            print(f"✅ Schwab API initialized (tokens: {tokens_file})")
        except Exception as e:
            print(f"⚠️  Schwab init failed: {e}. Using yfinance fallback.")
    
    def get_options_chain(self, ticker: str, days_out: int = 60) -> Optional[Dict]:
        """
        Get options chain for a ticker.
        
        Args:
            ticker: Stock symbol
            days_out: Maximum days until expiration to fetch
            
        Returns:
            Dict with 'calls' and 'puts' DataFrames, or None if failed
        """
        # Try Schwab first
        if self.initialized and self.client:
            try:
                result = self._get_schwab_chain(ticker, days_out)
                if result:
                    return result
            except Exception as e:
                print(f"⚠️  Schwab options failed for {ticker}: {e}")
        
        # Fallback to yfinance
        if YFINANCE_AVAILABLE:
            return self._get_yfinance_chain(ticker, days_out)
        
        return None
    
    def _get_schwab_chain(self, ticker: str, days_out: int) -> Optional[Dict]:
        """Fetch options chain from Schwab API."""
        from_date = datetime.now()
        to_date = from_date + timedelta(days=days_out)
        
        response = self.client.option_chains(
            symbol=ticker,
            contractType='ALL',
            strikeCount=20,  # 20 strikes above and below current price
            fromDate=from_date.strftime('%Y-%m-%d'),
            toDate=to_date.strftime('%Y-%m-%d')
        )
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        # Parse Schwab response into standardized format
        calls_list = []
        puts_list = []
        
        call_map = data.get('callExpDateMap', {})
        put_map = data.get('putExpDateMap', {})
        
        for exp_date, strikes in call_map.items():
            exp = exp_date.split(':')[0]  # Format: "2025-01-17:30"
            for strike, contracts in strikes.items():
                for contract in contracts:
                    calls_list.append({
                        'expiration': exp,
                        'strike': float(strike),
                        'bid': contract.get('bid', 0),
                        'ask': contract.get('ask', 0),
                        'last': contract.get('last', 0),
                        'volume': contract.get('totalVolume', 0),
                        'openInterest': contract.get('openInterest', 0),
                        'impliedVolatility': contract.get('volatility', 0) / 100,
                        'delta': contract.get('delta', 0),
                        'theta': contract.get('theta', 0),
                        'contractSymbol': contract.get('symbol', '')
                    })
        
        for exp_date, strikes in put_map.items():
            exp = exp_date.split(':')[0]
            for strike, contracts in strikes.items():
                for contract in contracts:
                    puts_list.append({
                        'expiration': exp,
                        'strike': float(strike),
                        'bid': contract.get('bid', 0),
                        'ask': contract.get('ask', 0),
                        'last': contract.get('last', 0),
                        'volume': contract.get('totalVolume', 0),
                        'openInterest': contract.get('openInterest', 0),
                        'impliedVolatility': contract.get('volatility', 0) / 100,
                        'delta': contract.get('delta', 0),
                        'theta': contract.get('theta', 0),
                        'contractSymbol': contract.get('symbol', '')
                    })
        
        return {
            'calls': pd.DataFrame(calls_list) if calls_list else pd.DataFrame(),
            'puts': pd.DataFrame(puts_list) if puts_list else pd.DataFrame(),
            'underlying_price': data.get('underlyingPrice', 0),
            'source': 'schwab'
        }
    
    def _get_yfinance_chain(self, ticker: str, days_out: int) -> Optional[Dict]:
        """Fetch options chain from yfinance as fallback."""
        try:
            stock = yf.Ticker(ticker)
            expirations = stock.options
            
            if not expirations:
                return None
            
            # Filter expirations within days_out
            cutoff = datetime.now() + timedelta(days=days_out)
            valid_exps = []
            for exp in expirations:
                exp_date = datetime.strptime(exp, '%Y-%m-%d')
                if exp_date <= cutoff:
                    valid_exps.append(exp)
            
            if not valid_exps:
                valid_exps = expirations[:3]  # Take first 3 if none in range
            
            all_calls = []
            all_puts = []
            
            for exp in valid_exps[:5]:  # Limit to 5 expirations
                try:
                    chain = stock.option_chain(exp)
                    
                    calls = chain.calls.copy()
                    calls['expiration'] = exp
                    all_calls.append(calls)
                    
                    puts = chain.puts.copy()
                    puts['expiration'] = exp
                    all_puts.append(puts)
                except:
                    continue
            
            calls_df = pd.concat(all_calls, ignore_index=True) if all_calls else pd.DataFrame()
            puts_df = pd.concat(all_puts, ignore_index=True) if all_puts else pd.DataFrame()
            
            # Get current price
            price = stock.info.get('currentPrice') or stock.info.get('regularMarketPrice', 0)
            
            return {
                'calls': calls_df,
                'puts': puts_df,
                'underlying_price': price,
                'source': 'yfinance'
            }
        except Exception as e:
            print(f"⚠️  yfinance options failed for {ticker}: {e}")
            return None
    
    def get_covered_call_suggestion(
        self,
        ticker: str,
        current_price: float,
        min_days: int = 21,
        max_days: int = 60,
        target_otm_pct: float = 8.0
    ) -> Optional[Dict]:
        """
        Get covered call suggestion for a stock position.
        """
        chain = self.get_options_chain(ticker, max_days)
        if not chain or chain['calls'].empty:
            return None
        
        calls = chain['calls'].copy()
        
        # Filter by expiration
        calls['exp_date'] = pd.to_datetime(calls['expiration'])
        now = datetime.now()
        calls['days_to_exp'] = (calls['exp_date'] - now).dt.days
        calls = calls[(calls['days_to_exp'] >= min_days) & (calls['days_to_exp'] <= max_days)].copy()
        
        if calls.empty:
            return None
        
        # Filter to OTM calls only
        otm_calls = calls[calls['strike'] > current_price].copy()
        if otm_calls.empty:
            return None
        
        # Calculate OTM%
        otm_calls['otm_pct'] = ((otm_calls['strike'] - current_price) / current_price) * 100
        otm_calls['otm_diff'] = abs(otm_calls['otm_pct'] - target_otm_pct)
        
        best = otm_calls.loc[otm_calls['otm_diff'].idxmin()]
        
        strike = best['strike']
        bid = best.get('bid', 0) or 0
        ask = best.get('ask', 0) or 0
        mid = (bid + ask) / 2 if bid > 0 else ask
        days = best['days_to_exp']
        
        if mid <= 0 or days <= 0:
            return None
        
        upside = ((strike - current_price) / current_price) * 100
        premium_pct = (mid / current_price) * 100
        annualized = (premium_pct / days) * 365
        
        return {
            'ticker': ticker,
            'current_price': current_price,
            'expiration': best['expiration'],
            'days_to_exp': int(days),
            'strike': strike,
            'bid': bid,
            'ask': ask,
            'premium': round(mid, 2),
            'upside_pct': round(upside, 1),
            'premium_pct': round(premium_pct, 2),
            'annualized_yield': round(annualized, 1),
            'source': chain['source']
        }
    
    def get_deep_itm_put_suggestion(
        self,
        ticker: str,
        current_price: float,
        min_days: int = 21,
        max_days: int = 50,
        target_itm_pct: float = 30.0
    ) -> Optional[Dict]:
        """
        Get deep ITM put suggestion for bearish position.
        """
        chain = self.get_options_chain(ticker, max_days)
        if not chain or chain['puts'].empty:
            return None
        
        puts = chain['puts'].copy()
        
        # Filter by expiration
        puts['exp_date'] = pd.to_datetime(puts['expiration'])
        now = datetime.now()
        puts['days_to_exp'] = (puts['exp_date'] - now).dt.days
        puts = puts[(puts['days_to_exp'] >= min_days) & (puts['days_to_exp'] <= max_days)].copy()
        
        if puts.empty:
            return None
        
        # Filter to ITM puts only (strike > current price)
        itm_puts = puts[puts['strike'] > current_price].copy()
        if itm_puts.empty:
            return None
        
        # Calculate ITM%
        itm_puts['itm_pct'] = ((itm_puts['strike'] - current_price) / current_price) * 100
        
        # Try to find puts with delta ~0.97 (deep ITM)
        if 'delta' in itm_puts.columns:
            itm_puts['abs_delta'] = itm_puts['delta'].abs()
            high_delta = itm_puts[itm_puts['abs_delta'] >= 0.90]
            
            if not high_delta.empty:
                high_delta = high_delta.copy()
                high_delta['delta_diff'] = abs(high_delta['abs_delta'] - 0.97)
                best = high_delta.loc[high_delta['delta_diff'].idxmin()]
            else:
                best = itm_puts.loc[itm_puts['itm_pct'].idxmax()]
        else:
            target_itm = itm_puts[(itm_puts['itm_pct'] >= 25) & (itm_puts['itm_pct'] <= 40)]
            if not target_itm.empty:
                target_itm = target_itm.copy()
                best = target_itm.loc[target_itm['bid'].idxmax()] if 'bid' in target_itm.columns else target_itm.iloc[0]
            else:
                best = itm_puts.loc[itm_puts['itm_pct'].idxmax()]
        
        strike = best['strike']
        bid = best.get('bid', 0) or 0
        ask = best.get('ask', 0) or 0
        mid = (bid + ask) / 2 if bid > 0 else ask
        days = best['days_to_exp']
        itm_pct = best.get('itm_pct', ((strike - current_price) / current_price) * 100)
        
        if mid <= 0 or days <= 0:
            return None
        
        intrinsic = strike - current_price
        time_value = mid - intrinsic if mid > intrinsic else 0
        time_value_pct = (time_value / mid) * 100 if mid > 0 else 0
        
        return {
            'ticker': ticker,
            'current_price': current_price,
            'expiration': best['expiration'],
            'days_to_exp': int(days),
            'strike': strike,
            'bid': bid,
            'ask': ask,
            'mid': round(mid, 2),
            'itm_pct': round(itm_pct, 1),
            'intrinsic': round(intrinsic, 2),
            'time_value': round(time_value, 2),
            'time_value_pct': round(time_value_pct, 1),
            'delta': best.get('delta', 'N/A'),
            'source': chain['source']
        }


# Global instance for easy access
_schwab_client = None

def get_schwab_client() -> SchwabOptions:
    """Get or create the global Schwab client instance."""
    global _schwab_client
    if _schwab_client is None:
        _schwab_client = SchwabOptions()
    return _schwab_client


def get_options_chain(ticker: str, days_out: int = 60) -> Optional[Dict]:
    """Convenience function to get options chain."""
    return get_schwab_client().get_options_chain(ticker, days_out)


def get_covered_call_suggestion(
    ticker: str,
    current_price: float,
    min_days: int = 21,
    max_days: int = 60,
    target_otm_pct: float = 8.0
) -> Optional[Dict]:
    """Convenience function to get covered call suggestion."""
    return get_schwab_client().get_covered_call_suggestion(
        ticker, current_price, min_days, max_days, target_otm_pct
    )


def get_deep_itm_put_suggestion(
    ticker: str,
    current_price: float,
    min_days: int = 21,
    max_days: int = 50,
    target_itm_pct: float = 30.0
) -> Optional[Dict]:
    """Convenience function to get deep ITM put suggestion for shorts."""
    return get_schwab_client().get_deep_itm_put_suggestion(
        ticker, current_price, min_days, max_days, target_itm_pct
    )


# Initial auth helper
def initial_auth():
    """
    Run this once to complete OAuth flow and save tokens.
    
    Usage:
        python -c "from data.schwab_options import initial_auth; initial_auth()"
    """
    if not SCHWAB_AVAILABLE:
        print("❌ Install schwabdev first: pip install schwabdev")
        return
    
    client_id = os.environ.get('SCHWAB_APP_KEY') or os.environ.get('SCHWAB_CLIENT_ID')
    client_secret = os.environ.get('SCHWAB_APP_SECRET') or os.environ.get('SCHWAB_CLIENT_SECRET')
    callback_url = os.environ.get('SCHWAB_CALLBACK_URL', 'https://127.0.0.1:8182/callback')
    tokens_file = _find_tokens_file()
    
    if not client_id or not client_secret:
        print("❌ Set SCHWAB_APP_KEY and SCHWAB_APP_SECRET environment variables")
        return
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                 SCHWAB INITIAL AUTHENTICATION                 ║
╠══════════════════════════════════════════════════════════════╣
║ 1. A browser will open for Schwab login                      ║
║ 2. Log in with your Schwab brokerage credentials             ║
║ 3. Authorize the app                                         ║
║ 4. You'll be redirected to a blank page - that's normal      ║
║ 5. Tokens will be saved to: {tokens_file:<30} ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    try:
        client = schwabdev.Client(
            app_key=client_id,
            app_secret=client_secret,
            callback_url=callback_url,
            tokens_file=tokens_file
        )
        print(f"✅ Authentication successful! Tokens saved to {tokens_file}")
        
        response = client.quotes(['AAPL'])
        if response.status_code == 200:
            print("✅ API test successful - ready to use!")
        else:
            print(f"⚠️  API test returned status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Authentication failed: {e}")


if __name__ == '__main__':
    print("="*60)
    print("Schwab Options Module Test")
    print("="*60)
    
    app_key = os.environ.get('SCHWAB_APP_KEY') or os.environ.get('SCHWAB_CLIENT_ID')
    app_secret = os.environ.get('SCHWAB_APP_SECRET') or os.environ.get('SCHWAB_CLIENT_SECRET')
    tokens_file = _find_tokens_file()
    
    print(f"\nConfiguration:")
    print(f"  SCHWAB_APP_KEY: {'✅ Set' if app_key else '❌ NOT SET'}")
    print(f"  SCHWAB_APP_SECRET: {'✅ Set' if app_secret else '❌ NOT SET'}")
    print(f"  schwabdev installed: {'✅ Yes' if SCHWAB_AVAILABLE else '❌ No'}")
    print(f"  yfinance installed: {'✅ Yes' if YFINANCE_AVAILABLE else '❌ No'}")
    print(f"  Token file: {tokens_file if os.path.exists(tokens_file) else '❌ Not found'}")
    
    print("\nTesting options chain fetch...")
    chain = get_options_chain('AAPL', days_out=45)
    
    if chain:
        print(f"\n✅ Source: {chain['source']}")
        print(f"   Underlying: ${chain['underlying_price']:.2f}")
        print(f"   Calls: {len(chain['calls'])} contracts")
        print(f"   Puts: {len(chain['puts'])} contracts")
    else:
        print("❌ Failed to fetch options chain")

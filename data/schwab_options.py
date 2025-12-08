"""
Schwab API Options Data Module

Provides reliable options chain data from Schwab API.
Falls back to yfinance if Schwab is not configured.

Setup:
1. Create app at https://developer.schwab.com (Market Data Production only)
2. Set callback URL to: https://127.0.0.1:8182
3. Wait for "Ready For Use" status
4. Run initial auth to get refresh token
5. Add to .env:
   SCHWAB_CLIENT_ID=your-app-key
   SCHWAB_CLIENT_SECRET=your-app-secret
   SCHWAB_CALLBACK_URL=https://127.0.0.1:8182
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
        
        client_id = os.environ.get('SCHWAB_CLIENT_ID')
        client_secret = os.environ.get('SCHWAB_CLIENT_SECRET')
        callback_url = os.environ.get('SCHWAB_CALLBACK_URL', 'https://127.0.0.1:8182')
        tokens_file = os.environ.get('SCHWAB_TOKENS_FILE', 'tokens.json')
        
        if not client_id or not client_secret:
            print("⚠️  Schwab credentials not set. Using yfinance fallback.")
            return
        
        try:
            self.client = schwabdev.Client(
                app_key=client_id,
                app_secret=client_secret,
                callback_url=callback_url,
                tokens_file=tokens_file
            )
            self.initialized = True
            print("✅ Schwab API initialized")
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
        Get a covered call suggestion for a stock.
        
        Args:
            ticker: Stock symbol
            current_price: Current stock price
            min_days: Minimum days to expiration
            max_days: Maximum days to expiration
            target_otm_pct: Target % out of the money for strike
            
        Returns:
            Dict with suggestion details or None
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
        
        # Find strike near target OTM %
        target_strike = current_price * (1 + target_otm_pct / 100)
        calls['strike_diff'] = abs(calls['strike'] - target_strike)
        
        # Get best match
        best = calls.loc[calls['strike_diff'].idxmin()]
        
        # Calculate metrics
        strike = best['strike']
        premium = best.get('bid', 0) or best.get('last', 0)
        days = best['days_to_exp']
        
        if premium <= 0 or days <= 0:
            return None
        
        upside_pct = ((strike - current_price) / current_price) * 100
        premium_pct = (premium / current_price) * 100
        annualized = (premium_pct / days) * 365
        
        return {
            'ticker': ticker,
            'current_price': current_price,
            'expiration': best['expiration'],
            'days_to_exp': int(days),
            'strike': strike,
            'premium': premium,
            'upside_pct': round(upside_pct, 1),
            'premium_pct': round(premium_pct, 2),
            'annualized_yield': round(annualized, 1),
            'delta': best.get('delta', 'N/A'),
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
        
        Strategy: Buy deep ITM put (delta ~0.97) for stock replacement on shorts.
        Deep ITM puts move ~1:1 with stock with minimal time decay.
        
        Args:
            ticker: Stock symbol
            current_price: Current stock price
            min_days: Minimum days to expiration
            max_days: Maximum days to expiration
            target_itm_pct: Target % in the money (30% = strike 30% above price)
            
        Returns:
            Dict with put suggestion details or None
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
            # For puts, delta is negative; high abs delta = deep ITM
            itm_puts['abs_delta'] = itm_puts['delta'].abs()
            high_delta = itm_puts[itm_puts['abs_delta'] >= 0.90]
            
            if not high_delta.empty:
                # Get closest to 0.97 delta
                high_delta = high_delta.copy()
                high_delta['delta_diff'] = abs(high_delta['abs_delta'] - 0.97)
                best = high_delta.loc[high_delta['delta_diff'].idxmin()]
            else:
                # No high delta, get deepest ITM
                best = itm_puts.loc[itm_puts['itm_pct'].idxmax()]
        else:
            # No delta data - use ITM% as proxy
            # Target ~30% ITM for delta ~0.97
            target_itm = itm_puts[(itm_puts['itm_pct'] >= 25) & (itm_puts['itm_pct'] <= 40)]
            if not target_itm.empty:
                # Get one with best bid
                target_itm = target_itm.copy()
                best = target_itm.loc[target_itm['bid'].idxmax()] if 'bid' in target_itm.columns else target_itm.iloc[0]
            else:
                # Get deepest available
                best = itm_puts.loc[itm_puts['itm_pct'].idxmax()]
        
        strike = best['strike']
        bid = best.get('bid', 0) or 0
        ask = best.get('ask', 0) or 0
        mid = (bid + ask) / 2 if bid > 0 else ask
        days = best['days_to_exp']
        itm_pct = best.get('itm_pct', ((strike - current_price) / current_price) * 100)
        
        if mid <= 0 or days <= 0:
            return None
        
        # Intrinsic value = strike - current price (for ITM put)
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
        python -c "from schwab_options import initial_auth; initial_auth()"
    """
    if not SCHWAB_AVAILABLE:
        print("❌ Install schwabdev first: pip install schwabdev")
        return
    
    client_id = os.environ.get('SCHWAB_CLIENT_ID')
    client_secret = os.environ.get('SCHWAB_CLIENT_SECRET')
    callback_url = os.environ.get('SCHWAB_CALLBACK_URL', 'https://127.0.0.1:8182')
    
    if not client_id or not client_secret:
        print("❌ Set SCHWAB_CLIENT_ID and SCHWAB_CLIENT_SECRET environment variables")
        return
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                 SCHWAB INITIAL AUTHENTICATION                 ║
╠══════════════════════════════════════════════════════════════╣
║ 1. A browser will open for Schwab login                      ║
║ 2. Log in with your Schwab brokerage credentials             ║
║ 3. Authorize the app                                         ║
║ 4. You'll be redirected to a blank page - that's normal      ║
║ 5. Tokens will be saved to schwab_token.json                 ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    try:
        client = schwabdev.Client(
            app_key=client_id,
            app_secret=client_secret,
            callback_url=callback_url,
            tokens_file='tokens.json'
        )
        print("✅ Authentication successful! Tokens saved to tokens.json")
        
        # Test with a quote
        response = client.quotes(['AAPL'])
        if response.status_code == 200:
            print("✅ API test successful - ready to use!")
        else:
            print(f"⚠️  API test returned status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Authentication failed: {e}")


if __name__ == '__main__':
    # Quick test
    print("Testing options chain fetch...")
    chain = get_options_chain('AAPL', days_out=45)
    
    if chain:
        print(f"\n✅ Source: {chain['source']}")
        print(f"   Underlying: ${chain['underlying_price']:.2f}")
        print(f"   Calls: {len(chain['calls'])} contracts")
        print(f"   Puts: {len(chain['puts'])} contracts")
        
        # Test covered call suggestion
        suggestion = get_covered_call_suggestion('AAPL', chain['underlying_price'])
        if suggestion:
            print(f"\n📞 Covered Call Suggestion for AAPL:")
            print(f"   Expiration: {suggestion['expiration']} ({suggestion['days_to_exp']} days)")
            print(f"   Strike: ${suggestion['strike']:.2f} ({suggestion['upside_pct']:+.1f}% OTM)")
            print(f"   Premium: ${suggestion['premium']:.2f} ({suggestion['premium_pct']:.2f}%)")
            print(f"   Annualized: {suggestion['annualized_yield']:.1f}%")
    else:
        print("❌ Failed to fetch options chain")

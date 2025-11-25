"""
Hybrid data handler: CoinGecko for crypto, Yahoo Finance for stocks
Includes PSAR anomaly detection to flag suspicious data
"""
import yfinance as yf
import requests
from typing import Dict, Optional, Tuple
import pandas as pd
import time

class CryptoDataHandler:
    """Handle crypto data from CoinGecko API (free tier, no key needed)"""
    
    CRYPTO_MAP = {
        'BTC-USD': 'bitcoin',
        'ETH-USD': 'ethereum',
        'SOL-USD': 'solana',
        'SUI20947-USD': 'sui'
    }
    
    @classmethod
    def is_crypto(cls, ticker: str) -> bool:
        """Check if ticker is a known crypto"""
        return ticker in cls.CRYPTO_MAP
    
    @classmethod
    def get_crypto_data(cls, ticker: str, period: str = '60d') -> Optional[pd.DataFrame]:
        """
        Fetch crypto data from CoinGecko
        Returns DataFrame matching yfinance format
        """
        if ticker not in cls.CRYPTO_MAP:
            return None
        
        coin_id = cls.CRYPTO_MAP[ticker]
        
        # Map period to days
        days_map = {
            '60d': 60,
            '90d': 90,
            '1y': 365,
            '2y': 730
        }
        days = days_map.get(period, 60)
        
        try:
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
            params = {
                'vs_currency': 'usd',
                'days': days,
                'interval': 'daily'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Convert to DataFrame matching yfinance format
            prices = data['prices']
            df = pd.DataFrame(prices, columns=['timestamp', 'Close'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # CoinGecko doesn't provide OHLC in free tier, so we approximate
            # This is acceptable for PSAR which primarily uses Close prices
            df['Open'] = df['Close']
            df['High'] = df['Close'] * 1.005  # Approximate 0.5% daily range
            df['Low'] = df['Close'] * 0.995
            df['Volume'] = 0  # Not available in free tier
            
            return df[['Open', 'High', 'Low', 'Close', 'Volume']]
            
        except Exception as e:
            print(f"CoinGecko fetch error for {ticker}: {e}")
            return None
    
    @classmethod
    def get_current_price(cls, ticker: str) -> Optional[float]:
        """Get current price for crypto ticker"""
        if ticker not in cls.CRYPTO_MAP:
            return None
        
        coin_id = cls.CRYPTO_MAP[ticker]
        
        try:
            url = f"https://api.coingecko.com/api/v3/simple/price"
            params = {
                'ids': coin_id,
                'vs_currencies': 'usd'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return data[coin_id]['usd']
            
        except Exception as e:
            print(f"CoinGecko price error for {ticker}: {e}")
            return None


class PSARValidator:
    """Validate PSAR calculations to detect data quality issues"""
    
    @staticmethod
    def detect_psar_anomaly(ticker: str, price: float, psar: float, prev_psar: Optional[float] = None) -> Tuple[bool, Optional[str]]:
        """
        Detect suspicious PSAR values that indicate data problems
        
        Returns: (is_anomaly, warning_message)
        """
        if not price or not psar:
            return False, None
        
        # Check 1: PSAR distance > 15% (extremely rare in stable data)
        distance_pct = abs((price - psar) / price) * 100
        if distance_pct > 15:
            return True, f"{ticker}: PSAR {distance_pct:.1f}% away from price (likely data issue)"
        
        # Check 2: PSAR jump > 10% between scans (indicates missing/bad data)
        if prev_psar:
            psar_jump = abs((psar - prev_psar) / prev_psar) * 100
            if psar_jump > 10:
                return True, f"{ticker}: PSAR jumped {psar_jump:.1f}% since last scan (data quality issue)"
        
        return False, None


class HybridDataFetcher:
    """Unified interface: CoinGecko for crypto, Yahoo for stocks"""
    
    @staticmethod
    def get_data(ticker: str, period: str = '60d') -> Optional[pd.DataFrame]:
        """
        Fetch data from appropriate source
        - CoinGecko for crypto (better data quality)
        - Yahoo Finance for stocks
        """
        # Try CoinGecko first for known crypto
        if CryptoDataHandler.is_crypto(ticker):
            print(f"  Fetching {ticker} from CoinGecko...")
            df = CryptoDataHandler.get_crypto_data(ticker, period)
            if df is not None:
                return df
            print(f"  CoinGecko failed, falling back to Yahoo...")
        
        # Fall back to Yahoo Finance
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period)
            if df.empty:
                return None
            return df
        except Exception as e:
            print(f"  Yahoo fetch error for {ticker}: {e}")
            return None
    
    @staticmethod
    def get_current_price(ticker: str) -> Optional[float]:
        """Get current price from appropriate source"""
        if CryptoDataHandler.is_crypto(ticker):
            price = CryptoDataHandler.get_current_price(ticker)
            if price:
                return price
        
        # Fall back to Yahoo
        try:
            stock = yf.Ticker(ticker)
            data = stock.history(period='1d')
            if not data.empty:
                return data['Close'].iloc[-1]
        except:
            pass
        
        return None


# Example usage
if __name__ == "__main__":
    # Test crypto fetch
    print("Testing BTC data fetch...")
    df = HybridDataFetcher.get_data('BTC-USD')
    if df is not None:
        print(f"Retrieved {len(df)} days of BTC data")
        print(f"Latest close: ${df['Close'].iloc[-1]:,.2f}")
    
    # Test current price
    price = HybridDataFetcher.get_current_price('BTC-USD')
    print(f"Current BTC price: ${price:,.2f}")
    
    # Test anomaly detection
    validator = PSARValidator()
    is_anomaly, msg = validator.detect_psar_anomaly('BTC-USD', 96000, 88573)
    print(f"Anomaly detected: {is_anomaly}, Message: {msg}")

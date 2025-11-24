# config.py
import os
import pandas as pd

# =============================================================================
# DATA CONFIGURATION
# =============================================================================

DATA_CONFIG = {
    'history_period': '6mo',      # How much history to fetch
    'min_data_points': 50         # Minimum days of data required
}

# =============================================================================
# INDICATOR THRESHOLDS
# =============================================================================

INDICATOR_THRESHOLDS = {
    'rsi_oversold': 30,
    'stoch_oversold': 20,
    'willr_oversold': -80,
    'bb_distance_pct': 0.02,      # Price within 2% of lower band
}

# =============================================================================
# PSAR SETTINGS
# =============================================================================

PSAR_CONFIG = {
    'iaf': 0.02,      # Initial Acceleration Factor
    'maxaf': 0.2      # Maximum Acceleration Factor
}

# =============================================================================
# ALERT SETTINGS
# =============================================================================

ALERT_ON_ENTRY = True        # Alert when a stock ENTERS a Buy signal
ALERT_ON_EXIT = True         # Alert when a stock EXITS a Buy signal
ALERT_DAILY_SUMMARY = True   # Send a summary email even if no changes
INCLUDE_EXCEL_ATTACHMENT = False # Disable Excel attachment for market scanner
INCLUDE_SELL_SIGNALS = True  # Include sell signals in reports

# =============================================================================
# EMAIL CONFIGURATION
# =============================================================================

EMAIL_CONFIG = {
    'sender_email': os.environ.get('GMAIL_EMAIL', ''),
    'sender_password': os.environ.get('GMAIL_PASSWORD', ''),
    'recipient_email': os.environ.get('RECIPIENT_EMAIL', ''),
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587
}

# =============================================================================
# TICKER LIST MANAGEMENT
# =============================================================================

def get_all_tickers():
    """Fetches all stock tickers from CSV files located in the script directory."""
    all_tickers = set()
    ticker_sources = {}

    # Get the directory where this script (config.py) is located
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Broad Market Indices
    # Dictionary mapping Source Name -> Filename
    market_files = {
        'S&P 500': 'sp500_tickers.csv',
        'NASDAQ 100': 'nasdaq100_tickers.csv',
        'Russell 2000': 'russell2000_tickers.csv'
    }

    print("Loading market tickers...")
    for source, filename in market_files.items():
        csv_path = os.path.join(BASE_DIR, filename)
        if os.path.exists(csv_path):
            try:
                # specific handling for Russell 2000 which usually has a 'Ticker' column
                # others might have 'Symbol'
                df = pd.read_csv(csv_path)
                
                # Determine which column holds the ticker
                col_name = 'Symbol'
                if 'Ticker' in df.columns:
                    col_name = 'Ticker'
                elif 'Symbol' not in df.columns:
                    # Fallback: grab the first column
                    col_name = df.columns[0]

                tickers = df[col_name].dropna().astype(str).tolist()
                
                # Clean tickers (remove whitespace)
                tickers = [t.strip() for t in tickers if t.strip()]
                
                all_tickers.update(tickers)
                print(f"  ✓ Got {len(tickers)} {source} tickers from {filename}")
                
                for t in tickers:
                    ticker_sources.setdefault(t, []).append(source)
            except Exception as e:
                print(f"  ✗ Failed to read {filename}: {e}")
        else:
            # Only warn if it's not the standard indices (optional)
            pass

    # 2. IBD Lists
    ibd_list_names = ['ibd_50', 'ibd_bigcap20', 'ibd_ipo', 'ibd_spotlight', 'ibd_sector']
    
    print("Checking for IBD CSV files...")
    for list_name in ibd_list_names:
        filename = f"{list_name}.csv"
        csv_path = os.path.join(BASE_DIR, filename)
        
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path)
                # Assume 'Symbol' is the column name for IBD lists
                col_name = 'Symbol' if 'Symbol' in df.columns else df.columns[0]
                
                tickers = df[col_name].dropna().astype(str).tolist()
                tickers = [t.strip() for t in tickers if t.strip()]
                
                all_tickers.update(tickers)
                print(f"  ✓ Found {filename} ({len(tickers)} stocks)")
                
                source_name = list_name.replace('ibd_', '').upper()
                for t in tickers:
                    ticker_sources.setdefault(t, []).append(f"IBD {source_name}")
            except Exception as e:
                print(f"  ✗ Failed to read {filename}: {e}")

    # 3. Add Crypto and Indices (Hardcoded)
    crypto_indices = ['BTC-USD', 'ETH-USD', '^GSPC', '^NDX', '^RUT']
    all_tickers.update(crypto_indices)
    print("Adding crypto and indices...")
    for t in crypto_indices:
        ticker_sources.setdefault(t, []).append('Crypto/Index')
    
    # Final Cleanup
    # Remove any None, empty strings, or headers that got sneaking in
    all_tickers.discard(None)
    all_tickers.discard('')
    all_tickers.discard('Symbol')
    all_tickers.discard('Ticker')
    
    return list(all_tickers), ticker_sources

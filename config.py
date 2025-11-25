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
    ibd_stats = {}  # NEW: Store IBD ratings and stats

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
                print(f"  [OK] Got {len(tickers)} {source} tickers from {filename}")
                
                for t in tickers:
                    ticker_sources.setdefault(t, []).append(source)
            except Exception as e:
                print(f"  [FAIL] Failed to read {filename}: {e}")
        else:
            # Only warn if it's not the standard indices (optional)
            pass

    # 2. IBD Lists (with enhanced stats)
    ibd_list_names = ['ibd_50', 'ibd_bigcap20', 'ibd_ipo', 'ibd_spotlight', 'ibd_sector']
    
    print("Checking for IBD CSV files...")
    for list_name in ibd_list_names:
        filename = f"{list_name}.csv"
        csv_path = os.path.join(BASE_DIR, filename)
        
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path)
                
                # Assume 'Symbol' is the column name
                col_name = 'Symbol' if 'Symbol' in df.columns else df.columns[0]
                
                tickers = df[col_name].dropna().astype(str).tolist()
                tickers = [t.strip() for t in tickers if t.strip()]
                
                all_tickers.update(tickers)
                print(f"  [OK] Found {filename} ({len(tickers)} stocks)")
                
                source_name = list_name.replace('ibd_', '').upper()
                
                # Extract IBD stats for each ticker
                for idx, row in df.iterrows():
                    ticker = str(row.get(col_name, '')).strip()
                    if not ticker:
                        continue
                    
                    # Store all IBD stats
                    ibd_stats[ticker] = {
                        'Company': row.get('Company', 'N/A'),
                        'Composite': row.get('Composite', 'N/A'),
                        'EPS': row.get('EPS', 'N/A'),
                        'RS': row.get('RS', 'N/A'),
                        'GroupRS': row.get('GroupRS', 'N/A'),
                        'SMR': row.get('SMR', 'N/A'),
                        'AccDis': row.get('AccDis', 'N/A'),
                        'OffHigh': row.get('OffHigh', 'N/A'),
                        'Price_IBD': row.get('Price', 'N/A'),
                        'Day50': row.get('Day50', 'N/A'),
                        'Vol': row.get('Vol', 'N/A'),
                        'BuyPoint': row.get('BuyPoint', 'N/A'),  # If you add this column
                        'Comment': row.get('Comment', ''),        # If you add this column
                        'IBD_List': f"IBD {source_name}"
                    }
                    
                    ticker_sources.setdefault(ticker, []).append(f"IBD {source_name}")
                    
            except Exception as e:
                print(f"  [FAIL] Failed to read {filename}: {e}")

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
    
    print(f"\n✓ Loaded {len(ibd_stats)} stocks with IBD stats")
    
    return list(all_tickers), ticker_sources, ibd_stats

# ============================================
# NEW SETTINGS FOR UPDATED SCANNER
# ============================================

# Custom watchlist
CUSTOM_WATCHLIST_PATH = 'custom_watchlist.txt'

# Table limits for email report
TABLE_LIMIT_PSAR = 50
TABLE_LIMIT_EARLY = 50
TABLE_LIMIT_DIVIDEND = 50
TABLE_LIMIT_EXITS = None  # No limit on exits - show all

# Dividend filters
MIN_DIVIDEND_YIELD = 1.5  # Minimum 1.5% yield to show in dividend table

# Use live ticker lists (fallback to CSV if fails)
USE_LIVE_TICKER_LISTS = True



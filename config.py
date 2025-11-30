import os
import pandas as pd
import warnings

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
# ROBUST FILE LOADER
# =============================================================================

def load_stock_file(path):
    """
    Robustly load a stock file, handling CSVs with different encodings
    AND Excel files masquerading as CSVs (0xd0 error).
    """
    if not os.path.exists(path):
        return None

    # 1. Try reading as a standard CSV (UTF-8)
    try:
        return pd.read_csv(path, encoding='utf-8')
    except (UnicodeDecodeError, pd.errors.ParserError):
        pass

    # 2. Try reading as Windows encoded CSV (Common for Excel-saved CSVs)
    try:
        return pd.read_csv(path, encoding='cp1252')
    except (UnicodeDecodeError, pd.errors.ParserError):
        pass

    # 3. Try reading as an Excel file (Fix for 0xd0 error / binary files)
    # Even if named .csv, it might be an .xls or .xlsx
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return pd.read_excel(path)
    except Exception:
        pass
        
    print(f"  ✗ Could not read file format: {os.path.basename(path)}")
    return None

def get_column_data(df, file_type='Generic'):
    """Extract tickers from a dataframe regardless of column names."""
    if df is None or df.empty:
        return []
    
    # List of possible column names for the ticker symbol
    possible_names = ['Symbol', 'Ticker', 'Stock', 'Company Symbol']
    
    col_name = None
    for name in possible_names:
        if name in df.columns:
            col_name = name
            break
            
    # Fallback: Use the first column if no known name matches
    if col_name is None:
        col_name = df.columns[0]
        
    # Clean data: drop NAs, convert to string, strip whitespace
    tickers = df[col_name].dropna().astype(str).str.strip().tolist()
    
    # Filter out garbage (headers repeated, empty strings)
    valid_tickers = [t for t in tickers if t and t.upper() not in possible_names and len(t) < 10]
    
    return valid_tickers

# =============================================================================
# TICKER LIST MANAGEMENT
# =============================================================================

def get_all_tickers():
    """Fetches all stock tickers from files located in the script directory."""
    all_tickers = set()
    ticker_sources = {}

    # Get the directory where this script (config.py) is located
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Broad Market Indices
    market_files = {
        'S&P 500': 'sp500_tickers.csv',
        'NASDAQ 100': 'nasdaq100_tickers.csv',
        'Russell 2000': 'russell2000_tickers.csv'
    }

    print("Loading market tickers...")
    for source, filename in market_files.items():
        csv_path = os.path.join(BASE_DIR, filename)
        df = load_stock_file(csv_path)
        
        if df is not None:
            tickers = get_column_data(df, source)
            all_tickers.update(tickers)
            print(f"  ✓ Got {len(tickers)} {source} tickers from {filename}")
            
            for t in tickers:
                ticker_sources.setdefault(t, []).append(source)
        else:
            # Only warn if it's not the standard indices (optional)
            pass

    # 2. IBD Lists
    ibd_list_names = ['ibd_50', 'ibd_bigcap20', 'ibd_ipo', 'ibd_spotlight', 'ibd_sector']
    
    print("Checking for IBD CSV files...")
    for list_name in ibd_list_names:
        filename = f"{list_name}.csv"
        csv_path = os.path.join(BASE_DIR, filename)
        
        # Use the robust loader to handle the 0xd0/binary error
        df = load_stock_file(csv_path)
        
        if df is not None:
            tickers = get_column_data(df, list_name)
            all_tickers.update(tickers)
            print(f"  ✓ Found {filename} ({len(tickers)} stocks)")
            
            source_name = list_name.replace('ibd_', '').upper()
            for t in tickers:
                ticker_sources.setdefault(t, []).append(f"IBD {source_name}")

    # 3. Add Crypto and Indices (Hardcoded)
    crypto_indices = ['BTC-USD', 'ETH-USD', '^GSPC', '^NDX', '^RUT']
    all_tickers.update(crypto_indices)
    print("Adding crypto and indices...")
    for t in crypto_indices:
        ticker_sources.setdefault(t, []).append('Crypto/Index')
    
    # Final Cleanup
    all_tickers.discard(None)
    all_tickers.discard('')
    
    # FIX: Return EXACTLY 2 values to match market_scanner.py expectation
    return list(all_tickers), ticker_sources

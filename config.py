import os
import pandas as pd
import warnings

# =============================================================================
# CONFIGURATION SETTINGS
# =============================================================================
DATA_CONFIG = {'history_period': '6mo', 'min_data_points': 50}

INDICATOR_THRESHOLDS = {
    'rsi_oversold': 30, 'stoch_oversold': 20, 'willr_oversold': -80, 'bb_distance_pct': 0.02
}

PSAR_CONFIG = {'iaf': 0.02, 'maxaf': 0.2}

ALERT_ON_ENTRY = True
ALERT_ON_EXIT = True
ALERT_DAILY_SUMMARY = True

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
    """Robustly load a stock file, handling CSVs AND Excel files masked as CSVs."""
    if not os.path.exists(path):
        return None

    # 1. Try standard CSV
    try: return pd.read_csv(path, encoding='utf-8')
    except: pass

    # 2. Try Windows CSV
    try: return pd.read_csv(path, encoding='cp1252')
    except: pass

    # 3. Try Excel (Fixes IBD file error)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return pd.read_excel(path)
    except: pass
        
    print(f"  ✗ Could not read file format: {os.path.basename(path)}")
    return None

def get_column_data(df):
    """Extract tickers from a dataframe."""
    if df is None or df.empty: return []
    for name in ['Symbol', 'Ticker', 'Stock', 'Company Symbol']:
        if name in df.columns:
            return df[name].dropna().astype(str).str.strip().tolist()
    return df.iloc[:, 0].dropna().astype(str).str.strip().tolist()

def get_all_tickers():
    all_tickers = set()
    ticker_sources = {}
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Broad Market
    market_files = {
        'S&P 500': 'sp500_tickers.csv',
        'NASDAQ 100': 'nasdaq100_tickers.csv',
        'Russell 2000': 'russell2000_tickers.csv'
    }

    print("Loading market tickers...")
    for source, filename in market_files.items():
        path = os.path.join(BASE_DIR, filename)
        df = load_stock_file(path)
        if df is not None:
            tickers = get_column_data(df)
            all_tickers.update(tickers)
            print(f"  ✓ Got {len(tickers)} {source} tickers")
            for t in tickers: ticker_sources.setdefault(t, []).append(source)

    # 2. IBD Lists
    print("Checking for IBD files...")
    ibd_list_names = ['ibd_50', 'ibd_bigcap20', 'ibd_ipo', 'ibd_spotlight', 'ibd_sector']
    for list_name in ibd_list_names:
        filename = f"{list_name}.csv"
        path = os.path.join(BASE_DIR, filename)
        df = load_stock_file(path)
        if df is not None:
            tickers = get_column_data(df)
            all_tickers.update(tickers)
            print(f"  ✓ Found {filename} ({len(tickers)} stocks)")
            source_tag = f"IBD {list_name.replace('ibd_', '').upper()}"
            for t in tickers: ticker_sources.setdefault(t, []).append(source_tag)

    # 3. Crypto
    crypto = ['BTC-USD', 'ETH-USD', '^GSPC', '^NDX', '^RUT']
    all_tickers.update(crypto)
    for t in crypto: ticker_sources.setdefault(t, []).append('Index')
    
    return list(all_tickers), ticker_sources

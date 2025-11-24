#!/usr/bin/env python3
"""
Configuration for Market-Wide PSAR Scanner
Scans IBD, S&P 500, NASDAQ 100, Russell 1000, and major indices
"""

import os
import requests
import pandas as pd
from io import StringIO

# =============================================================================
# STOCK LISTS - BROAD MARKET
# =============================================================================

def get_sp500_tickers():
    """Get S&P 500 tickers from multiple sources with proper fallback chain"""
    
    # Method 1: Try local CSV file first (most reliable)
    try:
        if os.path.exists('sp500_tickers.csv'):
            print("  Fetching S&P 500 from CSV file...")
            df = pd.read_csv('sp500_tickers.csv')
            # Handle different possible column names
            symbol_col = None
            for col in ['Symbol', 'Ticker', 'symbol', 'ticker']:
                if col in df.columns:
                    symbol_col = col
                    break
            if symbol_col:
                tickers = df[symbol_col].str.replace('.', '-').tolist()
                print(f"  ✓ Got {len(tickers)} S&P 500 tickers from CSV")
                return tickers
    except Exception as e:
        print(f"  ✗ CSV failed: {e}")
    
    # Method 2: Try Slickcharts (more reliable than Wikipedia)
    try:
        print("  Fetching S&P 500 from Slickcharts...")
        url = 'https://www.slickcharts.com/sp500'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        tables = pd.read_html(response.text)
        df = tables[0]
        tickers = df['Symbol'].str.replace('.', '-').tolist()
        print(f"  ✓ Got {len(tickers)} S&P 500 tickers from Slickcharts")
        return tickers
    except Exception as e:
        print(f"  ✗ Slickcharts failed: {e}")
    
    # Method 3: Try Wikipedia with better headers
    try:
        print("  Fetching S&P 500 from Wikipedia...")
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        tables = pd.read_html(response.text)
        df = tables[0]
        tickers = df['Symbol'].str.replace('.', '-').tolist()
        print(f"  ✓ Got {len(tickers)} S&P 500 tickers from Wikipedia")
        return tickers
    except Exception as e:
        print(f"  ✗ Wikipedia failed: {e}")
    
    # Method 4: Hardcoded fallback - expanded to 250 stocks
    print("  → Using expanded hardcoded fallback (250 stocks)...")
    return [
        # Mega caps (Top 50)
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B',
        'LLY', 'AVGO', 'JPM', 'V', 'UNH', 'XOM', 'MA', 'COST', 'HD', 'PG',
        'JNJ', 'NFLX', 'BAC', 'ABBV', 'CVX', 'CRM', 'KO', 'MRK', 'WMT',
        'AMD', 'PEP', 'TMO', 'CSCO', 'ACN', 'MCD', 'LIN', 'ABT', 'DHR',
        'ADBE', 'INTC', 'DIS', 'CMCSA', 'NKE', 'VZ', 'TXN', 'WFC', 'PM',
        'ORCL', 'QCOM', 'INTU', 'IBM', 'AMGN',
        # Large caps (51-150)
        'HON', 'UNP', 'RTX', 'CAT', 'GE', 'AMAT', 'LOW', 'SPGI', 'MS', 'BA',
        'ELV', 'NEE', 'BKNG', 'BLK', 'DE', 'AXP', 'GS', 'SYK', 'SBUX', 'TJX',
        'MDT', 'GILD', 'MMC', 'LRCX', 'ADI', 'ADP', 'MDLZ', 'CVS', 'AMT', 'VRTX',
        'PLD', 'REGN', 'CI', 'C', 'ISRG', 'ZTS', 'BMY', 'MO', 'SO', 'CB',
        'DUK', 'BDX', 'SHW', 'SCHW', 'ETN', 'PNC', 'TMUS', 'NOC', 'BSX', 'EOG',
        'CME', 'EQIX', 'APH', 'USB', 'ITW', 'COP', 'MCO', 'HCA', 'MMM', 'ICE',
        'NSC', 'WM', 'PYPL', 'EMR', 'FCX', 'AON', 'TGT', 'PGR', 'FI', 'MU',
        'PSA', 'SLB', 'MCK', 'APD', 'F', 'GM', 'JCI', 'FDX', 'KLAC', 'SNPS',
        'CDNS', 'MAR', 'AIG', 'CSX', 'MRVL', 'ORLY', 'PANW', 'ROP', 'MSI', 'AJG',
        'TT', 'CARR', 'PCAR', 'AFL', 'AZO', 'ADSK', 'NXPI', 'WELL', 'O', 'CPRT',
        # Mid-large caps (151-250)
        'GWW', 'TRV', 'SRE', 'CTAS', 'PAYX', 'CL', 'CMG', 'HLT', 'D', 'ROST',
        'AEP', 'SPG', 'TEL', 'MSCI', 'ALL', 'BK', 'KMI', 'ODFL', 'FTNT', 'PRU',
        'KHC', 'CTVA', 'YUM', 'EA', 'FAST', 'EW', 'A', 'VRSK', 'GIS', 'CEG',
        'DD', 'IT', 'HSY', 'KMB', 'GEHC', 'IDXX', 'MCHP', 'EXC', 'XEL', 'DXCM',
        'OTIS', 'GLW', 'CTSH', 'DOW', 'VMC', 'HES', 'PWR', 'MLM', 'WBD', 'KEYS',
        'IQV', 'ACGL', 'ROK', 'CHD', 'WEC', 'PPG', 'CBRE', 'MTD', 'MPWR', 'FTV',
        'AVB', 'CDW', 'FANG', 'EIX', 'HWM', 'TRGP', 'IRM', 'BIIB', 'DLR', 'APTV',
        'WST', 'CSGP', 'VICI', 'DAL', 'STZ', 'LH', 'DLTR', 'UAL', 'EQR', 'AWK',
        'RSG', 'TROW', 'HPQ', 'ES', 'LVS', 'FITB', 'WY', 'COF', 'MTB', 'ARE',
        'RMD', 'ZBH', 'NTRS', 'EBAY', 'BALL', 'TDG', 'CF', 'HBAN', 'WAB', 'VTR'
    ]

def get_nasdaq100_tickers():
    """Get NASDAQ 100 tickers from multiple sources with proper fallback chain"""
    
    # Method 1: Try local CSV file first
    try:
        if os.path.exists('nasdaq100_tickers.csv'):
            print("  Fetching NASDAQ 100 from CSV file...")
            df = pd.read_csv('nasdaq100_tickers.csv')
            symbol_col = None
            for col in ['Symbol', 'Ticker', 'symbol', 'ticker']:
                if col in df.columns:
                    symbol_col = col
                    break
            if symbol_col:
                tickers = df[symbol_col].tolist()
                print(f"  ✓ Got {len(tickers)} NASDAQ 100 tickers from CSV")
                return tickers
    except Exception as e:
        print(f"  ✗ CSV failed: {e}")
    
    # Method 2: Try Slickcharts
    try:
        print("  Fetching NASDAQ 100 from Slickcharts...")
        url = 'https://www.slickcharts.com/nasdaq100'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        tables = pd.read_html(response.text)
        df = tables[0]
        tickers = df['Symbol'].tolist()
        print(f"  ✓ Got {len(tickers)} NASDAQ 100 tickers from Slickcharts")
        return tickers
    except Exception as e:
        print(f"  ✗ Slickcharts failed: {e}")
    
    # Method 3: Try Wikipedia with better headers
    try:
        print("  Fetching NASDAQ 100 from Wikipedia...")
        url = 'https://en.wikipedia.org/wiki/NASDAQ-100'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) APpleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        tables = pd.read_html(response.text)
        df = tables[4]
        tickers = df['Ticker'].tolist()
        print(f"  ✓ Got {len(tickers)} NASDAQ 100 tickers from Wikipedia")
        return tickers
    except Exception as e:
        print(f"  ✗ Wikipedia failed: {e}")
    
    # Method 4: Hardcoded fallback - complete NASDAQ 100
    print("  → Using complete hardcoded fallback (100+ stocks)...")
    return [
        # Top 20
        'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'NVDA', 'META', 'TSLA',
        'AVGO', 'COST', 'NFLX', 'AMD', 'PEP', 'CSCO', 'ADBE', 'TMUS',
        'INTU', 'TXN', 'QCOM', 'CMCSA',
        # Next 30
        'AMGN', 'HON', 'AMAT', 'SBUX', 'PANW', 'ADP', 'GILD', 'VRTX',
        'ADI', 'LRCX', 'REGN', 'ISRG', 'BKNG', 'MU', 'SNPS', 'KLAC',
        'INTC', 'PYPL', 'CDNS', 'MELI', 'CRWD', 'ORLY', 'FTNT', 'MRVL',
        'CTAS', 'DASH', 'MNST', 'WDAY', 'DXCM', 'ABNB',
        # Next 30
        'CHTR', 'NXPI', 'TTD', 'TEAM', 'PCAR', 'PAYX', 'IDXX', 'CPRT',
        'ODFL', 'AZN', 'KDP', 'FAST', 'ROST', 'BKR', 'GEHC', 'EA',
        'CTSH', 'VRSK', 'DDOG', 'EXC', 'XEL', 'KHC', 'ZS', 'FANG',
        'CSGP', 'CCEP', 'ANSS', 'CDW', 'ON', 'BIIB',
        # Remaining 20+
        'WBD', 'MDB', 'ILMN', 'GFS', 'MCHP', 'DLTR', 'WBA', 'MRNA',
        'SMCI', 'ARM', 'ALGN', 'SIRI', 'TTWO', 'RIVN', 'LCID', 'ZM',
        'HOOD', 'RBLX', 'COIN', 'PLTR', 'SNOW'
    ]

def get_russell1000_additional():
    """Get additional Russell 1000 stocks not in S&P 500"""
    # Subset of Russell 1000 - major mid-caps
    return [
        'ABNB', 'BILL', 'BROS', 'COIN', 'CRWD', 'DASH', 'DDOG', 'DT',
        'FTNT', 'HUBS', 'IOT', 'MDB', 'NET', 'OKTA', 'PANW', 'PATH',
        'RIOT', 'RIVN', 'RBLX', 'SHOP', 'SNOW', 'SQ', 'TEAM', 'TTD',
        'TWLO', 'U', 'UBER', 'WDAY', 'ZM', 'ZS'
    ]

def get_russell2000_tickers():
    """Get Russell 2000 tickers from multiple sources"""
    
    # Method 1: Try local CSV file first
    try:
        if os.path.exists('russell2000_tickers.csv'):
            print("  Fetching Russell 2000 from CSV file...")
            df = pd.read_csv('russell2000_tickers.csv')
            symbol_col = None
            for col in ['Symbol', 'Ticker', 'symbol', 'ticker']:
                if col in df.columns:
                    symbol_col = col
                    break
            if symbol_col:
                tickers = df[symbol_col].str.replace('.', '-').tolist()
                print(f"  ✓ Got {len(tickers)} Russell 2000 tickers from CSV")
                return tickers
    except Exception as e:
        print(f"  ✗ CSV failed: {e}")
    
    # Method 2: Try iShares IWM holdings (official Russell 2000 ETF)
    try:
        print("  Fetching Russell 2000 from iShares IWM holdings...")
        url = 'https://www.ishares.com/us/products/239710/ishares-russell-2000-etf'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        # This would need additional parsing - skip for now
        raise Exception("iShares parsing not implemented yet")
    except Exception as e:
        print(f"  ✗ iShares failed: {e}")
    
    # Method 3: Hardcoded fallback - top 200 Russell 2000 stocks
    print("  → Using hardcoded fallback (200 top Russell 2000 stocks)...")
    return [
        # Small cap growth leaders
        'SMCI', 'CELH', 'DECK', 'CAVA', 'APP', 'CWAN', 'CVNA', 'FOUR', 
        'BROS', 'RBLX', 'SNOW', 'GTLB', 'IOT', 'PCVX', 'HIMS', 'COIN',
        'IBKR', 'SFM', 'EXAS', 'RYAN', 'PCOR', 'LITE', 'MKSI', 'ENTG',
        # Small cap value/dividend
        'OGE', 'PNW', 'NWE', 'AVA', 'CWEN', 'BKH', 'SJW', 'AWR', 'YORW',
        'NJR', 'SR', 'MGEE', 'UTL', 'OTTR', 'CNS', 'CWT', 'GEF', 'TRNO',
        # REITs
        'MAC', 'KRG', 'VNO', 'SLG', 'BXP', 'HIW', 'DEI', 'JBGS', 'PDM',
        'ESRT', 'HPP', 'PGRE', 'AKR', 'BRX', 'UE', 'WHL', 'ROIC', 'GTY',
        # Financials  
        'EWBC', 'WAL', 'CATY', 'BANR', 'CVBF', 'PNFP', 'THFF', 'UMBF',
        'CBSH', 'FFIN', 'HWC', 'FULT', 'CADE', 'TCBI', 'FFNW', 'SBCF',
        # Industrials
        'STRL', 'GVA', 'PATK', 'ARCB', 'SAIA', 'WERN', 'JBHT', 'CHRW',
        'KNX', 'MATX', 'HRI', 'HUBG', 'MRTN', 'ECHO', 'SNDR', 'HTLD',
        # Technology
        'TENB', 'DOMO', 'NCNO', 'DOCN', 'BRZE', 'ALRM', 'PRGS', 'APPF',
        'JAMF', 'BLKB', 'QLYS', 'MGNI', 'PUBM', 'COUP', 'ZUO', 'BILL',
        # Healthcare
        'LEGN', 'PRCT', 'CORT', 'KRYS', 'TMDX', 'OUST', 'IRTC', 'PRVA',
        'GKOS', 'ATRC', 'TNDM', 'PODD', 'AXNX', 'SRRK', 'TVTX', 'CGEM',
        # Consumer
        'SHAK', 'TXRH', 'BLMN', 'CBRL', 'DIN', 'FWRG', 'CAKE', 'BJRI',
        'CHUY', 'RUTH', 'PLAY', 'WING', 'EAT', 'TACO', 'LOCO', 'PZZA',
        # Energy
        'NOG', 'MTDR', 'SM', 'MGY', 'PR', 'CIVI', 'GPOR', 'REI',
        'CRGY', 'CPE', 'RRC', 'CTRA', 'CHRD', 'VTLE', 'PBF', 'NINE',
        # Materials
        'CENX', 'SXC', 'MP', 'HL', 'KALU', 'CRS', 'MTRN', 'MATW',
        'CMC', 'RS', 'ZEUS', 'WOR', 'MLI', 'SLVM', 'HAYN', 'ROCK'
    ]

def get_crypto_and_indices():
    """Get major crypto and market indices"""
    return {
        'crypto': ['BTC-USD', 'ETH-USD', 'SOL-USD', 'AVAX-USD'],
        'indices': ['SPY', 'QQQ', 'DIA', 'IWM', 'MDY', 'VTI']
    }

def get_ibd_from_csv():
    """
    Get IBD lists from CSV files if available
    Place CSV files in the same directory:
    - ibd_50.csv
    - ibd_bigcap20.csv
    - ibd_ipo.csv
    - ibd_spotlight.csv
    - ibd_sector.csv
    """
    ibd_lists = {}
    
    # Check for both CSV and XLS files
    files_to_check = {
        'ibd_50': ['ibd_50.csv', 'IBD_50.xls', 'ibd_50.xls'],
        'ibd_bigcap': ['ibd_bigcap20.csv', 'BIG_CAP_20.xls', 'ibd_bigcap20.xls'],
        'ibd_ipo': ['ibd_ipo.csv', 'IPO_LEADERS.xls', 'ibd_ipo.xls'],
        'ibd_spotlight': ['ibd_spotlight.csv', 'STOCK_SPOTLIGHT.xls', 'ibd_spotlight.xls'],
        'ibd_sector': ['ibd_sector.csv', 'SECTOR_LEADERS.xls', 'ibd_sector.xls']
    }
    
    for key, filenames in files_to_check.items():
        for filename in filenames:
            try:
                if os.path.exists(filename):
                    # Read file based on extension
                    if filename.endswith('.csv'):
                        df = pd.read_csv(filename)
                    else:  # .xls or .xlsx
                        df = pd.read_excel(filename)
                    
                    # Find ticker column
                    if 'Symbol' in df.columns:
                        tickers = df['Symbol'].tolist()
                    elif 'Ticker' in df.columns:
                        tickers = df['Ticker'].tolist()
                    else:
                        tickers = df.iloc[:, 0].tolist()
                    
                    # Clean up - remove "Symbol" header if it's in data
                    tickers = [str(t).strip() for t in tickers if str(t) != 'Symbol' and str(t) != 'nan' and len(str(t)) <= 10]
                    
                    if tickers:
                        ibd_lists[key] = tickers
                        print(f"  ✓ Found {filename} ({len(tickers)} stocks)")
                        break  # Found file, stop trying other extensions
            except Exception as e:
                pass
    
    return ibd_lists

# Build complete ticker list
def get_all_tickers():
    """Get all tickers with source tracking"""
    ticker_sources = {}
    
    # S&P 500
    print("Fetching S&P 500...")
    sp500 = get_sp500_tickers()
    for ticker in sp500:
        ticker_sources.setdefault(ticker, []).append('S&P 500')
    
    # NASDAQ 100
    print("Fetching NASDAQ 100...")
    nasdaq100 = get_nasdaq100_tickers()
    for ticker in nasdaq100:
        ticker_sources.setdefault(ticker, []).append('NASDAQ 100')
    
    # Russell 1000 additional
    print("Adding Russell 1000 stocks...")
    russell = get_russell1000_additional()
    for ticker in russell:
        ticker_sources.setdefault(ticker, []).append('Russell 1000')
    
    # Russell 2000
    print("Fetching Russell 2000...")
    russell2000 = get_russell2000_tickers()
    for ticker in russell2000:
        ticker_sources.setdefault(ticker, []).append('Russell 2000')
    
    # Crypto and Indices
    print("Adding crypto and indices...")
    crypto_idx = get_crypto_and_indices()
    for ticker in crypto_idx['crypto']:
        ticker_sources.setdefault(ticker, []).append('Crypto')
    for ticker in crypto_idx['indices']:
        ticker_sources.setdefault(ticker, []).append('Index ETF')
    
    # IBD Lists
    print("Checking for IBD CSV files...")
    ibd_lists = get_ibd_from_csv()
    if ibd_lists.get('ibd_50'):
        for ticker in ibd_lists['ibd_50']:
            ticker_sources.setdefault(ticker, []).append('IBD 50')
    if ibd_lists.get('ibd_bigcap'):
        for ticker in ibd_lists['ibd_bigcap']:
            ticker_sources.setdefault(ticker, []).append('IBD Big Cap 20')
    if ibd_lists.get('ibd_ipo'):
        for ticker in ibd_lists['ibd_ipo']:
            ticker_sources.setdefault(ticker, []).append('IBD IPO')
    if ibd_lists.get('ibd_spotlight'):
        for ticker in ibd_lists['ibd_spotlight']:
            ticker_sources.setdefault(ticker, []).append('IBD Spotlight')
    if ibd_lists.get('ibd_sector'):
        for ticker in ibd_lists['ibd_sector']:
            ticker_sources.setdefault(ticker, []).append('IBD Sector')
    
    return list(ticker_sources.keys()), ticker_sources

# =============================================================================
# EMAIL CONFIGURATION
# =============================================================================

EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'sender_email': os.environ.get('GMAIL_EMAIL', 'glamp2013@gmail.com'),
    'sender_password': os.environ.get('GMAIL_PASSWORD', ''),
    'recipient_email': os.environ.get('RECIPIENT_EMAIL', 'glamp2013@gmail.com')
}

# =============================================================================
# ALERT PREFERENCES
# =============================================================================

ALERT_ON_ENTRY = True           # Alert when position enters PSAR buy
ALERT_ON_EXIT = True            # Alert when position exits PSAR buy
ALERT_DAILY_SUMMARY = True      # Daily summary
INCLUDE_EXCEL_ATTACHMENT = False  # Don't attach Excel (too many stocks)
INCLUDE_SELL_SIGNALS = False     # Don't show all sell signals (too many)

# =============================================================================
# INDICATOR THRESHOLDS
# =============================================================================

INDICATOR_THRESHOLDS = {
    'rsi_oversold': 35,
    'rsi_overbought': 70,
    'stoch_oversold': 25,
    'stoch_overbought': 75,
    'willr_oversold': -80,
    'willr_overbought': -20,
    'bb_distance_pct': 0.05
}

# =============================================================================
# PSAR PARAMETERS
# =============================================================================

PSAR_CONFIG = {
    'iaf': 0.02,
    'maxaf': 0.2
}

# =============================================================================
# DATA FETCH SETTINGS
# =============================================================================

DATA_CONFIG = {
    'history_period': '6mo',
    'min_data_points': 50
}

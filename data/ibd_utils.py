"""
IBD (Investor's Business Daily) utilities module.

Handles loading IBD stock lists, generating IBD research URLs,
and formatting IBD-related display elements.
"""

import os
import pandas as pd

# Get the directory where this module is located
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

# Map IBD filenames to their list parameter for URLs
IBD_LIST_MAP = {
    'ibd_50': 'ibd50',
    'ibd_bigcap20': 'bigcap20',
    'ibd_sector': 'sectorleaders',
    'ibd_ipo': 'ipo-leaders',
    'ibd_spotlight': 'stock-spotlight'
}

# IBD files to load (will check both current dir and module dir)
IBD_FILES = [
    'ibd_50.csv',
    'ibd_bigcap20.csv',
    'ibd_sector.csv',
    'ibd_ipo.csv',
    'ibd_spotlight.csv'
]


def load_ibd_data():
    """
    Load IBD stats from all IBD CSV/Excel files.
    
    Returns:
        tuple: (ibd_stats dict, list of unique tickers)
        
        ibd_stats = {
            'TICKER': {
                'composite': rating,
                'eps': rating,
                'rs': rating,
                'smr': rating,
                'source': 'IBD 50',
                'company_name': 'Company Name',
                'list': 'ibd50'
            },
            ...
        }
    """
    print("Loading IBD data files...")
    ibd_stats = {}
    all_ibd_tickers = []
    
    for filename in IBD_FILES:
        # Check multiple possible locations for IBD files
        filepath = None
        possible_paths = [
            filename,                                           # Current directory
            os.path.join(MODULE_DIR, filename),                # data/ folder (where ibd_utils.py is)
            os.path.join(os.path.dirname(MODULE_DIR), filename),  # Parent of data/ (project root)
            os.path.join('data_files', filename),              # data_files/ folder
            os.path.join(os.path.dirname(MODULE_DIR), 'data_files', filename),  # project_root/data_files/
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                filepath = path
                print(f"  Found IBD file: {path}")
                break
        
        if not filepath:
            print(f"  ✗ IBD file not found: {filename} (checked {len(possible_paths)} locations)")
            continue
            
        if filepath:
            try:
                # IBD files are Excel files with header rows before data
                df = None
                
                # Try Excel with xlrd engine (for .xls files), no header first
                try:
                    df = pd.read_excel(filepath, engine='xlrd', header=None)
                except:
                    try:
                        df = pd.read_excel(filepath, header=None)
                    except:
                        try:
                            df = pd.read_csv(filepath, header=None)
                        except:
                            pass
                
                if df is None or df.empty:
                    print(f"  ✗ Could not read {filepath}")
                    continue
                
                # Find the header row (row where first cell is 'Symbol')
                header_row = None
                for i, row in df.iterrows():
                    first_cell = str(row.iloc[0]).strip().upper()
                    if first_cell == 'SYMBOL':
                        header_row = i
                        break
                
                if header_row is None:
                    print(f"  ✗ Could not find header in {filepath}")
                    continue
                
                # Re-read with correct header
                try:
                    df = pd.read_excel(filepath, engine='xlrd', header=header_row)
                except:
                    try:
                        df = pd.read_excel(filepath, header=header_row)
                    except:
                        df = pd.read_csv(filepath, header=header_row)
                
                # Get symbols from first column
                symbol_col = df.columns[0]
                
                # Check for rating columns
                composite_col = None
                eps_col = None
                rs_col = None
                smr_col = None
                
                for col in df.columns:
                    col_upper = str(col).upper()
                    if 'COMPOSITE' in col_upper:
                        composite_col = col
                    elif col_upper == 'EPS RATING' or col_upper == 'EPS':
                        eps_col = col
                    elif col_upper == 'RS RATING' or col_upper == 'RS':
                        rs_col = col
                    elif col_upper == 'SMR RATING' or col_upper == 'SMR':
                        smr_col = col
                
                # Get list name for URLs (use original filename for mapping)
                list_name = IBD_LIST_MAP.get(filename.replace('.csv', ''), 'ibd50')
                
                # Extract tickers and stats
                count = 0
                for _, row in df.iterrows():
                    symbol = str(row[symbol_col]).strip().upper()
                    
                    # Skip invalid symbols
                    if not symbol or symbol == 'NAN' or symbol == 'SYMBOL' or len(symbol) > 10:
                        continue
                    if not symbol[0].isalpha():
                        continue
                    
                    all_ibd_tickers.append(symbol)
                    count += 1
                    
                    # Get company name for IBD URL
                    company_name = None
                    for col in df.columns:
                        if 'company' in str(col).lower() or 'name' in str(col).lower():
                            company_name = str(row[col]).strip() if pd.notna(row[col]) else None
                            break
                    
                    # Store stats (use original filename for source display)
                    ibd_stats[symbol] = {
                        'composite': row.get(composite_col, 'N/A') if composite_col else 'N/A',
                        'eps': row.get(eps_col, 'N/A') if eps_col else 'N/A',
                        'rs': row.get(rs_col, 'N/A') if rs_col else 'N/A',
                        'smr': row.get(smr_col, 'N/A') if smr_col else 'N/A',
                        'source': filename.replace('.csv', '').replace('_', ' ').upper(),
                        'company_name': company_name,
                        'list': list_name
                    }
                
                print(f"  ✓ Loaded {count} tickers from {filepath}")
                
            except Exception as e:
                print(f"  ✗ Error loading {filename}: {e}")
    
    unique_tickers = list(set(all_ibd_tickers))
    print(f"  Total unique IBD tickers: {len(unique_tickers)}")
    return ibd_stats, unique_tickers


def get_ibd_url(ticker, ibd_stats, exchange=None):
    """
    Generate IBD research URL for a ticker.
    
    Args:
        ticker: Stock symbol (e.g., 'AAPL')
        ibd_stats: Dictionary of IBD stats from load_ibd_data()
        exchange: Optional exchange name (e.g., 'NASDAQ', 'NYSE')
    
    Returns:
        URL string or None if not an IBD stock
    
    Example URLs:
        https://research.investors.com/stock-quotes/nyse-agnicoeagle-mines-aem.htm?list=sectorleaders&type=weekly
        https://research.investors.com/stock-quotes/nasdaq-micron-technology-mu.htm?list=ibd50&type=weekly
    """
    if ticker not in ibd_stats:
        return None
    
    ibd_info = ibd_stats[ticker]
    company_name = ibd_info.get('company_name')
    list_name = ibd_info.get('list', 'ibd50')
    
    if not company_name:
        return None
    
    # Convert company name to URL format: "Micron Technology" -> "micron-technology"
    url_name = company_name.lower()
    url_name = ''.join(c if c.isalnum() or c == ' ' else '' for c in url_name)
    url_name = '-'.join(url_name.split())
    
    # Determine exchange (nyse or nasdaq)
    if exchange:
        exch = 'nasdaq' if 'NASDAQ' in exchange.upper() else 'nyse'
    else:
        exch = 'nyse'  # Default to NYSE
    
    # Build URL
    url = f"https://research.investors.com/stock-quotes/{exch}-{url_name}-{ticker.lower()}.htm?list={list_name}&type=weekly"
    return url


def format_ibd_ticker(ticker, source, ibd_url=None):
    """
    Format a ticker with IBD star and optional link.
    
    Args:
        ticker: Stock symbol
        source: Source string (should contain 'IBD' if IBD stock)
        ibd_url: Optional IBD URL for the star link
    
    Returns:
        HTML string for display
    """
    is_ibd = 'IBD' in (source or '')
    
    if is_ibd and ibd_url:
        return f"<a href='{ibd_url}' target='_blank' style='text-decoration:none;'>⭐</a>{ticker}"
    elif is_ibd:
        return f"⭐{ticker}"
    else:
        return ticker


def is_ibd_stock(ticker, ibd_stats):
    """Check if a ticker is on any IBD list."""
    return ticker in ibd_stats


def get_ibd_ratings(ticker, ibd_stats):
    """
    Get IBD ratings for a ticker.
    
    Returns:
        dict with 'composite', 'eps', 'rs', 'smr' keys, or empty dict
    """
    if ticker not in ibd_stats:
        return {}
    
    info = ibd_stats[ticker]
    return {
        'composite': info.get('composite', 'N/A'),
        'eps': info.get('eps', 'N/A'),
        'rs': info.get('rs', 'N/A'),
        'smr': info.get('smr', 'N/A')
    }


# For testing
if __name__ == "__main__":
    print("Loading IBD data...")
    ibd_stats, tickers = load_ibd_data()
    
    print(f"\nTotal IBD stocks: {len(tickers)}")
    print(f"\nSample IBD stats:")
    for ticker in list(ibd_stats.keys())[:5]:
        info = ibd_stats[ticker]
        url = get_ibd_url(ticker, ibd_stats)
        print(f"  {ticker}: {info['company_name']} ({info['list']})")
        print(f"    URL: {url}")
        print(f"    Display: {format_ibd_ticker(ticker, 'IBD', url)}")

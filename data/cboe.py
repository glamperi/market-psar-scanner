import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import datetime
import re
import warnings
from io import StringIO

# Suppress warnings
warnings.filterwarnings('ignore', category=FutureWarning)

# --- Configuration ---
TOTAL_PCR_CORRECTION_WARN = 0.60
TOTAL_PCR_OVERSOLD_BUY = 1.20

def _capture_analysis_output(total_pcr, data_time=None):
    """Generates the formatted string output based on the fetched data."""
    output = []
    
    output.append("="*50)
    time_str = f" ({data_time})" if data_time else ""
    output.append(f"MARKET SENTIMENT (Cboe Total P/C Ratio){time_str}")
    output.append("="*50)

    if total_pcr is not None:
        output.append(f"TOTAL PUT/CALL RATIO: {total_pcr:.2f}")
        if total_pcr < 0.50:
            output.append("🚨 EXTREME COMPLACENCY (<0.50) - Potential market TOP")
        elif total_pcr < TOTAL_PCR_CORRECTION_WARN:
            output.append("🚨 WARNING: Below 0.60 - High greed, correction possible")
        elif total_pcr < 0.70:
            output.append("Bullish sentiment (0.60-0.70) - Normal")
        elif total_pcr < 0.90:
            output.append("Neutral sentiment (0.70-0.90)")
        elif total_pcr < 1.00:
            output.append("🟢 Elevated fear (0.90-1.00) - Buying opportunity")
        elif total_pcr < TOTAL_PCR_OVERSOLD_BUY:
            output.append("🟢 High fear (1.00-1.20) - Good buying opportunity")
        else:
            output.append("✅ EXTREME FEAR (>1.20) - Contrarian BUY signal")
    else:
        output.append("TOTAL PUT/CALL RATIO: Not available")

    output.append("="*50)
    return "\n".join(output)


def get_cboe_ratios_and_analyze():
    """
    Fetches Cboe Put/Call Ratios using Selenium web scraping.
    
    The data is in an iframe at ww2.cboe.com with tables showing:
    TIME, CALLS, PUTS, TOTAL, P/C RATIO
    
    We find the LAST ROW that has P/C RATIO filled in (not empty).
    """
    # The actual data is in this iframe URL (found via network inspection)
    url = "https://ww2.cboe.com/us/options/market_statistics/?iframe=1"
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    print("\nLaunching headless browser to fetch Cboe data (This may take a few seconds)...")
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    except Exception as e:
        return f"🚨 MARKET SENTIMENT FETCH FAILED 🚨\nError initializing Chrome driver: {type(e).__name__}: {e}\n(Ensure Chrome is installed and updated.)"

    total_pcr = None
    data_time = None
    
    try:
        driver.get(url)
        
        # Wait for page to load
        time.sleep(8)
        
        page_text = driver.page_source
        
        # Try to parse HTML tables
        try:
            dfs = pd.read_html(StringIO(page_text))
            print(f"  Found {len(dfs)} tables")
            
            # Look for table with P/C RATIO column
            for i, df in enumerate(dfs):
                if df.empty or len(df.columns) < 4:
                    continue
                
                cols = [str(c).upper() for c in df.columns]
                
                # Check if this table has P/C RATIO column
                has_pc_ratio = any('P/C' in c or 'PC RATIO' in c or 'PUT/CALL' in c for c in cols)
                has_calls = any('CALL' in c for c in cols)
                has_puts = any('PUT' in c and 'CALL' not in c for c in cols)
                
                if has_pc_ratio and has_calls and has_puts:
                    print(f"  Table {i}: {len(df)} rows, cols: {list(df.columns)}")
                    
                    # Find column indices
                    calls_col = None
                    puts_col = None
                    time_col = None
                    pc_ratio_col = None
                    
                    for j, col in enumerate(df.columns):
                        col_upper = str(col).upper()
                        if 'P/C' in col_upper or 'PC RATIO' in col_upper or 'PUT/CALL' in col_upper:
                            pc_ratio_col = j
                        elif 'CALL' in col_upper and 'PUT' not in col_upper:
                            calls_col = j
                        elif 'PUT' in col_upper and 'CALL' not in col_upper:
                            puts_col = j
                        elif 'TIME' in col_upper:
                            time_col = j
                    
                    if time_col is None:
                        time_col = 0  # First column is usually TIME
                    
                    if calls_col is not None and puts_col is not None:
                        # Find the LAST ROW with P/C RATIO filled in
                        # Iterate backwards through rows to find most recent with data
                        for row_idx in range(len(df) - 1, -1, -1):
                            row = df.iloc[row_idx]
                            
                            # Check if P/C RATIO column has data (if we found that column)
                            if pc_ratio_col is not None:
                                pc_val = str(row.iloc[pc_ratio_col]).strip()
                                # Skip if P/C RATIO is empty, NaN, or just whitespace
                                if pc_val in ['', 'nan', 'NaN', '-', '--'] or pd.isna(row.iloc[pc_ratio_col]):
                                    continue
                            
                            try:
                                # Parse numbers (remove commas if present)
                                calls_val = str(row.iloc[calls_col]).replace(',', '').strip()
                                puts_val = str(row.iloc[puts_col]).replace(',', '').strip()
                                
                                # Skip if calls/puts are empty
                                if not calls_val or calls_val in ['', 'nan', 'NaN']:
                                    continue
                                    
                                calls = int(float(calls_val))
                                puts = int(float(puts_val))
                                
                                if calls > 100000:  # Sanity check - should be large numbers
                                    total_pcr = puts / calls
                                    
                                    # Get time
                                    data_time = str(row.iloc[time_col])
                                    
                                    print(f"  Calls: {calls:,}, Puts: {puts:,}, P/C: {total_pcr:.2f} at {data_time}")
                                    break
                            except (ValueError, TypeError) as e:
                                continue
                        
                        if total_pcr is not None:
                            break
                            
        except Exception as e:
            print(f"  Table parsing error: {e}")
        
        # Fallback: regex pattern matching
        if total_pcr is None:
            # Look for time + 3 numbers pattern
            pattern = r'(\d{1,2}:\d{2}\s*[AP]M)\s*(\d[\d,]*)\s*(\d[\d,]*)\s*(\d[\d,]*)'
            matches = re.findall(pattern, page_text)
            
            if matches:
                print(f"  Found {len(matches)} time-based rows via regex")
                # Go backwards through matches to find one with real data
                for match in reversed(matches):
                    data_time = match[0]
                    calls = int(match[1].replace(',', ''))
                    puts = int(match[2].replace(',', ''))
                    
                    if calls > 100000:
                        total_pcr = puts / calls
                        print(f"  Regex: Calls: {calls:,}, Puts: {puts:,}, P/C: {total_pcr:.2f}")
                        break
        
        if total_pcr is None:
            return "🚨 MARKET SENTIMENT FETCH FAILED 🚨\nCould not find calls/puts data on page.\nCBOE may have changed their page layout."

    except Exception as e:
        return f"🚨 MARKET SENTIMENT FETCH FAILED 🚨\nError: {type(e).__name__}: {e}"
    finally:
        driver.quit()
        
    return _capture_analysis_output(total_pcr, data_time)

if __name__ == "__main__":
    print(get_cboe_ratios_and_analyze())

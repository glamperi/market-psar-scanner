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
    TIME, CALLS, PUTS, TOTAL
    
    P/C Ratio = PUTS / CALLS (calculated from last row of Total section)
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
            
            # Look for the "Total" table - should have columns like TIME, CALLS, PUTS, TOTAL
            for i, df in enumerate(dfs):
                if df.empty or len(df.columns) < 3:
                    continue
                
                cols = [str(c).upper() for c in df.columns]
                
                # Check if this looks like the right table
                has_calls = any('CALL' in c for c in cols)
                has_puts = any('PUT' in c for c in cols)
                
                if has_calls and has_puts:
                    print(f"  Table {i}: {len(df)} rows, cols: {list(df.columns)}")
                    
                    # Find column indices
                    calls_col = None
                    puts_col = None
                    time_col = None
                    
                    for j, col in enumerate(df.columns):
                        col_upper = str(col).upper()
                        if 'CALL' in col_upper and 'PUT' not in col_upper:
                            calls_col = j
                        elif 'PUT' in col_upper:
                            puts_col = j
                        elif 'TIME' in col_upper or j == 0:
                            time_col = j
                    
                    if calls_col is not None and puts_col is not None:
                        # Get the LAST row (most recent time)
                        last_row = df.iloc[-1]
                        
                        try:
                            # Parse numbers (remove commas if present)
                            calls_val = str(last_row.iloc[calls_col]).replace(',', '')
                            puts_val = str(last_row.iloc[puts_col]).replace(',', '')
                            
                            calls = int(calls_val)
                            puts = int(puts_val)
                            
                            if calls > 100000:  # Sanity check - should be large numbers
                                total_pcr = puts / calls
                                
                                # Get time
                                if time_col is not None:
                                    data_time = str(last_row.iloc[time_col])
                                
                                print(f"  Calls: {calls:,}, Puts: {puts:,}, P/C: {total_pcr:.2f} at {data_time}")
                                break
                        except (ValueError, TypeError) as e:
                            print(f"  Parse error: {e}")
                            continue
                            
        except Exception as e:
            print(f"  Table parsing error: {e}")
        
        # Fallback: regex pattern matching
        if total_pcr is None:
            # Look for time + 3 numbers pattern
            pattern = r'(\d{1,2}:\d{2}\s*[AP]M)\s*(\d[\d,]*)\s*(\d[\d,]*)\s*(\d[\d,]*)'
            matches = re.findall(pattern, page_text)
            
            if matches:
                print(f"  Found {len(matches)} time-based rows via regex")
                last_match = matches[-1]
                data_time = last_match[0]
                calls = int(last_match[1].replace(',', ''))
                puts = int(last_match[2].replace(',', ''))
                
                if calls > 100000:
                    total_pcr = puts / calls
                    print(f"  Regex: Calls: {calls:,}, Puts: {puts:,}, P/C: {total_pcr:.2f}")
        
        if total_pcr is None:
            return "🚨 MARKET SENTIMENT FETCH FAILED 🚨\nCould not find calls/puts data on page.\nCBOE may have changed their page layout."

    except Exception as e:
        return f"🚨 MARKET SENTIMENT FETCH FAILED 🚨\nError: {type(e).__name__}: {e}"
    finally:
        driver.quit()
        
    return _capture_analysis_output(total_pcr, data_time)

if __name__ == "__main__":
    print(get_cboe_ratios_and_analyze())

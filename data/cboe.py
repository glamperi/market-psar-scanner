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

def _capture_analysis_output(total_pcr, vix_pcr=None, data_time=None):
    """Generates the formatted string output based on the fetched data."""
    output = []
    
    output.append("="*50)
    time_str = f" ({data_time})" if data_time else ""
    output.append(f"MARKET SENTIMENT (Cboe Put/Call Ratios){time_str}")
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
    
    # VIX Put/Call Ratio (only show if we found it)
    if vix_pcr is not None:
        output.append("")
        output.append(f"VIX PUT/CALL RATIO: {vix_pcr:.2f}")
        if vix_pcr >= 1.20:
            output.append("📈 CONTRARIAN BUY: VIX PCR above 1.20. Extreme VIX Put buying suggests volatility will fall (Bullish for the Market).")
        elif vix_pcr >= 1.00:
            output.append("🟢 Elevated VIX puts - Traders expect volatility to decrease (Bullish)")
        elif vix_pcr >= 0.80:
            output.append("Neutral VIX sentiment")
        elif vix_pcr >= 0.60:
            output.append("🟡 Elevated VIX calls - Traders hedging, expect volatility rise")
        else:
            output.append("🔴 Extreme VIX call buying - Fear of volatility spike (Bearish)")

    output.append("="*50)
    return "\n".join(output)


def get_cboe_ratios_and_analyze():
    """
    Fetches Cboe Put/Call Ratios using Selenium web scraping.
    
    Fetches:
    1. Total Put/Call Ratio (intraday from iframe)
    2. VIX Put/Call Ratio (daily from main page)
    """
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
    vix_pcr = None
    data_time = None
    
    try:
        # --- FIRST: Get Total P/C Ratio from intraday iframe ---
        url_intraday = "https://ww2.cboe.com/us/options/market_statistics/?iframe=1"
        driver.get(url_intraday)
        time.sleep(8)
        
        page_text = driver.page_source
        
        # Try to parse HTML tables for Total P/C
        try:
            dfs = pd.read_html(StringIO(page_text))
            print(f"  Found {len(dfs)} tables (intraday)")
            
            for i, df in enumerate(dfs):
                if df.empty or len(df.columns) < 4:
                    continue
                
                cols = [str(c).upper() for c in df.columns]
                has_pc_ratio = any('P/C' in c or 'PC RATIO' in c or 'PUT/CALL' in c for c in cols)
                has_calls = any('CALL' in c for c in cols)
                has_puts = any('PUT' in c and 'CALL' not in c for c in cols)
                
                if has_pc_ratio and has_calls and has_puts:
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
                        time_col = 0
                    
                    if calls_col is not None and puts_col is not None:
                        for row_idx in range(len(df) - 1, -1, -1):
                            row = df.iloc[row_idx]
                            
                            if pc_ratio_col is not None:
                                pc_val = str(row.iloc[pc_ratio_col]).strip()
                                if pc_val in ['', 'nan', 'NaN', '-', '--'] or pd.isna(row.iloc[pc_ratio_col]):
                                    continue
                            
                            try:
                                calls_val = str(row.iloc[calls_col]).replace(',', '').strip()
                                puts_val = str(row.iloc[puts_col]).replace(',', '').strip()
                                
                                if not calls_val or calls_val in ['', 'nan', 'NaN']:
                                    continue
                                    
                                calls = int(float(calls_val))
                                puts = int(float(puts_val))
                                
                                if calls > 100000:
                                    total_pcr = puts / calls
                                    data_time = str(row.iloc[time_col])
                                    print(f"  Total P/C: {total_pcr:.2f} at {data_time}")
                                    break
                            except (ValueError, TypeError):
                                continue
                        
                        if total_pcr is not None:
                            break
                            
        except Exception as e:
            print(f"  Intraday table parsing error: {e}")
        
        # Fallback regex for Total P/C
        if total_pcr is None:
            pattern = r'(\d{1,2}:\d{2}\s*[AP]M)\s*(\d[\d,]*)\s*(\d[\d,]*)\s*(\d[\d,]*)'
            matches = re.findall(pattern, page_text)
            
            if matches:
                for match in reversed(matches):
                    data_time = match[0]
                    calls = int(match[1].replace(',', ''))
                    puts = int(match[2].replace(',', ''))
                    
                    if calls > 100000:
                        total_pcr = puts / calls
                        print(f"  Total P/C (regex): {total_pcr:.2f}")
                        break
        
        # --- SECOND: Get VIX P/C Ratio from daily page ---
        try:
            # Try iframe URL first (like intraday)
            url_daily = "https://www.cboe.com/us/options/market_statistics/daily/?iframe=1"
            driver.get(url_daily)
            time.sleep(3)
            
            # Handle cookie consent popup if present
            try:
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                
                # Look for common cookie consent buttons
                consent_buttons = [
                    "//button[contains(text(), 'Accept')]",
                    "//button[contains(text(), 'Accept All')]",
                    "//button[contains(text(), 'I Accept')]",
                    "//button[contains(@class, 'accept')]",
                    "//a[contains(text(), 'Accept')]",
                ]
                
                for xpath in consent_buttons:
                    try:
                        button = driver.find_element(By.XPATH, xpath)
                        if button.is_displayed():
                            button.click()
                            print("  Clicked cookie consent")
                            time.sleep(2)
                            break
                    except:
                        continue
            except:
                pass  # No consent popup or couldn't click it
            
            time.sleep(3)
            daily_page = driver.page_source
            
            # The daily page has both:
            # - CBOE TOTAL PUT/CALL RATIO (e.g., 0.75)
            # - CBOE VOLATILITY INDEX (VIX) PUT/CALL RATIO (e.g., 0.77)
            # We need to find the VIX one specifically
            
            # Method 1: Look for the specific VIX text pattern
            # Pattern: "VOLATILITY INDEX (VIX)" ... "PUT/CALL" ... number
            vix_section_pattern = r'VOLATILITY\s+INDEX\s*\(VIX\)[^0-9]*PUT[/\s]*CALL[^0-9]*RATIO[^0-9]*(\d+\.\d+)'
            vix_match = re.search(vix_section_pattern, daily_page.upper())
            
            if vix_match:
                try:
                    vix_pcr = float(vix_match.group(1))
                    if 0.2 < vix_pcr < 3.0:
                        print(f"  VIX P/C: {vix_pcr:.2f}")
                    else:
                        vix_pcr = None
                except ValueError:
                    vix_pcr = None
            
            # Method 2: Find VIX section in page, extract the ratio
            if vix_pcr is None:
                # Look for "VIX" in the page, then find the associated ratio
                vix_label = "VOLATILITY INDEX (VIX)"
                vix_pos = daily_page.upper().find(vix_label)
                
                if vix_pos > 0:
                    # Look in next 300 chars for "PUT/CALL" and then a decimal
                    search_area = daily_page[vix_pos:vix_pos+300]
                    
                    # Find decimals after PUT/CALL in this section
                    pc_pos = search_area.upper().find('PUT')
                    if pc_pos > 0:
                        after_pc = search_area[pc_pos:]
                        decimal_pattern = r'(\d\.\d{2})'
                        decimals = re.findall(decimal_pattern, after_pc[:100])
                        for d in decimals:
                            try:
                                val = float(d)
                                if 0.2 < val < 3.0:
                                    vix_pcr = val
                                    print(f"  VIX P/C (fallback): {vix_pcr:.2f}")
                                    break
                            except ValueError:
                                continue
            
            # Method 3: Try parsing tables
            if vix_pcr is None:
                try:
                    daily_dfs = pd.read_html(StringIO(daily_page))
                    for df in daily_dfs:
                        df_str = df.to_string().upper()
                        if 'VIX' in df_str and 'PUT' in df_str:
                            # Look through rows/cols for VIX ratio
                            for idx, row in df.iterrows():
                                row_str = ' '.join([str(v).upper() for v in row.values])
                                if 'VIX' in row_str and 'PUT' in row_str:
                                    # Find decimal in this row
                                    for val in row.values:
                                        try:
                                            v = float(val)
                                            if 0.2 < v < 3.0:
                                                vix_pcr = v
                                                print(f"  VIX P/C (table): {vix_pcr:.2f}")
                                                break
                                        except (ValueError, TypeError):
                                            continue
                                if vix_pcr:
                                    break
                        if vix_pcr:
                            break
                except Exception as e:
                    print(f"  VIX table parsing error: {e}")
                                
        except Exception as e:
            print(f"  Warning: Could not fetch VIX P/C ratio: {e}")
            # Don't fail - just skip VIX P/C
        
        if total_pcr is None:
            return "🚨 MARKET SENTIMENT FETCH FAILED 🚨\nCould not find Total P/C data.\nCBOE may have changed their page layout."

    except Exception as e:
        return f"🚨 MARKET SENTIMENT FETCH FAILED 🚨\nError: {type(e).__name__}: {e}"
    finally:
        driver.quit()
        
    return _capture_analysis_output(total_pcr, vix_pcr, data_time)


if __name__ == "__main__":
    print(get_cboe_ratios_and_analyze())

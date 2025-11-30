import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import datetime
import io
import warnings

# Suppress the FutureWarning from pandas.read_html
warnings.filterwarnings('ignore', category=FutureWarning)

# --- Configuration ---
# Thresholds for Analysis
TOTAL_PCR_CORRECTION_WARN = 0.60
TOTAL_PCR_OVERSOLD_BUY = 1.20
VIX_PCR_COMPLACENCY_WARN = 0.20
VIX_PCR_BULLISH_CONTRARIAN = 1.20

def _capture_analysis_output(total_pcr, vix_pcr):
    """Generates the formatted string output based on the fetched data."""
    output = []
    
    output.append("\n" + "="*50)
    output.append(f"MARKET SENTIMENT ANALYSIS (Cboe Ratios) for {datetime.date.today()}")
    output.append("="*50)

    # TOTAL PCR Analysis
    if total_pcr is not None:
        output.append(f"TOTAL PUT/CALL RATIO: {total_pcr:.2f}")
        if total_pcr < TOTAL_PCR_CORRECTION_WARN:
            output.append("🚨 WARNING: TOTAL PCR below 0.60. Market is due for a correction (Extreme Greed).")
        elif total_pcr > TOTAL_PCR_OVERSOLD_BUY:
            output.append("✅ SIGNAL: TOTAL PCR above 1.20. Market is oversold, suggesting a buy (Extreme Fear).")
        else:
            output.append("Neutral. Sentiment is within historical norms.")
    else:
        output.append("TOTAL PUT/CALL RATIO data not found.")

    output.append("-" * 50)
    
    # VIX PCR Analysis
    if vix_pcr is not None:
        output.append(f"VIX PUT/CALL RATIO: {vix_pcr:.2f}")
        if vix_pcr < VIX_PCR_COMPLACENCY_WARN:
            output.append("🚨 WARNING: VIX PCR below 0.20. Market is complacent (Low Hedging Activity).")
        elif vix_pcr > VIX_PCR_BULLISH_CONTRARIAN:
            output.append("📈 CONTRARIAN BUY: VIX PCR above 1.20. Extreme VIX Put buying suggests volatility will fall (Bullish for the Market).")
        else:
            output.append("Neutral. VIX-related sentiment is within historical norms.")
    else:
        output.append("VIX PUT/CALL RATIO data not found.")
        
    output.append("="*50)
    return "\n".join(output)


def get_cboe_ratios_and_analyze():
    """Fetches Cboe Put/Call Ratios using Selenium and returns a market sentiment analysis string."""
    url = "https://www.cboe.com/us/options/market_statistics/daily/"
    
    # --- Selenium Setup ---
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")

    print("Launching headless browser and installing driver for Cboe...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    total_pcr = None
    vix_pcr = None

    try:
        driver.get(url)
        time.sleep(5)  # Wait for JavaScript to load the data

        print("Parsing rendered HTML...")
        tables = pd.read_html(io.StringIO(driver.page_source))
        
        # --- Extract Ratios from Tables ---
        for df in tables:
            # Check if the table has at least 2 columns
            if df.shape[1] < 2:
                continue
                
            first_col_str = df.iloc[:, 0].astype(str).str.upper()

            # Find TOTAL PUT/CALL RATIO
            if total_pcr is None:
                total_row = df[first_col_str.str.contains("TOTAL PUT/CALL RATIO", na=False)]
                if not total_row.empty:
                    try:
                        total_pcr = float(total_row.iloc[0, 1])
                    except (ValueError, IndexError):
                        pass

            # Find VIX PUT/CALL RATIO
            if vix_pcr is None:
                vix_row = df[first_col_str.str.contains("VIX PUT/CALL RATIO", na=False)]
                if vix_row.empty:
                    vix_row = df[first_col_str.str.contains("VOLATILITY INDEX", na=False)]
                
                if not vix_row.empty:
                    try:
                        vix_pcr = float(vix_row.iloc[0, 1])
                    except (ValueError, IndexError):
                        pass
            
            # Stop searching if both are found
            if total_pcr is not None and vix_pcr is not None:
                break
        
    except Exception as e:
        print(f"An error occurred while fetching Cboe data: {type(e).__name__}: {e}")
    finally:
        driver.quit()
        
    return _capture_analysis_output(total_pcr, vix_pcr)

if __name__ == "__main__":
    # If run directly, print the analysis
    print(get_cboe_ratios_and_analyze())

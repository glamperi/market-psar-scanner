#!/usr/bin/env python3
"""
Market-Wide Multi-Indicator PSAR Scanner with Email Alerts
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import json
import os
import csv
warnings.filterwarnings('ignore')

# Import configuration and EmailReport
from config import (
    get_all_tickers,
    EMAIL_CONFIG,
    ALERT_ON_ENTRY,
    ALERT_ON_EXIT,
    ALERT_DAILY_SUMMARY,
    INDICATOR_THRESHOLDS, 
    PSAR_CONFIG,
    DATA_CONFIG
)
# IMPORT THE NEW REPORT CLASS
from email_report import EmailReport

print("Market Scanner - Initialized")

# ... (Include the calculate_signal_weight, calculate_psar, calculate_all_indicators, 
#      analyze_stock, load_previous_status, save_current_status, detect_changes 
#      functions here - they remain UNCHANGED from the previous version) ...
#
# NOTE: To save space, I am not repeating the helper functions (calculate_psar, etc.) 
# as they are identical to what you have. 
# 
# BELOW IS THE UPDATED MAIN FUNCTION:

def main():
    print("=" * 100)
    print("MARKET-WIDE MULTI-INDICATOR PSAR SCANNER")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)
    
    # 1. Get Tickers (Using the fixed config.py)
    all_tickers, ticker_sources = get_all_tickers()
    
    print(f"\nScanning {len(all_tickers)} stocks...")
    results = []
    results_dict = {}
    
    # 2. Scan Stocks
    for i, ticker in enumerate(all_tickers, 1):
        if i % 50 == 0: print(f"Progress: {i}/{len(all_tickers)}")
        result = analyze_stock(ticker, ticker_sources)
        if result:
            results.append(result)
            results_dict[ticker] = result
        else:
            results_dict[ticker] = None
            
    if not results:
        print("No results found.")
        return

    # 3. Process Results
    df_all = pd.DataFrame(results)
    
    all_buys = df_all[df_all['PSAR_Buy'] == True].to_dict('records')
    
    all_early = df_all[
        (df_all['PSAR_Buy'] == False) &
        ((df_all['MACD_Buy'] == True) | (df_all['BB_Buy'] == True) | 
         (df_all['WillR_Buy'] == True) | (df_all['Coppock_Buy'] == True) | 
         (df_all['Ultimate_Buy'] == True))
    ].to_dict('records')
    
    # 4. Detect Changes
    print("\nCHECKING FOR CHANGES...")
    previous_status = load_previous_status()
    changes = detect_changes(previous_status, results_dict)
    
    # 5. Export CSVs (Relative Path Fix)
    print("\nEXPORTING CSV FILES...")
    csv_dir = 'outputs'
    os.makedirs(csv_dir, exist_ok=True)
    
    # Helper to calculate weight before saving
    def add_weights(datalist):
        for d in datalist:
            if 'signal_weight' not in d: d['signal_weight'] = calculate_signal_weight(d)
        return datalist

    # Export Buys
    if all_buys:
        pd.DataFrame(all_buys).to_csv(os.path.join(csv_dir, 'current_psar_buys.csv'), index=False)
        
    # Export New Entries
    if changes['new_entries']:
        pd.DataFrame(add_weights(changes['new_entries'])).to_csv(os.path.join(csv_dir, 'new_psar_entries.csv'), index=False)
        
    # Export Exits
    if changes['recent_exits_7day']:
        pd.DataFrame(changes['recent_exits_7day']).to_csv(os.path.join(csv_dir, 'recent_exits_7day.csv'), index=False)
        
    # Save Status
    results_dict['_exit_history'] = changes.get('_exit_history', {})
    save_current_status(results_dict)
    
    # 6. SEND EMAIL (Using the new EmailReport class)
    print("\nSENDING EMAIL ALERT...")
    
    should_alert = False
    subject = f"📊 Market Scanner Report - {datetime.now().strftime('%Y-%m-%d')}"
    
    if changes['new_entries'] and ALERT_ON_ENTRY:
        should_alert = True
        subject = f"🟢 {len(changes['new_entries'])} New PSAR Buy Signals!"
    elif changes['new_exits'] and ALERT_ON_EXIT:
        should_alert = True
        subject = f"🔴 {len(changes['new_exits'])} PSAR Exits!"
        
    if ALERT_DAILY_SUMMARY or should_alert or not previous_status:
        # HERE IS THE FIX: Use EmailReport class
        report = EmailReport(changes, all_buys, all_early)
        report.send_email(subject)
    else:
        print("No significant changes, email skipped.")
        
    print("\n✓ Done!")

if __name__ == "__main__":
    main()

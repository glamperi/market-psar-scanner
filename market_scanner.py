#!/usr/bin/env python3
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import json
import os
import csv
warnings.filterwarnings('ignore')

from config import (get_all_tickers, EMAIL_CONFIG, ALERT_ON_ENTRY, ALERT_ON_EXIT, 
                   ALERT_DAILY_SUMMARY, INDICATOR_THRESHOLDS, PSAR_CONFIG, DATA_CONFIG)
from email_report import EmailReport

# ... [KEEP YOUR EXISTING HELPER FUNCTIONS HERE: analyze_stock, etc.] ...
# ... [IF YOU NEED THE FULL FILE AGAIN, LET ME KNOW] ...

def main():
    print("=" * 100)
    print(f"MARKET SCANNER - {datetime.now()}")
    print("=" * 100)
    
    all_tickers, ticker_sources = get_all_tickers()
    results = []
    results_dict = {}
    
    # SCANNING
    for i, ticker in enumerate(all_tickers, 1):
        if i % 50 == 0: print(f"Progress: {i}/{len(all_tickers)}")
        # Pass sources to analyze_stock so it knows if it is IBD
        result = analyze_stock(ticker, ticker_sources)
        if result:
            results.append(result)
            results_dict[ticker] = result
        else:
            results_dict[ticker] = None

    if not results: return

    # PROCESSING
    df_all = pd.DataFrame(results)
    all_buys = df_all[df_all['PSAR_Buy'] == True].to_dict('records')
    all_early = df_all[(df_all['PSAR_Buy'] == False) & 
                       ((df_all['MACD_Buy'] == True) | (df_all['BB_Buy'] == True) | 
                        (df_all['WillR_Buy'] == True))].to_dict('records')

    # CHANGES
    previous_status = load_previous_status()
    changes = detect_changes(previous_status, results_dict)
    
    # SAVE & EMAIL
    save_current_status(results_dict)
    
    subject = f"📊 Market Report - {datetime.now().strftime('%Y-%m-%d')}"
    if changes['new_entries']: subject = f"🟢 {len(changes['new_entries'])} New Buys!"
    
    report = EmailReport(changes, all_buys, all_early)
    report.send_email(subject)

if __name__ == "__main__":
    main()

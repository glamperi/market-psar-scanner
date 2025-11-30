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

# Import configuration
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
# Import the EmailReport class (Ensure email_report.py is in the same folder)
from email_report import EmailReport

print("Market Scanner - Initialized")

# =============================================================================
# SIGNAL WEIGHT CALCULATION
# =============================================================================

def calculate_signal_weight(stock_data):
    """
    Calculate signal weight out of 100 based on indicator presence.
    """
    weight = 0
    if stock_data.get('MACD_Buy', False):
        weight += 30
    if stock_data.get('BB_Buy', False):
        weight += 10
    if stock_data.get('WillR_Buy', False):
        weight += 20
    if stock_data.get('Coppock_Buy', False):
        weight += 10
    if stock_data.get('Ultimate_Buy', False):
        weight += 30
    return weight

# =============================================================================
# PSAR CALCULATION
# =============================================================================

def calculate_psar(df, iaf=None, maxaf=None):
    """Calculate Parabolic SAR"""
    if iaf is None:
        iaf = PSAR_CONFIG['iaf']
    if maxaf is None:
        maxaf = PSAR_CONFIG['maxaf']
    
    length = len(df)
    high = df['High'].values
    low = df['Low'].values
    close = df['Close'].values
    
    psar = np.zeros(length)
    bull = True
    af = iaf
    hp = high[0]
    lp = low[0]
    psar[0] = close[0]
    
    for i in range(1, length):
        if bull:
            psar[i] = psar[i-1] + af * (hp - psar[i-1])
            if i >= 2:
                psar[i] = min(psar[i], low[i-1], low[i-2])
            else:
                psar[i] = min(psar[i], low[i-1])
        else:
            psar[i] = psar[i-1] + af * (lp - psar[i-1])
            if i >= 2:
                psar[i] = max(psar[i], high[i-1], high[i-2])
            else:
                psar[i] = max(psar[i], high[i-1])
        
        reverse = False
        
        if bull:
            if low[i] < psar[i]:
                bull = False
                reverse = True
                psar[i] = hp
                lp = low[i]
                af = iaf
        else:
            if high[i] > psar[i]:
                bull = True
                reverse = True
                psar[i] = lp
                hp = high[i]
                af = iaf
        
        if not reverse:
            if bull:
                if high[i] > hp:
                    hp = high[i]
                    af = min(af + iaf, maxaf)
                if low[i-1] < psar[i]:
                    psar[i] = low[i-1]
            else:
                if low[i] < lp:
                    lp = low[i]
                    af = min(af + iaf, maxaf)
                if high[i-1] > psar[i]:
                    psar[i] = high[i-1]
    
    return psar, bull

# =============================================================================
# INDICATOR CALCULATIONS
# =============================================================================

def calculate_ema(data, period):
    return data.ewm(span=period, adjust=False).mean()

def calculate_macd(close, fast=12, slow=26, signal=9):
    try:
        ema_fast = calculate_ema(close, fast)
        ema_slow = calculate_ema(close, slow)
        macd_line = ema_fast - ema_slow
        signal_line = calculate_ema(macd_line, signal)
        return macd_line, signal_line
    except:
        return None, None

def calculate_rsi(close, period=14):
    try:
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    except:
        return None

def calculate_stochastic(high, low, close, k_period=14, d_period=3):
    try:
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=d_period).mean()
        return k_percent, d_percent
    except:
        return None, None

def calculate_williams_r(high, low, close, period=14):
    try:
        highest_high = high.rolling(window=period).max()
        lowest_low = low.rolling(window=period).min()
        return -100 * ((highest_high - close) / (highest_high - lowest_low))
    except:
        return None

def calculate_bollinger_bands(close, period=20, std_dev=2):
    try:
        middle_band = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        upper_band = middle_band + (std * std_dev)
        lower_band = middle_band - (std * std_dev)
        return upper_band, middle_band, lower_band
    except:
        return None, None, None

def calculate_coppock_curve(close, wma_period=10, roc1_period=14, roc2_period=11):
    try:
        roc1 = ((close - close.shift(roc1_period)) / close.shift(roc1_period)) * 100
        roc2 = ((close - close.shift(roc2_period)) / close.shift(roc2_period)) * 100
        roc_sum = roc1 + roc2
        return roc_sum.rolling(window=wma_period).mean()
    except:
        return None

def calculate_ultimate_oscillator(high, low, close, period1=7, period2=14, period3=28):
    try:
        bp = close - pd.Series(low).combine(close.shift(1), min)
        tr = pd.Series(high).combine(close.shift(1), max) - pd.Series(low).combine(close.shift(1), min)
        avg1 = bp.rolling(window=period1).sum() / tr.rolling(window=period1).sum()
        avg2 = bp.rolling(window=period2).sum() / tr.rolling(window=period2).sum()
        avg3 = bp.rolling(window=period3).sum() / tr.rolling(window=period3).sum()
        return 100 * ((4 * avg1) + (2 * avg2) + avg3) / 7
    except:
        return None

def calculate_all_indicators(df):
    """Calculate all technical indicators"""
    indicators = {}
    try:
        close = df['Close']
        high = df['High']
        low = df['Low']
        
        # MACD
        m, s = calculate_macd(close)
        indicators['macd'] = m.iloc[-1] if m is not None else None
        indicators['macd_buy'] = m.iloc[-1] > s.iloc[-1] if m is not None else False
        
        # RSI
        r = calculate_rsi(close)
        indicators['rsi'] = r.iloc[-1] if r is not None else None
        indicators['rsi_oversold'] = r.iloc[-1] < INDICATOR_THRESHOLDS['rsi_oversold'] if r is not None else False
        
        # Stochastic
        k, d = calculate_stochastic(high, low, close)
        indicators['stoch'] = k.iloc[-1] if k is not None else None
        indicators['stoch_oversold'] = k.iloc[-1] < INDICATOR_THRESHOLDS['stoch_oversold'] if k is not None else False
        
        # Williams %R
        w = calculate_williams_r(high, low, close)
        indicators['willr'] = w.iloc[-1] if w is not None else None
        indicators['willr_oversold'] = w.iloc[-1] < INDICATOR_THRESHOLDS['willr_oversold'] if w is not None else False
        
        # Bollinger Bands
        u, mid, l = calculate_bollinger_bands(close)
        if l is not None:
            indicators['bb_buy'] = (close.iloc[-1] - l.iloc[-1]) / close.iloc[-1] < INDICATOR_THRESHOLDS['bb_distance_pct']
        else:
            indicators['bb_buy'] = False
            
        # Ultimate Oscillator
        u_osc = calculate_ultimate_oscillator(high, low, close)
        indicators['ultimate_buy'] = u_osc.iloc[-1] < 30 if u_osc is not None else False
        
        # Coppock
        c = calculate_coppock_curve(close)
        if c is not None and len(c) > 1:
            indicators['coppock_buy'] = c.iloc[-1] > 0 and c.iloc[-1] > c.iloc[-2]
        else:
            indicators['coppock_buy'] = False
            
        return indicators
    except Exception:
        return None

# =============================================================================
# STOCK ANALYSIS
# =============================================================================

def analyze_stock(ticker, ticker_sources):
    """Analyze stock with all indicators"""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=DATA_CONFIG['history_period'])
        
        if len(df) < DATA_CONFIG['min_data_points']:
            return None
        
        # Calculate PSAR
        psar, is_psar_buy = calculate_psar(df)
        
        # Calculate all other indicators
        indicators = calculate_all_indicators(df)
        
        if indicators is None:
            return None
        
        latest_close = df['Close'].iloc[-1]
        latest_psar = psar[-1]
        
        if pd.isna(latest_close) or latest_close <= 0:
            return None
            
        if pd.isna(latest_psar):
            valid_psar = psar[~pd.isna(psar)]
            if len(valid_psar) > 0:
                latest_psar = valid_psar.iloc[-1]
            else:
                return None
        
        distance_pct = ((latest_close - latest_psar) / latest_close) * 100
        change_pct = ((latest_close - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
        
        try:
            info = stock.info
            company = info.get('longName', ticker)
            sector = info.get('sector', 'N/A')
            div = info.get('dividendYield', 0)
            if div and div > 1: div = div / 100
            dividend_yield = round(div * 100, 2) if div else 0
        except:
            company = ticker
            sector = 'N/A'
            dividend_yield = 0
            
        source = ', '.join(ticker_sources.get(ticker, ['Unknown']))
        
        return {
            'Ticker': ticker,
            'Source': source,
            'Company': company,
            'Sector': sector,
            'Price': round(latest_close, 2),
            'PSAR': round(latest_psar, 2),
            'Distance %': round(distance_pct, 2),
            'Day Change %': round(change_pct, 2),
            'Dividend Yield %': dividend_yield,
            'PSAR_Buy': bool(is_psar_buy),
            'MACD_Buy': bool(indicators['macd_buy']),
            'BB_Buy': bool(indicators['bb_buy']),
            'WillR_Buy': bool(indicators['willr_oversold']),
            'RSI_Oversold': bool(indicators['rsi_oversold']),
            'Stoch_Oversold': bool(indicators['stoch_oversold']),
            'Coppock_Buy': bool(indicators['coppock_buy']),
            'Ultimate_Buy': bool(indicators['ultimate_buy']),
            'RSI': round(indicators['rsi'], 2) if indicators['rsi'] else None
        }
    except Exception:
        return None

# =============================================================================
# CHANGE TRACKING
# =============================================================================

def load_previous_status():
    if os.path.exists('scan_status.json'):
        try:
            with open('scan_status.json', 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_current_status(results_dict):
    def convert(o):
        if isinstance(o, (np.integer, int)): return int(o)
        if isinstance(o, (np.floating, float)): return float(o)
        if isinstance(o, (np.bool_, bool)): return bool(o)
        return str(o)
    
    with open('scan_status.json', 'w') as f:
        json.dump(results_dict, f, default=convert, indent=2)

def detect_changes(previous, current):
    changes = {'new_entries': [], 'new_exits': [], 'recent_exits_7day': []}
    current_time = datetime.now()
    
    exit_history = previous.get('_exit_history', {})
    cleaned_history = {}
    
    # Clean old history
    for ticker, data in exit_history.items():
        try:
            exit_time = datetime.fromisoformat(data['exit_time'])
            if (current_time - exit_time).days < 7:
                cleaned_history[ticker] = data
        except: pass
        
    for ticker, curr in current.items():
        if not curr: continue
        prev = previous.get(ticker, {})
        if not prev: prev = {}
        
        curr_buy = curr['PSAR_Buy']
        prev_buy = prev.get('PSAR_Buy', False)
        
        if curr_buy and not prev_buy:
            changes['new_entries'].append(curr)
            cleaned_history.pop(ticker, None)
        elif not curr_buy and prev_buy:
            changes['new_exits'].append(curr)
            cleaned_history[ticker] = {
                'exit_time': current_time.isoformat(),
                'exit_price': curr['Price'],
                'data': curr
            }
            
    # Process exits for report
    for ticker, info in cleaned_history.items():
        try:
            exit_time = datetime.fromisoformat(info['exit_time'])
            days_ago = (current_time - exit_time).days
            hours_ago = int((current_time - exit_time).total_seconds() / 3600)
            
            data = info['data'].copy()
            if ticker in current and current[ticker]:
                data.update(current[ticker])
                
            data['days_ago'] = days_ago
            data['hours_ago'] = hours_ago
            data['exit_time'] = info['exit_time']
            data['exit_price'] = info['exit_price']
            changes['recent_exits_7day'].append(data)
        except: pass
        
    changes['recent_exits_7day'].sort(key=lambda x: x['exit_time'], reverse=True)
    changes['_exit_history'] = cleaned_history
    return changes

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 100)
    print("MARKET-WIDE MULTI-INDICATOR PSAR SCANNER")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)
    
    # 1. Get Tickers (Using config.py)
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
    
    def add_weights(datalist):
        for d in datalist:
            if 'signal_weight' not in d: d['signal_weight'] = calculate_signal_weight(d)
        return datalist

    if all_buys:
        pd.DataFrame(all_buys).to_csv(os.path.join(csv_dir, 'current_psar_buys.csv'), index=False)
    if changes['new_entries']:
        pd.DataFrame(add_weights(changes['new_entries'])).to_csv(os.path.join(csv_dir, 'new_psar_entries.csv'), index=False)
    if changes['recent_exits_7day']:
        pd.DataFrame(changes['recent_exits_7day']).to_csv(os.path.join(csv_dir, 'recent_exits_7day.csv'), index=False)
        
    results_dict['_exit_history'] = changes.get('_exit_history', {})
    save_current_status(results_dict)
    
    # 6. SEND EMAIL (Using EmailReport class from email_report.py)
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
        # Generate and send report using external class
        report = EmailReport(changes, all_buys, all_early)
        report.send_email(subject)
    else:
        print("No significant changes, email skipped.")
        
    print("\n✓ Done!")

if __name__ == "__main__":
    main()

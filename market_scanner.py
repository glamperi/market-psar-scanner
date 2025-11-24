#!/usr/bin/env python3
"""
Market-Wide Multi-Indicator PSAR Scanner with Email Alerts
Scans S&P 500, NASDAQ 100, Russell 1000, IBD lists, crypto, and indices

Features:
- Scans 500-1000+ stocks automatically
- Same 8 technical indicators as portfolio scanner
- Email alerts for buy/sell signal changes
- Warning section for recent exits
- No Excel attachment (too large for broad market)
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
warnings.filterwarnings('ignore')

# Import configuration
from config import (
    get_all_tickers,
    EMAIL_CONFIG,
    ALERT_ON_ENTRY,
    ALERT_ON_EXIT,
    ALERT_DAILY_SUMMARY,
    INCLUDE_EXCEL_ATTACHMENT,
    INCLUDE_SELL_SIGNALS,
    INDICATOR_THRESHOLDS, 
    PSAR_CONFIG,
    DATA_CONFIG
)

print("Market Scanner - Using manual indicator calculations")

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
    """Calculate Exponential Moving Average"""
    return data.ewm(span=period, adjust=False).mean()

def calculate_macd(close, fast=12, slow=26, signal=9):
    """Calculate MACD"""
    try:
        ema_fast = calculate_ema(close, fast)
        ema_slow = calculate_ema(close, slow)
        macd_line = ema_fast - ema_slow
        signal_line = calculate_ema(macd_line, signal)
        return macd_line, signal_line
    except:
        return None, None

def calculate_rsi(close, period=14):
    """Calculate RSI"""
    try:
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    except:
        return None

def calculate_stochastic(high, low, close, k_period=14, d_period=3):
    """Calculate Stochastic Oscillator"""
    try:
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=d_period).mean()
        return k_percent, d_percent
    except:
        return None, None

def calculate_williams_r(high, low, close, period=14):
    """Calculate Williams %R"""
    try:
        highest_high = high.rolling(window=period).max()
        lowest_low = low.rolling(window=period).min()
        willr = -100 * ((highest_high - close) / (highest_high - lowest_low))
        return willr
    except:
        return None

def calculate_bollinger_bands(close, period=20, std_dev=2):
    """Calculate Bollinger Bands"""
    try:
        middle_band = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        upper_band = middle_band + (std * std_dev)
        lower_band = middle_band - (std * std_dev)
        return upper_band, middle_band, lower_band
    except:
        return None, None, None

def calculate_coppock_curve(close, wma_period=10, roc1_period=14, roc2_period=11):
    """Calculate Coppock Curve"""
    try:
        roc1 = ((close - close.shift(roc1_period)) / close.shift(roc1_period)) * 100
        roc2 = ((close - close.shift(roc2_period)) / close.shift(roc2_period)) * 100
        roc_sum = roc1 + roc2
        coppock = roc_sum.rolling(window=wma_period).mean()
        return coppock
    except:
        return None

def calculate_ultimate_oscillator(high, low, close, period1=7, period2=14, period3=28):
    """Calculate Ultimate Oscillator"""
    try:
        bp = close - pd.Series(low).combine(close.shift(1), min)
        tr = pd.Series(high).combine(close.shift(1), max) - pd.Series(low).combine(close.shift(1), min)
        
        avg1 = bp.rolling(window=period1).sum() / tr.rolling(window=period1).sum()
        avg2 = bp.rolling(window=period2).sum() / tr.rolling(window=period2).sum()
        avg3 = bp.rolling(window=period3).sum() / tr.rolling(window=period3).sum()
        
        uo = 100 * ((4 * avg1) + (2 * avg2) + avg3) / 7
        return uo
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
        try:
            macd_line, signal_line = calculate_macd(close)
            if macd_line is not None:
                indicators['macd'] = macd_line.iloc[-1]
                indicators['macd_signal'] = signal_line.iloc[-1]
                indicators['macd_buy'] = macd_line.iloc[-1] > signal_line.iloc[-1]
            else:
                indicators['macd'] = None
                indicators['macd_signal'] = None
                indicators['macd_buy'] = False
        except:
            indicators['macd'] = None
            indicators['macd_signal'] = None
            indicators['macd_buy'] = False
        
        # RSI
        try:
            rsi = calculate_rsi(close)
            if rsi is not None:
                indicators['rsi'] = rsi.iloc[-1]
                indicators['rsi_oversold'] = rsi.iloc[-1] < INDICATOR_THRESHOLDS['rsi_oversold']
            else:
                indicators['rsi'] = None
                indicators['rsi_oversold'] = False
        except:
            indicators['rsi'] = None
            indicators['rsi_oversold'] = False
        
        # Stochastic
        try:
            k_percent, d_percent = calculate_stochastic(high, low, close)
            if k_percent is not None:
                indicators['stoch'] = k_percent.iloc[-1]
                indicators['stoch_oversold'] = k_percent.iloc[-1] < INDICATOR_THRESHOLDS['stoch_oversold']
            else:
                indicators['stoch'] = None
                indicators['stoch_oversold'] = False
        except:
            indicators['stoch'] = None
            indicators['stoch_oversold'] = False
        
        # Williams %R
        try:
            willr = calculate_williams_r(high, low, close)
            if willr is not None:
                indicators['willr'] = willr.iloc[-1]
                indicators['willr_oversold'] = willr.iloc[-1] < INDICATOR_THRESHOLDS['willr_oversold']
            else:
                indicators['willr'] = None
                indicators['willr_oversold'] = False
        except:
            indicators['willr'] = None
            indicators['willr_oversold'] = False
        
        # Bollinger Bands
        try:
            upper_band, middle_band, lower_band = calculate_bollinger_bands(close)
            if lower_band is not None:
                indicators['bb_lower'] = lower_band.iloc[-1]
                indicators['bb_upper'] = upper_band.iloc[-1]
                indicators['price'] = close.iloc[-1]
                indicators['bb_buy'] = (close.iloc[-1] - lower_band.iloc[-1]) / close.iloc[-1] < INDICATOR_THRESHOLDS['bb_distance_pct']
            else:
                indicators['bb_lower'] = None
                indicators['bb_upper'] = None
                indicators['price'] = close.iloc[-1]
                indicators['bb_buy'] = False
        except:
            indicators['bb_lower'] = None
            indicators['bb_upper'] = None
            indicators['price'] = close.iloc[-1]
            indicators['bb_buy'] = False
        
        # Ultimate Oscillator
        try:
            uo = calculate_ultimate_oscillator(high, low, close)
            if uo is not None:
                indicators['ultimate'] = uo.iloc[-1]
                indicators['ultimate_buy'] = uo.iloc[-1] < 30
            else:
                indicators['ultimate'] = None
                indicators['ultimate_buy'] = False
        except:
            indicators['ultimate'] = None
            indicators['ultimate_buy'] = False
        
        # Coppock Curve
        try:
            coppock = calculate_coppock_curve(close)
            if coppock is not None and len(coppock) > 1:
                indicators['coppock'] = coppock.iloc[-1]
                indicators['coppock_buy'] = coppock.iloc[-1] > 0 and coppock.iloc[-1] > coppock.iloc[-2]
            else:
                indicators['coppock'] = None
                indicators['coppock_buy'] = False
        except:
            indicators['coppock'] = None
            indicators['coppock_buy'] = False
        
        return indicators
        
    except Exception as e:
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
        
        # Get additional data
        latest_close = df['Close'].iloc[-1]
        latest_psar = psar[-1]
        distance_pct = ((latest_close - latest_psar) / latest_close) * 100
        change_pct = ((latest_close - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
        
        # Get company info
        try:
            info = stock.info
            company = info.get('longName', ticker)
            sector = info.get('sector', 'N/A')
        except:
            company = ticker
            sector = 'N/A'
        
        # Get source
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
            'PSAR_Buy': bool(is_psar_buy),
            'MACD_Buy': bool(indicators['macd_buy']),
            'BB_Buy': bool(indicators['bb_buy']),
            'WillR_Buy': bool(indicators['willr_oversold']),
            'RSI_Oversold': bool(indicators['rsi_oversold']),
            'Stoch_Oversold': bool(indicators['stoch_oversold']),
            'Coppock_Buy': bool(indicators['coppock_buy']),
            'Ultimate_Buy': bool(indicators['ultimate_buy']),
            'MACD': round(indicators['macd'], 2) if indicators['macd'] else None,
            'RSI': round(indicators['rsi'], 2) if indicators['rsi'] else None,
            'Stoch': round(indicators['stoch'], 2) if indicators['stoch'] else None,
            'WillR': round(indicators['willr'], 2) if indicators['willr'] else None,
            'Coppock': round(indicators['coppock'], 2) if indicators['coppock'] else None,
            'Ultimate': round(indicators['ultimate'], 2) if indicators['ultimate'] else None
        }
        
    except Exception as e:
        return None

# =============================================================================
# CHANGE TRACKING & ALERTS
# =============================================================================

def load_previous_status():
    """Load previous scan results"""
    if os.path.exists('scan_status.json'):
        try:
            with open('scan_status.json', 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Warning: Previous scan_status.json corrupted: {e}")
            if os.path.exists('scan_status.json'):
                os.rename('scan_status.json', 'scan_status.json.corrupted')
            return {}
    return {}

def save_current_status(results_dict):
    """Save current scan results"""
    def convert_to_serializable(obj):
        if isinstance(obj, dict):
            return {k: convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [convert_to_serializable(item) for item in obj]
        elif hasattr(obj, 'item'):
            return obj.item()
        elif isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        elif isinstance(obj, (np.integer, int)):
            return int(obj)
        elif isinstance(obj, (np.floating, float)):
            return float(obj)
        elif obj is None or isinstance(obj, str):
            return obj
        else:
            return str(obj)
    
    serializable_dict = convert_to_serializable(results_dict)
    with open('scan_status.json', 'w') as f:
        json.dump(serializable_dict, f, indent=2)

def detect_changes(previous, current):
    """Detect entry/exit changes"""
    changes = {
        'new_entries': [],
        'new_exits': [],
        'still_buy': [],
        'still_sell': []
    }
    
    for ticker, curr_data in current.items():
        if curr_data is None:
            continue
            
        prev_data = previous.get(ticker, {})
        prev_is_buy = prev_data.get('PSAR_Buy', False)
        curr_is_buy = curr_data['PSAR_Buy']
        
        if curr_is_buy and not prev_is_buy:
            changes['new_entries'].append(curr_data)
        elif not curr_is_buy and prev_is_buy:
            changes['new_exits'].append(curr_data)
        elif curr_is_buy:
            changes['still_buy'].append(curr_data)
        else:
            changes['still_sell'].append(curr_data)
    
    return changes

# [CONTINUED IN NEXT FILE DUE TO LENGTH]

# =============================================================================
# EMAIL ALERTS
# =============================================================================

def send_email_alert(subject, body):
    """Send email alert"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['sender_email']
        msg['To'] = EMAIL_CONFIG['recipient_email']
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
        server.send_message(msg)
        server.quit()
        
        print(f"✓ Email sent: {subject}")
        return True
    except Exception as e:
        print(f"✗ Email failed: {e}")
        return False

def format_alert_email(changes, all_buys, all_early):
    """Format changes into HTML email - IDENTICAL to portfolio scanner format"""
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2>📊 Market-Wide PSAR Scanner Report</h2>
        <h3>Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</h3>
        <hr>
    """
    
    # WARNING: Recent exits
    if changes['new_exits']:
        html += """
        <div style="background-color: #FFE0E0; border: 3px solid #FF0000; padding: 15px; margin: 10px 0;">
            <h2 style="color: red;">⚠️ WARNING: The Following Went from PSAR Buy to Sell Recently! ⚠️</h2>
            <table border="1" cellpadding="5" style="border-collapse: collapse;">
                <tr style="background-color: #FFB6C1;">
                    <th>Ticker</th><th>Company</th><th>Source</th><th>Price</th><th>PSAR</th><th>Distance %</th><th>Day Change %</th><th>MACD</th><th>RSI</th>
                </tr>
        """
        for pos in sorted(changes['new_exits'], key=lambda x: x.get('Day Change %', 0)):
            html += f"""
            <tr>
                <td><strong>{pos['Ticker']}</strong></td>
                <td>{pos.get('Company', 'N/A')[:30]}</td>
                <td><small>{pos.get('Source', 'N/A')[:20]}</small></td>
                <td>${pos['Price']}</td>
                <td>${pos['PSAR']}</td>
                <td>{pos['Distance %']}%</td>
                <td style="color: {'green' if pos['Day Change %'] > 0 else 'red'};">{pos['Day Change %']:+.2f}%</td>
                <td>{pos.get('MACD', 'N/A')}</td>
                <td>{pos.get('RSI', 'N/A')}</td>
            </tr>
            """
        html += """
            </table>
        </div>
        <hr>
        """
    
    # Indicator Comparison Table
    html += """
    <h2>📊 Technical Indicator Comparison Guide</h2>
    <table border="2" cellpadding="8" style="border-collapse: collapse; margin: 15px 0;">
        <tr style="background-color: #4472C4; color: white;">
            <th>Indicator</th><th>Timing</th><th>Accuracy</th><th>Best For</th>
        </tr>
        <tr>
            <td><strong>RSI</strong></td>
            <td>Early</td>
            <td>Medium</td>
            <td>Oversold bounces</td>
        </tr>
        <tr>
            <td><strong>Stochastic</strong></td>
            <td>Very Early</td>
            <td>Low</td>
            <td>Day trading</td>
        </tr>
        <tr>
            <td><strong>MACD</strong></td>
            <td>Medium</td>
            <td>High</td>
            <td>Trend reversals ⭐</td>
        </tr>
        <tr>
            <td><strong>PSAR</strong></td>
            <td>Late</td>
            <td>Very High</td>
            <td>Confirmed trends</td>
        </tr>
        <tr>
            <td><strong>Bollinger Bands</strong></td>
            <td>Early</td>
            <td>Medium</td>
            <td>Volatility plays</td>
        </tr>
        <tr>
            <td><strong>Williams %R</strong></td>
            <td>Very Early</td>
            <td>Low-Medium</td>
            <td>Short-term reversals</td>
        </tr>
        <tr>
            <td><strong>Coppock Curve</strong></td>
            <td>Very Late</td>
            <td>High</td>
            <td>Major bottoms (long-term)</td>
        </tr>
        <tr>
            <td><strong>Ultimate Oscillator</strong></td>
            <td>Early-Medium</td>
            <td>High</td>
            <td>Multi-timeframe confirmation</td>
        </tr>
    </table>
    <p><em>Note: Combine multiple indicators for higher probability trades. PSAR confirms the trend after early indicators fire.</em></p>
    <hr>
    """
    
    # Alert section for NEW changes
    if changes['new_entries']:
        html += """
        <h2>🚨 NEW POSITION CHANGES</h2>
        <h3 style="color: green;">🟢 NEW BUY SIGNALS (Recently Entered PSAR Buy)</h3>
        <table border="1" cellpadding="5" style="border-collapse: collapse;">
            <tr style="background-color: #90EE90;">
                <th>Ticker</th><th>Company</th><th>Source</th><th>Price</th><th>Distance %</th><th>Day Chg %</th><th>MACD</th><th>BB</th><th>Coppock</th><th>Ultimate</th><th>RSI</th>
            </tr>
        """
        for pos in sorted(changes['new_entries'], key=lambda x: x.get('Distance %', 999)):
            html += f"""
            <tr>
                <td><strong>{pos['Ticker']}</strong></td>
                <td>{pos.get('Company', 'N/A')[:30]}</td>
                <td><small>{pos.get('Source', 'N/A')[:20]}</small></td>
                <td>${pos['Price']}</td>
                <td>{pos['Distance %']}%</td>
                <td style="color: {'green' if pos['Day Change %'] > 0 else 'red'};">{pos['Day Change %']:+.2f}%</td>
                <td>{'✓' if pos.get('MACD_Buy') else ''}</td>
                <td>{'✓' if pos.get('BB_Buy') else ''}</td>
                <td>{'✓' if pos.get('Coppock_Buy') else ''}</td>
                <td>{'✓' if pos.get('Ultimate_Buy') else ''}</td>
                <td>{pos.get('RSI', 'N/A')}</td>
            </tr>
            """
        html += "</table><br><hr>"
    
    # Summary statistics
    html += f"""
    <h2>📈 Summary Statistics</h2>
    <table border="1" cellpadding="8" style="border-collapse: collapse;">
        <tr>
            <td style="background-color: #90EE90;"><strong>🟢 Confirmed Buy Signals (PSAR Green)</strong></td>
            <td><strong>{len(all_buys)}</strong></td>
        </tr>
        <tr>
            <td style="background-color: #FFFF99;"><strong>🟡 Early Buy Signals (Building)</strong></td>
            <td><strong>{len(all_early)}</strong></td>
        </tr>
        <tr>
            <td><strong>🚨 New Entries (Since Last Scan)</strong></td>
            <td><strong>{len(changes['new_entries'])}</strong></td>
        </tr>
        <tr>
            <td><strong>⚠️ New Exits (Since Last Scan)</strong></td>
            <td><strong>{len(changes['new_exits'])}</strong></td>
        </tr>
    </table>
    <br>
    """
    
    # ALL PSAR Buy Signals (limit to top 50 for email)
    if all_buys:
        top_buys = sorted(all_buys, key=lambda x: x['Distance %'])[:50]
        html += f"""
        <h3>🟢 CURRENT BUY SIGNALS (Top 50 by Distance to PSAR)</h3>
        <p><em>Showing {len(top_buys)} of {len(all_buys)} total PSAR buy signals</em></p>
        <table border="1" cellpadding="5" style="border-collapse: collapse;">
            <tr style="background-color: #E0FFE0;">
                <th>Ticker</th><th>Company</th><th>Source</th><th>Price</th><th>Dist %</th><th>Day Chg %</th><th>MACD</th><th>BB</th><th>Coppock</th><th>Ultimate</th><th>RSI</th>
            </tr>
        """
        for pos in top_buys:
            html += f"""
            <tr>
                <td><strong>{pos['Ticker']}</strong></td>
                <td>{pos.get('Company', 'N/A')[:25]}</td>
                <td><small>{pos.get('Source', 'N/A')[:15]}</small></td>
                <td>${pos['Price']}</td>
                <td>{pos['Distance %']}%</td>
                <td style="color: {'green' if pos['Day Change %'] > 0 else 'red'};">{pos['Day Change %']:+.2f}%</td>
                <td>{'✓' if pos.get('MACD_Buy') else ''}</td>
                <td>{'✓' if pos.get('BB_Buy') else ''}</td>
                <td>{'✓' if pos.get('Coppock_Buy') else ''}</td>
                <td>{'✓' if pos.get('Ultimate_Buy') else ''}</td>
                <td>{pos.get('RSI', 'N/A')}</td>
            </tr>
            """
        html += "</table><br>"
    
    # ALL Early Buy Signals (limit to top 30 for email)
    if all_early:
        # Count signal strength
        for pos in all_early:
            pos['signal_count'] = sum([
                pos.get('MACD_Buy', False),
                pos.get('BB_Buy', False),
                pos.get('WillR_Buy', False),
                pos.get('Coppock_Buy', False),
                pos.get('Ultimate_Buy', False)
            ])
        
        top_early = sorted(all_early, key=lambda x: x['signal_count'], reverse=True)[:30]
        html += f"""
        <h3>🟡 EARLY BUY SIGNALS (Top 30 by Signal Count)</h3>
        <p><em>Showing {len(top_early)} of {len(all_early)} total early signals</em></p>
        <table border="1" cellpadding="5" style="border-collapse: collapse;">
            <tr style="background-color: #FFFFE0;">
                <th>Ticker</th><th>Company</th><th>Source</th><th>Price</th><th>Day Chg %</th><th>Signals</th><th>MACD</th><th>BB</th><th>Coppock</th><th>Ultimate</th><th>RSI</th>
            </tr>
        """
        for pos in top_early:
            html += f"""
            <tr>
                <td><strong>{pos['Ticker']}</strong></td>
                <td>{pos.get('Company', 'N/A')[:25]}</td>
                <td><small>{pos.get('Source', 'N/A')[:15]}</small></td>
                <td>${pos['Price']}</td>
                <td style="color: {'green' if pos['Day Change %'] > 0 else 'red'};">{pos['Day Change %']:+.2f}%</td>
                <td><strong>{pos['signal_count']}</strong></td>
                <td>{'✓' if pos.get('MACD_Buy') else ''}</td>
                <td>{'✓' if pos.get('BB_Buy') else ''}</td>
                <td>{'✓' if pos.get('Coppock_Buy') else ''}</td>
                <td>{'✓' if pos.get('Ultimate_Buy') else ''}</td>
                <td>{pos.get('RSI', 'N/A')}</td>
            </tr>
            """
        html += "</table><br>"
    
    html += f"""
        <hr>
        <p><em>Tip: Focus on stocks with multiple ✓ marks for stronger confirmation.</em></p>
        <p><em>Note: Excel attachment not included due to large dataset size. Full data saved in GitHub Actions artifacts.</em></p>
        <p><small>Automated report from Market-Wide PSAR Scanner</small></p>
    </body>
    </html>
    """
    
    return html

# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    print("=" * 100)
    print("MARKET-WIDE MULTI-INDICATOR PSAR SCANNER")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)
    print()
    
    # Get all tickers
    all_tickers, ticker_sources = get_all_tickers()
    
    print(f"\nScanning {len(all_tickers)} stocks from broad market...")
    print("This will take 10-20 minutes...")
    print()
    
    results = []
    results_dict = {}
    total = len(all_tickers)
    
    for i, ticker in enumerate(all_tickers, 1):
        if i % 50 == 0 or i == total:
            print(f"Progress: {i}/{total} ({(i/total)*100:.1f}%)")
        
        result = analyze_stock(ticker, ticker_sources)
        if result:
            results.append(result)
            results_dict[ticker] = result
        else:
            results_dict[ticker] = None
    
    if not results:
        print("\nNo results found!")
        return
    
    df_all = pd.DataFrame(results)
    
    # Separate into categories
    all_buys = df_all[df_all['PSAR_Buy'] == True].to_dict('records')
    
    all_early = df_all[
        (df_all['PSAR_Buy'] == False) &
        ((df_all['MACD_Buy'] == True) |
         (df_all['BB_Buy'] == True) |
         (df_all['WillR_Buy'] == True) |
         (df_all['Coppock_Buy'] == True) |
         (df_all['Ultimate_Buy'] == True))
    ].to_dict('records')
    
    # Detect changes
    print("\n" + "=" * 100)
    print("CHECKING FOR CHANGES...")
    print("=" * 100)
    previous_status = load_previous_status()
    changes = detect_changes(previous_status, results_dict)
    
    print(f"  New buy signals: {len(changes['new_entries'])}")
    print(f"  New sell signals: {len(changes['new_exits'])}")
    print(f"  Total PSAR buys: {len(all_buys)}")
    print(f"  Total early signals: {len(all_early)}")
    
    # Save current status
    save_current_status(results_dict)
    
    # Send email alert
    print("\n" + "=" * 100)
    print("SENDING EMAIL ALERT...")
    print("=" * 100)
    
    should_alert = False
    alert_subject = f"📊 Market Scanner Report - {datetime.now().strftime('%Y-%m-%d')}"
    
    if changes['new_entries'] and ALERT_ON_ENTRY:
        should_alert = True
        alert_subject = f"🟢 {len(changes['new_entries'])} New PSAR Buy Signals! - {datetime.now().strftime('%Y-%m-%d')}"
    
    if changes['new_exits'] and ALERT_ON_EXIT:
        should_alert = True
        if "New PSAR Buy" not in alert_subject:
            alert_subject = f"🔴 {len(changes['new_exits'])} PSAR Exit Signals! - {datetime.now().strftime('%Y-%m-%d')}"
    
    if ALERT_DAILY_SUMMARY or should_alert or len(previous_status) == 0:
        email_body = format_alert_email(changes, all_buys, all_early)
        send_email_alert(alert_subject, email_body)
    else:
        print("No significant changes detected, email skipped")
    
    # Print summary
    print()
    print("=" * 100)
    print("SUMMARY:")
    print("=" * 100)
    print(f"🟢 PSAR Buy Signals: {len(all_buys)} stocks")
    print(f"🟡 Early Buy Signals: {len(all_early)} stocks")
    print(f"🆕 New Entries: {len(changes['new_entries'])} stocks")
    print(f"⚠️  New Exits: {len(changes['new_exits'])} stocks")
    print("=" * 100)
    
    print("\n✓ Done!")

if __name__ == "__main__":
    main()
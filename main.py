#!/usr/bin/env python3
"""
Market PSAR Scanner V2
======================
Main entry point with full email integration.

Usage:
    python main.py                    # Full market scan + email
    python main.py -mystocks          # Portfolio scan + email
    python main.py -friends           # Friends watchlist + email
    python main.py -shorts            # Short candidates + email
    python main.py --no-email         # Scan without email
    python main.py --classic          # Use V1 logic for comparison
"""

import argparse
import sys
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional, List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Module imports
try:
    from indicators import get_all_indicators
    from signals import get_complete_signal, Zone, ZONE_CONFIG
    from scanners import (
        SmartBuyScanner,
        SmartShortScanner, 
        PortfolioScanner,
        FriendsScanner,
        ScanResult
    )
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure all modules are in the correct location.")
    sys.exit(1)

# Import existing utilities
try:
    from data.cboe import get_cboe_ratios_and_analyze
except ImportError:
    try:
        from cboe import get_cboe_ratios_and_analyze
    except ImportError:
        def get_cboe_ratios_and_analyze():
            return "CBOE data unavailable"

try:
    from data.ibd_utils import format_ibd_ticker, get_ibd_url
except ImportError:
    try:
        from ibd_utils import format_ibd_ticker, get_ibd_url
    except ImportError:
        format_ibd_ticker = None
        get_ibd_url = None

# Covered call analysis
try:
    from analysis.covered_calls import analyze_covered_call, build_covered_call_section
except ImportError:
    analyze_covered_call = None
    build_covered_call_section = None

# Shorts analysis
try:
    from analysis.shorts import (
        analyze_short_candidate, 
        build_shorts_report_html,
        get_short_interest,
        get_squeeze_risk
    )
except ImportError:
    analyze_short_candidate = None
    build_shorts_report_html = None
    get_short_interest = None
    get_squeeze_risk = None


# =============================================================================
# HTML EMAIL GENERATION
# =============================================================================

ZONE_COLORS = {
    'STRONG_BUY': '#1e8449',
    'BUY': '#27ae60',
    'EARLY_BUY': '#3498db',
    'HOLD': '#f39c12',
    'NEUTRAL': '#7f8c8d',
    'WARNING': '#e67e22',
    'WEAK': '#e67e22',
    'SELL': '#c0392b',
    'OVERSOLD_WATCH': '#8e44ad',
}

ZONE_EMOJIS = {
    'STRONG_BUY': '🟢🟢',
    'BUY': '🟢',
    'EARLY_BUY': '⚡',
    'HOLD': '⏸️',
    'NEUTRAL': '🟡',
    'WARNING': '⚠️',
    'WEAK': '🟠',
    'SELL': '🔴',
    'OVERSOLD_WATCH': '❄️',
}

GRADE_COLORS = {
    'A': '#1e8449',
    'B': '#27ae60',
    'C': '#f39c12',
    'D': '#e67e22',
    'X': '#c0392b',
}


def get_zone_color(zone: str) -> str:
    return ZONE_COLORS.get(zone, '#7f8c8d')


def get_zone_emoji(zone: str) -> str:
    return ZONE_EMOJIS.get(zone, '⚪')


def get_momentum_display(momentum: int, use_v2: bool = True) -> str:
    """Get colored momentum score with V2 interpretation."""
    if use_v2:
        # V2: 5-7 is ideal, 9-10 is exhausted
        if momentum >= 9:
            return f"<span style='color:#c0392b; font-weight:bold;' title='Exhausted - HOLD only'>{momentum}⏸️</span>"
        elif momentum >= 7:
            return f"<span style='color:#e67e22;' title='Strong but late'>{momentum}🔥</span>"
        elif momentum >= 5:
            return f"<span style='color:#27ae60; font-weight:bold;' title='Ideal entry zone'>{momentum}✨</span>"
        elif momentum >= 3:
            return f"<span style='color:#f39c12;' title='Building'>{momentum}</span>"
        else:
            return f"<span style='color:#c0392b;' title='Weak'>{momentum}</span>"
    else:
        # V1 classic
        if momentum >= 8:
            return f"<span style='color:#1e8449; font-weight:bold;'>{momentum}</span>"
        elif momentum >= 6:
            return f"<span style='color:#27ae60;'>{momentum}</span>"
        elif momentum >= 4:
            return f"<span style='color:#f39c12;'>{momentum}</span>"
        else:
            return f"<span style='color:#c0392b;'>{momentum}</span>"


def get_prsi_display(prsi_bullish: bool) -> str:
    """Get PRSI trend display."""
    if prsi_bullish:
        return "<span style='color:#27ae60;'>↗️</span>"
    else:
        return "<span style='color:#c0392b;'>↘️</span>"


def get_obv_display(obv_bullish: Optional[bool]) -> str:
    """Get OBV status display."""
    if obv_bullish is True:
        return "<span style='color:#27ae60;'>🟢</span>"
    elif obv_bullish is False:
        return "<span style='color:#c0392b;'>🔴</span>"
    else:
        return "<span style='color:#f39c12;'>🟡</span>"


def get_grade_display(grade: str, score: int) -> str:
    """Get entry grade display."""
    color = GRADE_COLORS.get(grade, '#7f8c8d')
    return f"<span style='color:{color}; font-weight:bold;'>{grade}</span>({score})"


def get_ticker_display(result: ScanResult) -> str:
    """Format ticker with IBD star and link if applicable."""
    if result.ibd_stock and result.ibd_url:
        return f"<a href='{result.ibd_url}' target='_blank' style='text-decoration:none;'>⭐</a>{result.ticker}"
    elif result.ibd_stock:
        return f"⭐{result.ticker}"
    else:
        return result.ticker


def build_results_table(results: List[ScanResult], zone: str, use_v2: bool = True, is_portfolio_mode: bool = False) -> str:
    """Build HTML table for a zone section."""
    if not results:
        return ""
    
    # Section header class mapping
    section_class = {
        'STRONG_BUY': 'strongbuy',
        'BUY': 'buy',
        'EARLY_BUY': 'earlybuy',
        'HOLD': 'hold',
        'NEUTRAL': 'hold',
        'WARNING': 'warning',
        'WEAK': 'warning',
        'SELL': 'sell',
        'OVERSOLD_WATCH': 'oversold',
        'DIVIDEND': 'dividend',
    }.get(zone, 'hold')
    
    # ATR column only for portfolio/friends mode (not dividend or early buy)
    show_atr = is_portfolio_mode and zone not in ['DIVIDEND', 'EARLY_BUY']
    
    # Different columns for Early Buy vs others
    if zone == 'EARLY_BUY':
        # Early Buy: show PRSI days and Williams for sorting visibility
        header = """
            <th>Ticker</th>
            <th>Price</th>
            <th>PSAR%</th>
            <th>Days</th>
            <th>PRSI</th>
            <th>OBV</th>
            <th>Will%R</th>
            <th>DMI</th>
            <th>ADX</th>
            <th>MACD</th>
        """
        days_col = 'prsi'  # Days since PRSI flipped
    elif zone == 'DIVIDEND':
        # Dividend: include Signal and Yield columns
        header = """
            <th>Ticker</th>
            <th>Price</th>
            <th>PSAR%</th>
            <th>Days</th>
            <th>Signal</th>
            <th>PRSI</th>
            <th>OBV</th>
            <th>DMI</th>
            <th>ADX</th>
            <th>MACD</th>
            <th>Yield</th>
        """
        days_col = 'psar'
    elif show_atr:
        # Portfolio mode: add ATR column
        header = """
            <th>Ticker</th>
            <th>Price</th>
            <th>PSAR%</th>
            <th>Days</th>
            <th>PRSI</th>
            <th>OBV</th>
            <th>DMI</th>
            <th>ADX</th>
            <th>MACD</th>
            <th>ATR%</th>
        """
        days_col = 'psar'
    else:
        # Strong Buy / Buy / Hold / Sell: show PSAR days
        header = """
            <th>Ticker</th>
            <th>Price</th>
            <th>PSAR%</th>
            <th>Days</th>
            <th>PRSI</th>
            <th>OBV</th>
            <th>DMI</th>
            <th>ADX</th>
            <th>MACD</th>
        """
        days_col = 'psar'  # Days since price crossed PSAR
    
    html = f"""
    <table>
        <tr class='th-{section_class}'>
            {header}
        </tr>
    """
    
    for r in results:
        ticker_display = get_ticker_display(r)
        zone_color = get_zone_color(r.zone)
        
        # Days column - different meaning based on section
        if days_col == 'prsi':
            days_display = r.prsi_days_since_flip
        else:
            days_display = getattr(r, 'psar_days_in_trend', 0)
        
        # Checkbox displays
        dmi_check = '✓' if getattr(r, 'dmi_bullish', False) else '✗'
        adx_check = '✓' if getattr(r, 'adx_strong', False) else '✗'
        macd_check = '✓' if getattr(r, 'macd_bullish', False) else '✗'
        
        # Color for checkboxes
        dmi_color = '#27ae60' if getattr(r, 'dmi_bullish', False) else '#e74c3c'
        adx_color = '#27ae60' if getattr(r, 'adx_strong', False) else '#e74c3c'
        macd_color = '#27ae60' if getattr(r, 'macd_bullish', False) else '#e74c3c'
        
        # ATR color coding and covered call suggestion
        # Green: ATR < 3% (low volatility)
        # Yellow: ATR 3-5% (moderate)
        # Red: ATR > 5% (high - consider covered calls)
        atr_pct = getattr(r, 'atr_percent', 0)
        if atr_pct >= 5:
            atr_color = '#e74c3c'  # Red - high volatility
            atr_display = f"{atr_pct:.1f}% 📞"  # Phone emoji suggests "call"
        elif atr_pct >= 3:
            atr_color = '#f39c12'  # Yellow/orange - moderate
            atr_display = f"{atr_pct:.1f}%"
        else:
            atr_color = '#27ae60'  # Green - low volatility
            atr_display = f"{atr_pct:.1f}%"
        
        if zone == 'EARLY_BUY':
            # Show Williams %R for early buys
            williams = getattr(r, 'williams_r', -50)
            williams_display = f"{williams:.0f}"
            html += f"""
        <tr>
            <td><strong>{ticker_display}</strong></td>
            <td>${r.price:.2f}</td>
            <td style='color:{zone_color}; font-weight:bold;'>{r.psar_gap:+.1f}%</td>
            <td>{days_display}</td>
            <td>{get_prsi_display(r.prsi_bullish)}</td>
            <td>{get_obv_display(r.obv_bullish)}</td>
            <td>{williams_display}</td>
            <td style='color:{dmi_color};'>{dmi_check}</td>
            <td style='color:{adx_color};'>{adx_check}</td>
            <td style='color:{macd_color};'>{macd_check}</td>
        </tr>
            """
        elif zone == 'DIVIDEND':
            # Show Signal (Strong/Buy) and Yield for dividends
            days_in_trend = getattr(r, 'psar_days_in_trend', 999)
            if days_in_trend <= 5:
                signal_display = "<span style='color:#1e8449; font-weight:bold;'>🟢🟢 Strong</span>"
            else:
                signal_display = "<span style='color:#27ae60;'>🟢 Buy</span>"
            yield_display = f"{r.dividend_yield:.1f}%" if r.dividend_yield and r.dividend_yield > 0 else "-"
            html += f"""
        <tr>
            <td><strong>{ticker_display}</strong></td>
            <td>${r.price:.2f}</td>
            <td style='color:{zone_color}; font-weight:bold;'>{r.psar_gap:+.1f}%</td>
            <td>{days_display}</td>
            <td>{signal_display}</td>
            <td>{get_prsi_display(r.prsi_bullish)}</td>
            <td>{get_obv_display(r.obv_bullish)}</td>
            <td style='color:{dmi_color};'>{dmi_check}</td>
            <td style='color:{adx_color};'>{adx_check}</td>
            <td style='color:{macd_color};'>{macd_check}</td>
            <td>{yield_display}</td>
        </tr>
            """
        elif show_atr:
            # Portfolio mode with ATR column
            html += f"""
        <tr>
            <td><strong>{ticker_display}</strong></td>
            <td>${r.price:.2f}</td>
            <td style='color:{zone_color}; font-weight:bold;'>{r.psar_gap:+.1f}%</td>
            <td>{days_display}</td>
            <td>{get_prsi_display(r.prsi_bullish)}</td>
            <td>{get_obv_display(r.obv_bullish)}</td>
            <td style='color:{dmi_color};'>{dmi_check}</td>
            <td style='color:{adx_color};'>{adx_check}</td>
            <td style='color:{macd_color};'>{macd_check}</td>
            <td style='color:{atr_color}; font-weight:bold;'>{atr_display}</td>
        </tr>
            """
        else:
            # Standard row (market mode, no ATR)
            html += f"""
        <tr>
            <td><strong>{ticker_display}</strong></td>
            <td>${r.price:.2f}</td>
            <td style='color:{zone_color}; font-weight:bold;'>{r.psar_gap:+.1f}%</td>
            <td>{days_display}</td>
            <td>{get_prsi_display(r.prsi_bullish)}</td>
            <td>{get_obv_display(r.obv_bullish)}</td>
            <td style='color:{dmi_color};'>{dmi_check}</td>
            <td style='color:{adx_color};'>{adx_check}</td>
            <td style='color:{macd_color};'>{macd_check}</td>
        </tr>
            """
    
    html += "</table>"
    return html


def build_email_body(
    results: List[ScanResult],
    mode: str,
    use_v2: bool = True,
    cboe_text: str = "",
    total_scanned: int = 0,
    div_threshold: float = 2.0,
    strong_buy_limit: int = 100,
    early_buy_limit: int = 50,
    dividend_limit: int = 30
) -> str:
    """Build complete HTML email body with actionable sections."""
    
    html = """
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; font-size: 12px; }
            table { border-collapse: collapse; width: 100%; margin: 10px 0; }
            th { padding: 8px; text-align: left; font-size: 11px; }
            td { padding: 6px; border-bottom: 1px solid #ddd; font-size: 11px; }
            tr:hover { background-color: #f5f5f5; }
            
            .section-earlybuy { background-color: #2980b9; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
            .section-strongbuy { background-color: #1e8449; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
            .section-buy { background-color: #27ae60; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
            .section-hold { background-color: #f39c12; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
            .section-oversold { background-color: #8e44ad; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
            .section-warning { background-color: #e67e22; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
            .section-sell { background-color: #c0392b; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
            .section-dividend { background-color: #27ae60; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
            
            .th-earlybuy { background-color: #2980b9; color: white; }
            .th-strongbuy { background-color: #1e8449; color: white; }
            .th-buy { background-color: #27ae60; color: white; }
            .th-hold { background-color: #f39c12; color: white; }
            .th-oversold { background-color: #8e44ad; color: white; }
            .th-warning { background-color: #e67e22; color: white; }
            .th-sell { background-color: #c0392b; color: white; }
            .th-dividend { background-color: #27ae60; color: white; }
            
            .summary-box { background-color: #ecf0f1; padding: 15px; margin: 15px 0; border-radius: 5px; }
            .v2-note { background-color: #e8f6f3; border-left: 4px solid #1abc9c; padding: 10px; margin: 10px 0; font-size: 11px; }
            .action-box { background-color: #d5f4e6; border-left: 4px solid #27ae60; padding: 10px; margin: 10px 0; }
        </style>
    </head>
    <body>
    """
    
    version = "V2 (PRSI-Primary)" if use_v2 else "V1 (Classic)"
    html += f"<h2>📈 Market Scanner {version} - {datetime.now().strftime('%Y-%m-%d %H:%M')}</h2>"
    html += f"<p style='color:#7f8c8d; font-size:11px;'>Mode: {mode} | Scanned: {total_scanned} | Analyzed: {len(results)}</p>"
    
    # CBOE sentiment
    if cboe_text:
        html += f"""
        <div style='background-color:#ecf0f1; border-left:4px solid #2c3e50; padding:12px; margin:10px 0;'>
            <pre style='font-family: monospace; white-space: pre-wrap; margin: 0; font-size: 12px; color: #333;'>{cboe_text}</pre>
        </div>
        """
    
    # =================================================================
    # CATEGORIZE RESULTS INTO ACTIONABLE SECTIONS
    # PRSI is PRIMARY signal
    # Strong Buy = PRSI bullish + Price > PSAR (just crossed, fresh)
    # Early Buy = PRSI bullish + Price < PSAR (speculative, not confirmed)
    # =================================================================
    
    strong_buys = []  # PRSI bullish + Price > PSAR (confirmed, fresh signals best)
    buys = []         # PRSI bullish + Price > PSAR (established trends)
    early_buys = []   # PRSI bullish + Price < PSAR (speculative)
    dividend_buys = []
    
    # Additional categories for portfolio/friends mode only
    holds = []
    sells = []
    
    # Market cap threshold for dividends (1 billion = 1e9)
    MIN_DIVIDEND_MARKET_CAP = 1_000_000_000
    
    # ADX threshold for Strong Buys - set to 0 to disable, 15-25 typical
    # ROLLBACK: Change this to 0 to disable ADX filtering for Strong Buys
    STRONG_BUY_ADX_THRESHOLD = 15
    
    is_portfolio_mode = mode in ['Portfolio', 'Friends']
    
    for r in results:
        # Helper to check dividend eligibility
        def is_dividend_eligible():
            return (hasattr(r, 'dividend_yield') and r.dividend_yield and r.dividend_yield >= div_threshold and
                    hasattr(r, 'market_cap') and r.market_cap and r.market_cap >= MIN_DIVIDEND_MARKET_CAP)
        
        # Helper to get ADX value
        def get_adx_value():
            return getattr(r, 'adx_value', 0) or 0
        
        # PRSI BULLISH = BUY SIDE
        if r.prsi_bullish:
            if r.psar_gap >= 0:
                # Price is ABOVE PSAR (confirmed uptrend)
                days_in_trend = getattr(r, 'psar_days_in_trend', 999)
                adx_val = get_adx_value()
                
                # STRONG BUY: Fresh signal (just crossed, <= 5 days) + meets ADX threshold
                if days_in_trend <= 5:
                    # Check ADX threshold (0 = disabled)
                    if STRONG_BUY_ADX_THRESHOLD == 0 or adx_val >= STRONG_BUY_ADX_THRESHOLD:
                        strong_buys.append(r)
                        if is_dividend_eligible():
                            dividend_buys.append(r)
                    else:
                        # ADX too low, goes to regular Buy instead
                        buys.append(r)
                        if is_dividend_eligible():
                            dividend_buys.append(r)
                # BUY: Established trend (> 5 days)
                else:
                    buys.append(r)
                    if is_dividend_eligible():
                        dividend_buys.append(r)
            else:
                # Price is BELOW PSAR (not yet confirmed)
                # EARLY BUY: PRSI says go but price hasn't crossed yet
                early_buys.append(r)
        
        # PRSI BEARISH = CAUTION SIDE
        else:
            if is_portfolio_mode:
                if r.psar_gap >= 0:
                    # Price still above PSAR but PRSI turned - HOLD (potential pullback)
                    holds.append(r)
                else:
                    # Price below PSAR + PRSI bearish - SELL
                    sells.append(r)
    
    # =================================================================
    # SORTING
    # =================================================================
    
    # Helper: count checkboxes (DMI + ADX + MACD)
    def checkbox_count(r):
        count = 0
        if getattr(r, 'dmi_bullish', False): count += 1
        if getattr(r, 'adx_strong', False): count += 1
        if getattr(r, 'macd_bullish', False): count += 1
        return count
    
    # Strong buys: fewest days first (freshest), then OBV green, then most checkboxes
    strong_buys.sort(key=lambda x: (
        getattr(x, 'psar_days_in_trend', 999),  # Fewer days = fresher = better
        0 if x.obv_bullish else 1,               # OBV green first
        -checkbox_count(x)                        # More checkboxes = better
    ))
    
    # Buys: same logic but these are older trends
    buys.sort(key=lambda x: (
        getattr(x, 'psar_days_in_trend', 999),
        0 if x.obv_bullish else 1,
        -checkbox_count(x)
    ))
    
    # Early buys: PRSI flip recency, then gap (closer to crossing), then Williams (oversold better)
    early_buys.sort(key=lambda x: (
        x.prsi_days_since_flip,                   # Fresher PRSI flip = better
        -x.psar_gap,                              # Less negative gap = closer to crossing
        getattr(x, 'williams_r', -50)             # More negative Williams = more oversold = better entry
    ))
    
    # Dividend buys: sort same as strong/buy (freshness, OBV, checkboxes)
    # We'll mark them as Strong or Buy when displaying
    dividend_buys.sort(key=lambda x: (
        getattr(x, 'psar_days_in_trend', 999),  # Fewer days = fresher = better
        0 if x.obv_bullish else 1,               # OBV green first
        -checkbox_count(x)                        # More checkboxes = better
    ))
    
    # Holds: by PSAR gap (highest gap = most at risk of falling)
    holds.sort(key=lambda x: -x.psar_gap)
    
    # Sells: most negative gap first (deepest in downtrend)
    sells.sort(key=lambda x: x.psar_gap)
    
    # Limit lists to keep report readable
    strong_buys = strong_buys[:50]
    buys = buys[:100]
    early_buys = early_buys[:50]
    dividend_buys = dividend_buys[:30]
    holds = holds[:50]
    sells = sells[:30]
    
    # =================================================================
    # BUILD SUMMARY BOX
    # =================================================================
    if mode in ['Portfolio', 'Friends']:
        html += f"""
        <div class='action-box'>
            <strong>📊 PORTFOLIO SUMMARY:</strong><br>
            🟢🟢 <strong>{len(strong_buys)} Strong Buys</strong> (Fresh signals ≤5 days) |
            🟢 <strong>{len(buys)} Buys</strong> (Established trends) |
            ⏸️ {len(holds)} Holds |
            🔴 {len(sells)} Sells |
            ⚡ <strong>{len(early_buys)} Early Buys</strong> (Speculative)
        </div>
        """
    else:
        html += f"""
        <div class='action-box'>
            <strong>📊 ACTIONABLE SIGNALS:</strong><br>
            🟢🟢 <strong>{len(strong_buys)} Strong Buys</strong> (Fresh signals ≤5 days) |
            ⚡ <strong>{len(early_buys)} Early Buys</strong> (Speculative, price < PSAR)<br>
            💰 <strong>{len(dividend_buys)} Dividend Buys</strong> (Yield ≥{div_threshold}%)
        </div>
        """
    
    # V2 explanation note
    if use_v2:
        html += """
        <div class='v2-note'>
            <strong>V2 Signal Logic:</strong> PRSI (PSAR on RSI) is primary signal - it leads price by 1-3 days | 
            Trend Score = MACD + ADX + MA alignment | OBV 🟢 = accumulation confirms
        </div>
        """
    
    # =================================================================
    # BUILD TABLES FOR EACH SECTION
    # =================================================================
    
    # STRONG BUY - Fresh confirmed signals (≤5 days since price crossed PSAR)
    if strong_buys:
        # Apply limit for market mode
        display_strong = strong_buys if is_portfolio_mode else strong_buys[:strong_buy_limit]
        html += f"""
        <div class='section-strongbuy'>🟢🟢 STRONG BUY - Fresh Signals ({len(display_strong)} stocks{f' of {len(strong_buys)}' if len(strong_buys) > len(display_strong) else ''})</div>
        <p style='color:#1e8449; font-size:11px; margin:5px 0;'>PRSI bullish + Price just crossed above PSAR (≤5 days). Sorted by freshness, then OBV, then checkboxes.</p>
        """
        html += build_results_table(display_strong, 'STRONG_BUY', use_v2, is_portfolio_mode)
    
    # BUY - Established trends (Portfolio/Friends mode only)
    if buys and is_portfolio_mode:
        html += f"""
        <div class='section-buy'>🟢 BUY - Established Trends ({len(buys)} stocks)</div>
        <p style='color:#27ae60; font-size:11px; margin:5px 0;'>PRSI bullish + Price above PSAR (>5 days). Trend is confirmed but not as fresh.</p>
        """
        html += build_results_table(buys, 'BUY', use_v2, is_portfolio_mode)
    
    # === PORTFOLIO/FRIENDS MODE ONLY SECTIONS ===
    if mode in ['Portfolio', 'Friends']:
        # HOLD - PRSI bearish but price still above PSAR
        if holds:
            html += f"""
            <div class='section-hold'>⏸️ HOLD - Pullback Expected ({len(holds)} stocks)</div>
            <p style='color:#f39c12; font-size:11px; margin:5px 0;'>PRSI turned bearish but price still above PSAR. May pull back - don't add.</p>
            """
            html += build_results_table(holds, 'HOLD', use_v2, is_portfolio_mode)
        
        # SELL - PRSI bearish and price below PSAR
        if sells:
            html += f"""
            <div class='section-sell'>🔴 SELL - Downtrend ({len(sells)} stocks)</div>
            <p style='color:#c0392b; font-size:11px; margin:5px 0;'>PRSI bearish + Price below PSAR. Consider reducing position.</p>
            """
            html += build_results_table(sells, 'SELL', use_v2, is_portfolio_mode)
        
        # EARLY BUY - Speculative (last for portfolio since these are riskier)
        if early_buys:
            html += f"""
            <div class='section-earlybuy'>⚡ EARLY BUY - Speculative ({len(early_buys)} stocks)</div>
            <p style='color:#2980b9; font-size:11px; margin:5px 0;'>PRSI bullish but price still below PSAR. Higher risk - waiting for confirmation.</p>
            """
            html += build_results_table(early_buys, 'EARLY_BUY', use_v2, is_portfolio_mode)
        
        # COVERED CALL CANDIDATES - High ATR stocks (Portfolio/Friends only)
        if analyze_covered_call and build_covered_call_section:
            # Find high ATR stocks (>5%) that are in buy zones
            high_atr_stocks = []
            all_buy_zone = strong_buys + buys + holds  # Include holds since you own them
            
            for r in all_buy_zone:
                atr_pct = getattr(r, 'atr_percent', 0)
                if atr_pct >= 5.0:  # High volatility threshold
                    # Determine signal type
                    days_in_trend = getattr(r, 'psar_days_in_trend', 999)
                    if r.prsi_bullish and r.psar_gap >= 0:
                        if days_in_trend <= 5:
                            signal_type = "Strong Buy"
                        else:
                            signal_type = "Buy"
                    else:
                        signal_type = "Hold"
                    
                    high_atr_stocks.append((r, signal_type))
            
            if high_atr_stocks:
                print(f"\n  📞 Analyzing {len(high_atr_stocks)} high-ATR stocks for covered calls...")
                cc_suggestions = []
                
                for r, signal_type in high_atr_stocks:
                    suggestion = analyze_covered_call(
                        ticker=r.ticker,
                        current_price=r.price,
                        atr_percent=r.atr_percent,
                        williams_r=getattr(r, 'williams_r', -50),
                        adx_value=getattr(r, 'adx_value', 20),
                        signal_type=signal_type,
                        fetch_options=True
                    )
                    if suggestion:
                        cc_suggestions.append(suggestion)
                
                if cc_suggestions:
                    # Sort by ATR% descending (highest volatility = best premium potential)
                    cc_suggestions.sort(key=lambda x: -x.atr_percent)
                    html += build_covered_call_section(cc_suggestions)
    
    else:
        # MARKET MODE - Early Buy before Dividends
        if early_buys:
            display_early = early_buys[:early_buy_limit]
            html += f"""
            <div class='section-earlybuy'>⚡ EARLY BUY - Speculative ({len(display_early)} stocks{f' of {len(early_buys)}' if len(early_buys) > len(display_early) else ''})</div>
            <p style='color:#2980b9; font-size:11px; margin:5px 0;'>PRSI bullish but price still below PSAR. Sorted by PRSI flip recency, then gap (closer to crossing), then Williams %R.</p>
            """
            html += build_results_table(display_early, 'EARLY_BUY', use_v2, False)
        
        # DIVIDEND BUYS - Market mode only
        if dividend_buys:
            display_div = dividend_buys[:dividend_limit]
            html += f"""
            <div class='section-dividend' style='background-color:#27ae60; color:white; padding:12px; margin:20px 0 10px 0; font-size:14px; font-weight:bold;'>💰 DIVIDEND BUYS - Yield ≥{div_threshold}% ({len(display_div)} stocks{f' of {len(dividend_buys)}' if len(dividend_buys) > len(display_div) else ''})</div>
            <p style='color:#27ae60; font-size:11px; margin:5px 0;'>Dividend stocks (≥{div_threshold}% yield) in Strong Buy/Buy zones. Sorted by signal freshness.</p>
            """
            html += build_results_table(display_div, 'DIVIDEND', use_v2, False)
    
    # Summary legend
    if mode in ['Portfolio', 'Friends']:
        html += """
    <div class='summary-box'>
        <strong>Legend:</strong><br>
        ⭐ = IBD Stock (click for research) | 
        <strong>Days:</strong> Days since price crossed PSAR (Strong/Buy) or PRSI flipped (Early Buy)<br>
        PRSI: ↗️ Bullish ↘️ Bearish | OBV: 🟢 Accumulation 🔴 Distribution<br>
        <strong>Checkboxes:</strong> DMI (bulls control) | ADX (strong trend) | MACD (momentum up)<br>
        <strong>ATR%:</strong> <span style='color:#27ae60'>Green &lt;3%</span> | <span style='color:#f39c12'>Yellow 3-5%</span> | <span style='color:#e74c3c'>Red &gt;5% 📞 = Consider covered calls</span>
    </div>
    """
    else:
        html += """
    <div class='summary-box'>
        <strong>Legend:</strong><br>
        ⭐ = IBD Stock (click for research) | 
        <strong>Days:</strong> Days since price crossed PSAR (Strong/Buy) or PRSI flipped (Early Buy)<br>
        PRSI: ↗️ Bullish ↘️ Bearish | OBV: 🟢 Accumulation 🔴 Distribution<br>
        <strong>Checkboxes:</strong> DMI (bulls control) | ADX (strong trend) | MACD (momentum up)
    </div>
    """
    
    html += "</body></html>"
    return html


def send_email(
    results: List[ScanResult],
    mode: str,
    use_v2: bool = True,
    cboe_text: str = "",
    total_scanned: int = 0,
    additional_email: Optional[str] = None,
    div_threshold: float = 2.0,
    custom_title: Optional[str] = None
) -> bool:
    """Send email report."""
    sender_email = os.getenv("GMAIL_EMAIL")
    sender_password = os.getenv("GMAIL_PASSWORD")
    recipient_email = os.getenv("RECIPIENT_EMAIL")
    
    if not all([sender_email, sender_password, recipient_email]):
        print("✗ Missing email credentials (GMAIL_EMAIL, GMAIL_PASSWORD, RECIPIENT_EMAIL)")
        return False
    
    # Count actionable signals using V2 logic
    early_count = len([r for r in results if r.prsi_bullish and r.psar_gap < 0])
    strong_count = len([r for r in results if r.prsi_bullish and r.psar_gap >= 0 and getattr(r, 'psar_days_in_trend', 999) <= 5])
    buy_count = len([r for r in results if r.prsi_bullish and r.psar_gap >= 0 and getattr(r, 'psar_days_in_trend', 999) > 5])
    dividend_count = len([r for r in results if r.prsi_bullish and r.psar_gap >= 0 and r.dividend_yield and r.dividend_yield >= div_threshold])
    
    version = "V2" if use_v2 else "V1"
    if custom_title:
        subject = custom_title
    else:
        subject = f"📈 {version} {mode}: {early_count}⚡ {strong_count}🟢🟢 {buy_count}🟢 {dividend_count}💰 - {datetime.now().strftime('%m/%d %H:%M')}"
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender_email
    
    recipients = [recipient_email]
    if additional_email:
        recipients.append(additional_email)
    msg['To'] = ", ".join(recipients)
    
    html_body = build_email_body(results, mode, use_v2, cboe_text, total_scanned, div_threshold)
    msg.attach(MIMEText(html_body, 'html'))
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
        print(f"\n✓ Email sent to: {', '.join(recipients)}")
        print(f"  ⚡ Early: {early_count} | 🟢🟢 Strong: {strong_count} | 🟢 Buy: {buy_count} | 💰 Dividend: {dividend_count}")
        return True
    except Exception as e:
        print(f"\n✗ Failed to send email: {e}")
        return False


def send_shorts_email(
    html_body: str,
    mode: str,
    prime_count: int = 0,
    candidate_count: int = 0,
    additional_email: Optional[str] = None,
    custom_title: Optional[str] = None
) -> bool:
    """Send shorts report email."""
    sender_email = os.getenv("GMAIL_EMAIL")
    sender_password = os.getenv("GMAIL_PASSWORD")
    recipient_email = os.getenv("RECIPIENT_EMAIL")
    
    if not all([sender_email, sender_password, recipient_email]):
        print("✗ Missing email credentials (GMAIL_EMAIL, GMAIL_PASSWORD, RECIPIENT_EMAIL)")
        return False
    
    if custom_title:
        subject = custom_title
    else:
        subject = f"🐻 V2 {mode}: {prime_count}🔴 Short Candidates - {datetime.now().strftime('%m/%d %H:%M')}"
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender_email
    
    recipients = [recipient_email]
    if additional_email:
        recipients.append(additional_email)
    msg['To'] = ", ".join(recipients)
    
    msg.attach(MIMEText(html_body, 'html'))
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
        print(f"\n✓ Email sent to: {', '.join(recipients)}")
        print(f"  🔴 Short Candidates: {prime_count}")
        return True
    except Exception as e:
        print(f"\n✗ Failed to send email: {e}")
        return False


# =============================================================================
# CLI
# =============================================================================

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Market PSAR Scanner V2 - PRSI-Primary Signal Logic",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                     # Full market scan + email
  python main.py -mystocks           # Your portfolio + email
  python main.py -friends            # Friends watchlist + email
  python main.py -shorts             # Short candidates + email
  python main.py --no-email          # Scan without sending email
  python main.py --classic           # Use old V1 logic

V2 Key Changes:
  - PRSI (PSAR on RSI) is the primary signal
  - Momentum 5-7 = ideal entry, 9-10 = hold only
  - Gap > 5% = blocked (too risky)
  - OBV confirms/warns signals
        """
    )
    
    # Scan mode
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('-mystocks', action='store_true',
                           help='Scan your portfolio (mystocks.txt)')
    mode_group.add_argument('-friends', action='store_true',
                           help="Scan friend's watchlist (friends.txt)")
    mode_group.add_argument('-shorts', action='store_true',
                           help='Analyze shorts.txt watchlist for short opportunities')
    mode_group.add_argument('-shortscan', action='store_true',
                           help='Market-wide scan for best short candidates')
    
    # Logic version
    parser.add_argument('--classic', action='store_true',
                       help='Use V1 classic logic (Price PSAR primary)')
    
    # Filters
    parser.add_argument('--eps', type=float, default=None,
                       help='Minimum EPS growth %%')
    parser.add_argument('--rev', type=float, default=None,
                       help='Minimum revenue growth %%')
    parser.add_argument('--mc', type=float, default=None,
                       help='Minimum market cap in millions (default 5000 = $5B)')
    parser.add_argument('--adr', action='store_true',
                       help='Include ADR stocks')
    
    # Email
    parser.add_argument('--no-email', action='store_true',
                       help='Skip sending email report')
    parser.add_argument('--email-to', type=str, default=None,
                       help='Additional email recipient')
    
    # Output
    parser.add_argument('--html', type=str, default=None,
                       help='Save HTML report to file')
    parser.add_argument('--quiet', action='store_true',
                       help='Minimal console output')
    
    # Advanced
    parser.add_argument('--workers', type=int, default=10,
                       help='Parallel workers for data fetching')
    parser.add_argument('--no-ibd', action='store_true',
                       help='Skip IBD list scanning')
    parser.add_argument('--tickers', type=str, default=None,
                       help='Comma-separated list of specific tickers')
    parser.add_argument('--div', type=float, default=2.0,
                       help='Minimum dividend yield %% for dividend section (default: 2.0)')
    parser.add_argument('-t', '--title', type=str, default=None,
                       help='Custom email subject title')
    
    return parser.parse_args()


def create_progress_callback(quiet: bool = False):
    """Create a progress callback function."""
    if quiet:
        return None
    
    def progress(current: int, total: int, ticker: str, status: str):
        pct = current / total * 100
        bar_width = 30
        filled = int(bar_width * current / total)
        bar = '█' * filled + '░' * (bar_width - filled)
        print(f"\r[{bar}] {pct:5.1f}% ({current}/{total}) {ticker:<8}", end='', flush=True)
    
    return progress


def main():
    """Main entry point."""
    args = parse_args()
    
    use_v2 = not args.classic
    progress = create_progress_callback(args.quiet)
    
    # Determine mode
    if args.mystocks:
        mode = "Portfolio"
    elif args.friends:
        mode = "Friends"
    elif args.shorts:
        mode = "Shorts"
    elif args.shortscan:
        mode = "ShortScan"
    else:
        mode = "Market"
    
    # Print header
    if not args.quiet:
        version = "V1 Classic" if args.classic else "V2 PRSI-Primary"
        print(f"\n{'='*60}")
        print(f"📊 Market Scanner {version}")
        print(f"   Mode: {mode}")
        print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*60}\n")
    
    # Get CBOE data
    cboe_text = ""
    try:
        cboe_text = get_cboe_ratios_and_analyze()
    except Exception as e:
        if not args.quiet:
            print(f"Warning: Could not get CBOE data: {e}")
    
    # Common kwargs
    kwargs = {
        'use_v2': use_v2,
        'include_adr': args.adr,
        'eps_filter': args.eps,
        'rev_filter': args.rev,
        'max_workers': args.workers,
        'progress_callback': progress
    }
    
    if args.mc:
        kwargs['min_market_cap'] = args.mc
    
    # Custom tickers
    custom_tickers = None
    if args.tickers:
        custom_tickers = [t.strip().upper() for t in args.tickers.split(',')]
    
    # Create scanner
    if args.mystocks:
        scanner = PortfolioScanner(**kwargs)
    elif args.friends:
        scanner = FriendsScanner(**kwargs)
    elif args.shorts:
        scanner = SmartShortScanner(scan_market=False, **kwargs)
    elif args.shortscan:
        scanner = SmartShortScanner(scan_market=True, **kwargs)
    else:
        scanner = SmartBuyScanner(
            scan_ibd=not args.no_ibd,
            custom_tickers=custom_tickers,
            **kwargs
        )
    
    # Run scan
    try:
        summary = scanner.scan()
        
        # Collect all results
        results = []
        ticker_list = scanner.get_tickers()
        
        for ticker, source in ticker_list:
            result = scanner.scan_ticker(ticker, source)
            if result:
                results.append(result)
        
        if not args.quiet:
            print("\n")  # Clear progress bar
        
        # Special handling for shorts mode
        if mode in ['Shorts', 'ShortScan'] and analyze_short_candidate:
            # Analyze results as short candidates
            from analysis.shorts import ShortCandidate
            
            if not args.quiet:
                print(f"\n  🐻 Analyzing {len(results)} stocks for short opportunities...")
            
            # First pass: Score all stocks WITHOUT fetching options (fast)
            all_candidates = []
            
            for r in results:
                candidate = analyze_short_candidate(
                    ticker=r.ticker,
                    current_price=r.price,
                    psar_gap=r.psar_gap,
                    psar_days_bearish=getattr(r, 'psar_days_in_trend', 0),
                    prsi_bearish=not r.prsi_bullish,
                    prsi_days_since_flip=r.prsi_days_since_flip,
                    obv_bearish=not r.obv_bullish if r.obv_bullish is not None else False,
                    dmi_bearish=not getattr(r, 'dmi_bullish', True),
                    adx_value=getattr(r, 'adx_value', 20),
                    williams_r=getattr(r, 'williams_r', -50),
                    atr_percent=r.atr_percent,
                    fetch_options=False
                )
                all_candidates.append(candidate)
            
            # Different behavior for watchlist vs market scan
            is_watchlist_mode = (mode == 'Shorts')
            
            if is_watchlist_mode:
                # WATCHLIST MODE (-shorts): Show ALL stocks with their category
                # Categorize all candidates
                prime_shorts = [c for c in all_candidates if c.category == 'PRIME_SHORT']
                short_candidates = [c for c in all_candidates if c.category == 'SHORT_CANDIDATE']
                not_ready = [c for c in all_candidates if c.category == 'NOT_READY']
                avoid = [c for c in all_candidates if c.category == 'AVOID']
                
                # Sort each by score
                prime_shorts.sort(key=lambda x: -x.short_score)
                short_candidates.sort(key=lambda x: -x.short_score)
                not_ready.sort(key=lambda x: -x.short_score)
                avoid.sort(key=lambda x: -x.short_score)
                
                # Fetch options only for prime and candidates (top shorts)
                from analysis.shorts import get_put_spread_recommendation
                import time
                
                top_for_options = (prime_shorts + short_candidates)[:20]
                
                if top_for_options and not args.quiet:
                    print(f"\n  📊 Fetching put spreads for {len(top_for_options)} actionable candidates...")
                
                for i, candidate in enumerate(top_for_options):
                    if i > 0 and i % 3 == 0:
                        time.sleep(1.0)
                    try:
                        put_data = get_put_spread_recommendation(
                            candidate.ticker, 
                            candidate.current_price, 
                            candidate.atr_percent
                        )
                        if put_data and put_data.get('spread_cost', 0) > 0:
                            candidate.buy_put_strike = put_data['buy_strike']
                            candidate.sell_put_strike = put_data['sell_strike']
                            candidate.put_expiration = put_data['expiration']
                            candidate.put_days_to_expiry = put_data['days_to_expiry']
                            candidate.spread_cost = put_data['spread_cost']
                            candidate.max_profit = put_data['max_profit']
                    except Exception:
                        pass
                
                # Print console summary
                if not args.quiet:
                    print(f"\n{'='*60}")
                    print(f"SHORT WATCHLIST ANALYSIS: {len(all_candidates)} stocks")
                    print(f"{'='*60}")
                    print(f"  🔴🔴 Prime Shorts: {len(prime_shorts)}")
                    print(f"  🔴 Short Candidates: {len(short_candidates)}")
                    print(f"  ⏳ Not Ready: {len(not_ready)}")
                    print(f"  ❌ Avoid: {len(avoid)}")
                
                # Build watchlist HTML (shows all categories)
                from analysis.shorts import build_shorts_watchlist_html
                html_body = build_shorts_watchlist_html(
                    prime_shorts=prime_shorts,
                    short_candidates=short_candidates,
                    not_ready=not_ready,
                    avoid=avoid,
                    mode=mode,
                    total_scanned=len(results)
                )
                
                # Send email
                if not args.no_email:
                    send_shorts_email(
                        html_body=html_body,
                        mode=mode,
                        prime_count=len(prime_shorts) + len(short_candidates),
                        candidate_count=0,
                        additional_email=args.email_to,
                        custom_title=args.title
                    )
            
            else:
                # MARKET SCAN MODE (-shortscan): Filter to top candidates only
                # Only keep viable shorts
                viable_candidates = [c for c in all_candidates if c.category in ['PRIME_SHORT', 'SHORT_CANDIDATE']]
                viable_candidates.sort(key=lambda x: -x.short_score)
                top_for_options = viable_candidates[:25]
                
                # Second pass: Fetch options with delay to avoid rate limiting
                from analysis.shorts import get_put_spread_recommendation
                import time
                
                short_candidates = []
                skipped = []
                
                if top_for_options and not args.quiet:
                    print(f"\n  📊 Fetching put spreads for top {len(top_for_options)} candidates...")
                
                for i, candidate in enumerate(top_for_options):
                    # Add delay every 3 requests to avoid rate limiting
                    if i > 0 and i % 3 == 0:
                        time.sleep(1.0)
                    
                    try:
                        put_data = get_put_spread_recommendation(
                            candidate.ticker, 
                            candidate.current_price, 
                            candidate.atr_percent
                        )
                        if put_data and put_data.get('spread_cost', 0) > 0:
                            candidate.buy_put_strike = put_data['buy_strike']
                            candidate.sell_put_strike = put_data['sell_strike']
                            candidate.put_expiration = put_data['expiration']
                            candidate.put_days_to_expiry = put_data['days_to_expiry']
                            candidate.spread_cost = put_data['spread_cost']
                            candidate.max_profit = put_data['max_profit']
                            short_candidates.append(candidate)
                        else:
                            skipped.append(candidate)
                    except Exception:
                        skipped.append(candidate)
                    
                    # Stop once we have 25 candidates with options
                    if len(short_candidates) >= 25:
                        break
                
                # Print console summary
                if not args.quiet:
                    print(f"\n{'='*60}")
                    print(f"SHORT SCAN COMPLETE: {len(results)} stocks analyzed")
                    print(f"{'='*60}")
                    print(f"  🔴 Short Candidates (with options): {len(short_candidates)}")
                    print(f"  ⏳ Skipped (no options/rate limited): {len(skipped)}")
                
                # Build shorts HTML - single list only
                html_body = build_shorts_report_html(
                    short_candidates=short_candidates,
                    mode=mode,
                    total_scanned=len(results)
                )
                
                # Send email
                if not args.no_email:
                    send_shorts_email(
                        html_body=html_body,
                        mode=mode,
                        prime_count=len(short_candidates),
                        candidate_count=0,
                        additional_email=args.email_to,
                        custom_title=args.title
                    )
            
            # Save HTML if requested (for both modes)
            if args.html:
                with open(args.html, 'w') as f:
                    f.write(html_body)
                print(f"✓ HTML report saved to: {args.html}")
        
        else:
            # Standard buy-side processing
            # Print console summary
            if not args.quiet:
                print(f"\n{'='*60}")
                print(f"SCAN COMPLETE: {len(results)} stocks")
                print(f"{'='*60}")
                
                by_zone = {}
                for r in results:
                    by_zone[r.zone] = by_zone.get(r.zone, 0) + 1
                
                for zone in ['EARLY_BUY', 'STRONG_BUY', 'BUY', 'HOLD', 'WARNING', 'SELL', 'OVERSOLD_WATCH']:
                    if zone in by_zone:
                        print(f"  {get_zone_emoji(zone)} {zone}: {by_zone[zone]}")
            
            # Send email (unless --no-email)
            if not args.no_email:
                send_email(
                    results=results,
                    mode=mode,
                    use_v2=use_v2,
                    cboe_text=cboe_text,
                    total_scanned=summary.total_scanned,
                    additional_email=args.email_to,
                    div_threshold=args.div,
                    custom_title=args.title
                )
            
            # Save HTML if requested
            if args.html:
                html = build_email_body(results, mode, use_v2, cboe_text, summary.total_scanned, args.div)
                with open(args.html, 'w') as f:
                    f.write(html)
                print(f"✓ HTML report saved to: {args.html}")
        
    except KeyboardInterrupt:
        print("\n\nScan interrupted.")
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

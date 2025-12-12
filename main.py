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
from typing import Optional, List, Dict, Any, Tuple

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


def calculate_sbi(days_in_trend: int, atr_percent: float, gap_slope: float, adx_value: float = 20, prsi_fast_bearish: bool = False, is_broken: bool = False) -> int:
    """
    Calculate Smart Buy Indicator (SBI) 0-10.
    
    Day 1: ATR only (no slope data yet)
    Day 2: 80% ATR + 20% Slope
    Day 3: 60% ATR + 40% Slope
    Days 4-5: 40% ATR + 40% Slope + 20% ADX
    Days 6+: 40% Slope + 30% ADX + 30% ATR
    
    PRSI(4) bearish applies -2 penalty for Days 3+ (momentum warning)
    is_broken = True means stock crashed through PSAR (not a buy!)
    
    Args:
        days_in_trend: Days since PSAR crossed
        atr_percent: ATR as % of price
        gap_slope: Change in PSAR gap since cross (positive = widening = good)
        adx_value: ADX trend strength (higher = stronger trend)
        prsi_fast_bearish: True if PRSI(4) is bearish (momentum warning)
        is_broken: True if stock recently broke DOWN through PSAR (sell signal, not buy)
    
    Returns:
        SBI score 0-10 (10 = best)
    """
    # If broken (crashed through PSAR), SBI = 0 - this is NOT a buy
    if is_broken:
        return 0
    
    # ATR score - day-specific thresholds
    if days_in_trend == 1:
        atr_score = 10 if atr_percent < 7 else 4
    elif days_in_trend == 2:
        atr_score = 10 if atr_percent < 6 else 4
    elif days_in_trend in [3, 4]:
        atr_score = 10 if atr_percent < 5 else 4
    elif days_in_trend == 5:
        if atr_percent < 4:
            atr_score = 10
        elif atr_percent < 5:
            atr_score = 8
        elif atr_percent < 6:
            atr_score = 6
        else:
            atr_score = 4
    else:
        # Days 6+ use gradual ATR scoring
        if atr_percent < 2:
            atr_score = 10
        elif atr_percent < 2.5:
            atr_score = 9
        elif atr_percent < 3:
            atr_score = 8
        elif atr_percent < 4:
            atr_score = 7
        elif atr_percent < 5:
            atr_score = 6
        else:
            atr_score = 4
    
    # Slope score: gap widening = good, narrowing = bad
    if gap_slope >= 2:
        slope_score = 10  # Strongly widening
    elif gap_slope >= 1:
        slope_score = 9   # Widening
    elif gap_slope >= 0.5:
        slope_score = 8   # Slightly widening
    elif gap_slope >= -0.5:
        slope_score = 7   # Stable
    elif gap_slope >= -1:
        slope_score = 5   # Slightly narrowing
    elif gap_slope >= -2:
        slope_score = 3   # Narrowing
    else:
        slope_score = 1   # Strongly narrowing (trend exhausting)
    
    # ADX score: higher ADX = stronger trend = better
    if adx_value >= 40:
        adx_score = 10  # Very strong trend
    elif adx_value >= 30:
        adx_score = 8   # Strong trend
    elif adx_value >= 25:
        adx_score = 6   # Moderate trend
    elif adx_value >= 20:
        adx_score = 4   # Weak trend
    else:
        adx_score = 2   # Choppy/no trend
    
    # Calculate SBI based on days in trend
    if days_in_trend == 1:
        # Day 1: ATR only (no slope data yet)
        sbi = atr_score
    elif days_in_trend == 2:
        # Day 2: 80% ATR + 20% Slope
        sbi = int(0.8 * atr_score + 0.2 * slope_score)
    elif days_in_trend == 3:
        # Day 3: 60% ATR + 40% Slope
        sbi = int(0.6 * atr_score + 0.4 * slope_score)
    elif days_in_trend in [4, 5]:
        # Days 4-5: 40% ATR + 40% Slope + 20% ADX
        sbi = int(0.4 * atr_score + 0.4 * slope_score + 0.2 * adx_score)
    else:
        # Days 6+: 40% Slope + 30% ADX + 30% ATR
        sbi = int(0.4 * slope_score + 0.3 * adx_score + 0.3 * atr_score)
    
    # Apply PRSI(4) penalty for Days 3+ (momentum warning)
    if prsi_fast_bearish and days_in_trend >= 3:
        sbi = sbi - 2
    
    return max(0, min(10, sbi))


def calculate_sse(
    psar_gap: float,
    gap_slope: float,
    days_in_trend: int,
    prsi_bullish: bool,
    prsi_fast_bullish: bool,
    obv_bearish: bool,
    williams_r: float = -50
) -> Tuple[int, str, List[str]]:
    """
    Calculate Smart Sell/Exit (SSE) indicator 0-10.
    
    Higher score = stronger sell signal.
    
    Args:
        psar_gap: Current PSAR gap % (negative = below PSAR)
        gap_slope: Change in gap (negative = narrowing)
        days_in_trend: Days in current trend
        prsi_bullish: True if PRSI(14) bullish
        prsi_fast_bullish: True if PRSI(4) bullish
        obv_bearish: True if OBV shows distribution
        williams_r: Williams %R value (-100 to 0)
    
    Returns:
        Tuple of (score, category, reasons)
        - score: 0-10 (10 = urgent sell)
        - category: HOLD, WATCH, TRIM, SELL, URGENT
        - reasons: List of contributing factors
    """
    score = 0
    reasons = []
    
    # Price below PSAR = breakdown
    if psar_gap < 0:
        score += 3
        reasons.append(f"Below PSAR ({psar_gap:.1f}%)")
    
    # PRSI(14) bearish = confirmed reversal
    if not prsi_bullish:
        score += 3
        reasons.append("PRSI(14) bearish")
    
    # PRSI(4) bearish but PRSI(14) still bullish = early warning
    elif not prsi_fast_bullish:
        score += 2
        reasons.append("PRSI(4) bearish (momentum warning)")
    
    # Gap slope negative = trend weakening
    if gap_slope < -2:
        score += 2
        reasons.append(f"Gap narrowing fast ({gap_slope:.1f}%)")
    elif gap_slope < -1:
        score += 1
        reasons.append(f"Gap narrowing ({gap_slope:.1f}%)")
    
    # OBV distribution = selling pressure
    if obv_bearish:
        score += 1
        reasons.append("OBV distribution")
    
    # Williams %R oversold after being overbought = reversal
    if williams_r < -80:
        score += 1
        reasons.append(f"Williams %R oversold ({williams_r:.0f})")
    
    # Cap at 10
    score = min(10, score)
    
    # Categorize
    if score <= 2:
        category = "HOLD"
    elif score <= 4:
        category = "WATCH"
    elif score <= 6:
        category = "TRIM"
    elif score <= 8:
        category = "SELL"
    else:
        category = "URGENT"
    
    return score, category, reasons


def get_sse_display(sse_score: int, category: str) -> str:
    """Get colored display for SSE score."""
    if category == "HOLD":
        return f"<span style='color:#27ae60; font-weight:bold;'>{sse_score}</span>"  # Green
    elif category == "WATCH":
        return f"<span style='color:#f39c12; font-weight:bold;'>{sse_score}</span>"  # Yellow
    elif category == "TRIM":
        return f"<span style='color:#e67e22; font-weight:bold;'>{sse_score}</span>"  # Orange
    elif category == "SELL":
        return f"<span style='color:#e74c3c; font-weight:bold;'>{sse_score}</span>"  # Red
    else:  # URGENT
        return f"<span style='color:#c0392b; font-weight:bold;'>⛔{sse_score}</span>"  # Dark red with icon


def get_sbi_display(sbi: int) -> str:
    """Get colored SBI display."""
    if sbi >= 9:
        return f"<span style='color:#1e8449; font-weight:bold;'>{sbi}</span>"
    elif sbi >= 8:
        return f"<span style='color:#27ae60; font-weight:bold;'>{sbi}</span>"
    elif sbi >= 6:
        return f"<span style='color:#f39c12;'>{sbi}</span>"
    elif sbi >= 4:
        return f"<span style='color:#e67e22;'>{sbi}</span>"
    else:
        return f"<span style='color:#c0392b;'>{sbi}</span>"


def is_overheated(days_in_trend: int, atr_percent: float) -> bool:
    """
    Check if a fresh signal is overheated (high ATR relative to day).
    
    Day-specific thresholds:
    - Day 1: >= 7% is overheated
    - Day 2: >= 6% is overheated
    - Day 3-5: >= 5% is overheated (original threshold)
    """
    if days_in_trend == 1:
        return atr_percent >= 7.0
    elif days_in_trend == 2:
        return atr_percent >= 6.0
    elif days_in_trend <= 5:
        return atr_percent >= 5.0
    return False  # Days 6+ not considered overheated


def get_prsi_display(prsi_bullish: bool, momentum_warning: bool = False) -> str:
    """Get PRSI trend display with momentum warning."""
    if prsi_bullish:
        if momentum_warning:
            # PRSI(14) bullish but PRSI(4) bearish = momentum slowing
            return "<span style='color:#e67e22;'>↗️⚡</span>"
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
        'CUSTOM': 'custom',
    }.get(zone, 'hold')
    
    # ATR column only for portfolio/friends mode (not dividend or early buy) OR custom tickers
    show_atr = (is_portfolio_mode and zone not in ['DIVIDEND', 'EARLY_BUY']) or zone == 'CUSTOM'
    
    # Different columns for Early Buy vs others
    if zone == 'EARLY_BUY':
        # Early Buy: show PRSI days and Williams for sorting visibility
        header = """
            <th>Ticker</th>
            <th>Price</th>
            <th>PSAR%</th>
            <th>Days</th>
            <th>SBI</th>
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
            <th>SBI</th>
            <th>Signal</th>
            <th>PRSI</th>
            <th>OBV</th>
            <th>DMI</th>
            <th>ADX</th>
            <th>MACD</th>
            <th>Yield</th>
        """
        days_col = 'psar'
    elif zone == 'CUSTOM':
        # Custom tickers: show Zone column to indicate signal status
        header = """
            <th>Ticker</th>
            <th>Price</th>
            <th>Zone</th>
            <th>PSAR%</th>
            <th>Days</th>
            <th>SBI</th>
            <th>PRSI</th>
            <th>OBV</th>
            <th>DMI</th>
            <th>ADX</th>
            <th>MACD</th>
            <th>ATR%</th>
        """
        days_col = 'psar'
    elif show_atr:
        # Portfolio mode: add ATR column
        header = """
            <th>Ticker</th>
            <th>Price</th>
            <th>PSAR%</th>
            <th>Days</th>
            <th>SBI</th>
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
            <th>SBI</th>
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
        
        # PSAR gap color based on actual gap value
        # For BULLISH (positive gap): higher = more cushion = better
        # Green: >= 3% (good cushion), Yellow: 0-3% (close to PSAR), Blue/Red: negative (bearish)
        if r.psar_gap < 0:
            gap_color = '#3498db'  # Blue - below PSAR (bearish/early buy)
        elif r.psar_gap >= 3:
            gap_color = '#27ae60'  # Green - good cushion above PSAR
        else:
            gap_color = '#f39c12'  # Yellow - close to PSAR, could cross
        
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
        
        # SBI (Smart Buy Indicator) calculation - use atr_volatility (ATR/price %)
        days_in_trend_val = getattr(r, 'psar_days_in_trend', 0)
        atr_volatility = getattr(r, 'atr_volatility', 0)  # True volatility (always positive)
        gap_slope = getattr(r, 'psar_gap_slope', 0)
        adx_val = getattr(r, 'adx_value', 20)
        prsi_fast_bearish = not getattr(r, 'prsi_fast_bullish', True)
        is_broken = getattr(r, 'is_broken', False)
        sbi = calculate_sbi(days_in_trend_val, atr_volatility, gap_slope, adx_val, prsi_fast_bearish, is_broken)
        sbi_display = get_sbi_display(sbi)
        
        # ATR color coding and covered call suggestion
        # Green: ATR < 3% (low volatility)
        # Yellow: ATR 3-5% (moderate)
        # Red: ATR > 5% + ADX < 25 + Days > 5 (high volatility but choppy, not fresh breakout)
        if atr_volatility >= 5:
            atr_color = '#e74c3c'  # Red - high volatility
            # Only show CC link if ADX < 25 AND Days > 5 (not fresh breakout)
            if adx_val < 25 and days_in_trend_val > 5:
                atr_display = f"{atr_volatility:.1f}% <a href='#cc-{r.ticker}' style='text-decoration:none;'>📞</a>"
            else:
                atr_display = f"{atr_volatility:.1f}%"  # High ATR but trending or fresh, no CC suggestion
        elif atr_volatility >= 3:
            atr_color = '#f39c12'  # Yellow/orange - moderate
            atr_display = f"{atr_volatility:.1f}%"
        else:
            atr_color = '#27ae60'  # Green - low volatility
            atr_display = f"{atr_volatility:.1f}%"
        
        if zone == 'EARLY_BUY':
            # Show Williams %R for early buys
            williams = getattr(r, 'williams_r', -50)
            williams_display = f"{williams:.0f}"
            html += f"""
        <tr>
            <td><strong>{ticker_display}</strong></td>
            <td>${r.price:.2f}</td>
            <td style='color:{gap_color}; font-weight:bold;'>{r.psar_gap:+.1f}%</td>
            <td>{days_display}</td>
            <td>{sbi_display}</td>
            <td>{get_prsi_display(r.prsi_bullish, getattr(r, "prsi_momentum_warning", False))}</td>
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
            <td style='color:{gap_color}; font-weight:bold;'>{r.psar_gap:+.1f}%</td>
            <td>{days_display}</td>
            <td>{sbi_display}</td>
            <td>{signal_display}</td>
            <td>{get_prsi_display(r.prsi_bullish, getattr(r, "prsi_momentum_warning", False))}</td>
            <td>{get_obv_display(r.obv_bullish)}</td>
            <td style='color:{dmi_color};'>{dmi_check}</td>
            <td style='color:{adx_color};'>{adx_check}</td>
            <td style='color:{macd_color};'>{macd_check}</td>
            <td>{yield_display}</td>
        </tr>
            """
        elif zone == 'CUSTOM':
            # Show Zone column with actual zone status
            zone_emoji = get_zone_emoji(r.zone)
            actual_zone = r.zone.replace('_', ' ').title()
            html += f"""
        <tr>
            <td><strong>{ticker_display}</strong></td>
            <td>${r.price:.2f}</td>
            <td style='color:{zone_color}; font-weight:bold;'>{zone_emoji} {actual_zone}</td>
            <td style='color:{gap_color}; font-weight:bold;'>{r.psar_gap:+.1f}%</td>
            <td>{days_display}</td>
            <td>{sbi_display}</td>
            <td>{get_prsi_display(r.prsi_bullish, getattr(r, "prsi_momentum_warning", False))}</td>
            <td>{get_obv_display(r.obv_bullish)}</td>
            <td style='color:{dmi_color};'>{dmi_check}</td>
            <td style='color:{adx_color};'>{adx_check}</td>
            <td style='color:{macd_color};'>{macd_check}</td>
            <td style='color:{atr_color}; font-weight:bold;'>{atr_display}</td>
        </tr>
            """
        elif show_atr:
            # Portfolio mode with ATR column
            html += f"""
        <tr>
            <td><strong>{ticker_display}</strong></td>
            <td>${r.price:.2f}</td>
            <td style='color:{gap_color}; font-weight:bold;'>{r.psar_gap:+.1f}%</td>
            <td>{days_display}</td>
            <td>{sbi_display}</td>
            <td>{get_prsi_display(r.prsi_bullish, getattr(r, "prsi_momentum_warning", False))}</td>
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
            <td style='color:{gap_color}; font-weight:bold;'>{r.psar_gap:+.1f}%</td>
            <td>{days_display}</td>
            <td>{sbi_display}</td>
            <td>{get_prsi_display(r.prsi_bullish, getattr(r, "prsi_momentum_warning", False))}</td>
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
    dividend_limit: int = 30,
    scan_params: dict = None,
    custom_tickers: List[str] = None
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
            .section-custom { background-color: #3498db; color: white; padding: 12px; margin: 20px 0 10px 0; font-size: 14px; font-weight: bold; }
            
            .th-earlybuy { background-color: #2980b9; color: white; }
            .th-strongbuy { background-color: #1e8449; color: white; }
            .th-buy { background-color: #27ae60; color: white; }
            .th-hold { background-color: #f39c12; color: white; }
            .th-oversold { background-color: #8e44ad; color: white; }
            .th-warning { background-color: #e67e22; color: white; }
            .th-sell { background-color: #c0392b; color: white; }
            .th-dividend { background-color: #27ae60; color: white; }
            .th-custom { background-color: #3498db; color: white; }
            
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
    
    # Display scan parameters
    if scan_params:
        params_parts = []
        if scan_params.get('market_cap'):
            mc = scan_params['market_cap']
            if mc >= 1000:
                params_parts.append(f"Market Cap ≥ ${mc/1000:.0f}B")
            else:
                params_parts.append(f"Market Cap ≥ ${mc:.0f}M")
        if scan_params.get('eps_growth'):
            params_parts.append(f"Fwd EPS Growth ≥ {scan_params['eps_growth']}%")
        if scan_params.get('rev_growth'):
            params_parts.append(f"Revenue Growth ≥ {scan_params['rev_growth']}%")
        if scan_params.get('rvol'):
            params_parts.append(f"Rel Volume ≥ {scan_params['rvol']}x")
        if scan_params.get('include_adr'):
            params_parts.append("Including ADRs")
        if scan_params.get('div_threshold'):
            params_parts.append(f"Dividend ≥ {scan_params['div_threshold']}%")
        
        if params_parts:
            html += f"""
            <div style='background-color:#fff3cd; border-left:4px solid #f39c12; padding:10px; margin:10px 0; font-size:11px;'>
                <strong>🔍 Scan Filters:</strong> {' | '.join(params_parts)}
            </div>
            """
    
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
    # DISABLED: SBI now handles entry quality filtering
    STRONG_BUY_ADX_THRESHOLD = 0
    
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
    
    # =================================================================
    # SBI FILTERING FOR STRONG BUYS
    # =================================================================
    # Separate overheated stocks (Days 1-5 with ATR >= 5%)
    # Filter Strong Buys to SBI >= 8
    overheated_watch = []
    filtered_strong_buys = []
    
    for r in strong_buys:
        days_in_trend = getattr(r, 'psar_days_in_trend', 0)
        atr_volatility = getattr(r, 'atr_volatility', 0)
        gap_slope = getattr(r, 'psar_gap_slope', 0)
        adx_val = getattr(r, 'adx_value', 20)
        prsi_fast_bearish = not getattr(r, 'prsi_fast_bullish', True)
        is_broken = getattr(r, 'is_broken', False)
        sbi = calculate_sbi(days_in_trend, atr_volatility, gap_slope, adx_val, prsi_fast_bearish, is_broken)
        
        # Store SBI on result for display (temporary attribute)
        r._sbi = sbi
        
        # Check if overheated (Days 1-5 with high ATR)
        if is_overheated(days_in_trend, atr_volatility):
            overheated_watch.append(r)
        elif sbi >= 8:
            filtered_strong_buys.append(r)
        else:
            # SBI < 8, move to regular buys
            buys.insert(0, r)  # Add to front of buys
    
    strong_buys = filtered_strong_buys
    
    # Re-sort buys since we added some
    buys.sort(key=lambda x: (
        getattr(x, 'psar_days_in_trend', 999),
        0 if x.obv_bullish else 1,
        -checkbox_count(x)
    ))
    
    # Limit lists to keep report readable
    strong_buys = strong_buys[:50]
    buys = buys[:100]
    early_buys = early_buys[:50]
    holds = holds[:50]
    sells = sells[:30]
    
    # Filter dividend_buys to SBI 9-10 only (best entry quality)
    filtered_dividend_buys = []
    for r in dividend_buys:
        days_in_trend = getattr(r, 'psar_days_in_trend', 0)
        atr_volatility = getattr(r, 'atr_volatility', 0)
        gap_slope = getattr(r, 'psar_gap_slope', 0)
        adx_val = getattr(r, 'adx_value', 20)
        prsi_fast_bearish = not getattr(r, 'prsi_fast_bullish', True)
        is_broken = getattr(r, 'is_broken', False)
        sbi = calculate_sbi(days_in_trend, atr_volatility, gap_slope, adx_val, prsi_fast_bearish, is_broken)
        if sbi >= 9:
            filtered_dividend_buys.append(r)
    dividend_buys = filtered_dividend_buys[:30]
    
    # =================================================================
    # BUILD SUMMARY BOX
    # =================================================================
    if mode in ['Portfolio', 'Friends']:
        html += f"""
        <div class='action-box'>
            <strong>📊 PORTFOLIO SUMMARY:</strong><br>
            🟢🟢 <strong>{len(strong_buys)} Strong Buys</strong> (SBI ≥8) |
            🔥 <strong>{len(overheated_watch)} Overheated</strong> (High ATR - Watch) |
            🟢 <strong>{len(buys)} Buys</strong> |
            ⏸️ {len(holds)} Holds |
            🔴 {len(sells)} Sells |
            ⚡ <strong>{len(early_buys)} Early Buys</strong>
        </div>
        """
    else:
        html += f"""
        <div class='action-box'>
            <strong>📊 ACTIONABLE SIGNALS:</strong><br>
            🟢🟢 <strong>{len(strong_buys)} Strong Buys</strong> (SBI ≥8) |
            🔥 <strong>{len(overheated_watch)} Overheated</strong> (High ATR - Watch) |
            ⚡ <strong>{len(early_buys)} Early Buys</strong><br>
            💰 <strong>{len(dividend_buys)} Dividend Buys</strong> (Yield ≥{div_threshold}%, SBI 9-10)
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
    
    # CUSTOM TICKERS - Show all requested tickers first (bypasses normal categorization)
    if custom_tickers and results:
        html += f"""
        <div class='section-custom'>🔍 REQUESTED TICKERS ({len(results)} stocks)</div>
        <p style='color:#3498db; font-size:11px; margin:5px 0;'>All indicators for requested tickers. Zone shows current signal status.</p>
        """
        html += build_results_table(results, 'CUSTOM', use_v2, True)  # Use portfolio mode to show ATR
    
    # STRONG BUY - Fresh confirmed signals (≤5 days since price crossed PSAR)
    if strong_buys:
        # Apply limit for market mode
        display_strong = strong_buys if is_portfolio_mode else strong_buys[:strong_buy_limit]
        html += f"""
        <div class='section-strongbuy'>🟢🟢 STRONG BUY - Fresh Signals ({len(display_strong)} stocks{f' of {len(strong_buys)}' if len(strong_buys) > len(display_strong) else ''})</div>
        <p style='color:#1e8449; font-size:11px; margin:5px 0;'>SBI ≥ 8. PRSI bullish + Price just crossed above PSAR (≤5 days) + Low ATR. Best entry quality.</p>
        """
        html += build_results_table(display_strong, 'STRONG_BUY', use_v2, is_portfolio_mode)
    
    # OVERHEATED WATCH - Fresh signals but high ATR (potential chase)
    if overheated_watch:
        html += f"""
        <div class='section-warning' style='background-color:#e67e22;'>🔥 OVERHEATED WATCH - High ATR ({len(overheated_watch)} stocks)</div>
        <p style='color:#e67e22; font-size:11px; margin:5px 0;'>Fresh signals (≤5 days) with ATR ≥5%. May be chasing - wait for pullback or use for covered calls.</p>
        """
        html += build_results_table(overheated_watch, 'STRONG_BUY', use_v2, is_portfolio_mode)
    
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
        
        # COVERED CALL CANDIDATES - High ATR + Low ADX stocks (Portfolio/Friends only)
        # High ATR = good premium, Low ADX = choppy/less breakout risk
        if analyze_covered_call and build_covered_call_section:
            # Find stocks with ATR >= 5% AND ADX < 25 that are in buy zones
            high_atr_stocks = []
            all_buy_zone = strong_buys + buys + holds  # Include holds since you own them
            
            for r in all_buy_zone:
                atr_volatility = getattr(r, 'atr_volatility', 0)
                adx_val = getattr(r, 'adx_value', 50)  # Default high to exclude if missing
                days_in_trend = getattr(r, 'psar_days_in_trend', 999)
                
                # High ATR (good premium) + Low ADX (choppy) + Days > 5 (not fresh breakout)
                if atr_volatility >= 5.0 and adx_val < 25 and days_in_trend > 5:
                    # Determine signal type (Days > 5 so it's Buy or Hold, not Strong Buy)
                    if r.prsi_bullish and r.psar_gap >= 0:
                        signal_type = "Buy"
                    else:
                        signal_type = "Hold"
                    
                    high_atr_stocks.append((r, signal_type))
            
            if high_atr_stocks:
                print(f"\n  📞 Analyzing {len(high_atr_stocks)} stocks for covered calls (ATR≥5%, ADX<25, Days>5)...")
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
            <p style='color:#27ae60; font-size:11px; margin:5px 0;'>Dividend stocks (≥{div_threshold}% yield) with SBI 9-10. Best entry quality only.</p>
            """
            html += build_results_table(display_div, 'DIVIDEND', use_v2, False)
    
    # Summary legend
    if mode in ['Portfolio', 'Friends']:
        html += """
    <div class='summary-box'>
        <strong>Legend:</strong><br>
        ⭐ = IBD Stock (click for research) | 
        <strong>Days:</strong> Days since price crossed PSAR (Strong/Buy) or PRSI flipped (Early Buy)<br>
        <strong>SBI:</strong> Smart Buy Indicator (0-10) - D1: ATR | D2: 80%ATR+20%Slope | D3: 60%ATR+40%Slope | D4-5: 40%ATR+40%Slope+20%ADX | D6+: 40%Slope+30%ADX+30%ATR<br>
        &nbsp;&nbsp;&nbsp;PRSI(4) bearish applies -2 penalty for Days 3+ (momentum warning)<br>
        &nbsp;&nbsp;&nbsp;<span style='color:#1e8449'>9-10 = Excellent</span> | <span style='color:#27ae60'>8 = Good</span> | <span style='color:#f39c12'>6-7 = OK</span> | <span style='color:#e67e22'>4-5 = Caution</span> | <span style='color:#c0392b'>0-3 = Avoid</span><br>
        <strong>PRSI:</strong> ↗️ Bullish (14-day) ↘️ Bearish | <span style='color:#e67e22'>⚡ = PRSI(4) bearish (momentum warning)</span><br>
        OBV: 🟢 Accumulation 🔴 Distribution<br>
        <strong>Checkboxes:</strong> DMI (bulls control) | ADX (strong trend) | MACD (momentum up)<br>
        <strong>ATR%:</strong> <span style='color:#27ae60'>Green &lt;3%</span> | <span style='color:#f39c12'>Yellow 3-5%</span> | <span style='color:#e74c3c'>Red &gt;5% + ADX&lt;25 + Days&gt;5 📞 = Consider covered calls</span>
    </div>
    """
    else:
        html += """
    <div class='summary-box'>
        <strong>Legend:</strong><br>
        ⭐ = IBD Stock (click for research) | 
        <strong>Days:</strong> Days since price crossed PSAR (Strong/Buy) or PRSI flipped (Early Buy)<br>
        <strong>SBI:</strong> Smart Buy Indicator (0-10) - D1: ATR | D2: 80%ATR+20%Slope | D3: 60%ATR+40%Slope | D4-5: 40%ATR+40%Slope+20%ADX | D6+: 40%Slope+30%ADX+30%ATR<br>
        &nbsp;&nbsp;&nbsp;PRSI(4) bearish applies -2 penalty for Days 3+ (momentum warning)<br>
        &nbsp;&nbsp;&nbsp;<span style='color:#1e8449'>9-10 = Excellent</span> | <span style='color:#27ae60'>8 = Good</span> | <span style='color:#f39c12'>6-7 = OK</span> | <span style='color:#e67e22'>4-5 = Caution</span> | <span style='color:#c0392b'>0-3 = Avoid</span><br>
        <strong>PRSI:</strong> ↗️ Bullish (14-day) ↘️ Bearish | <span style='color:#e67e22'>⚡ = PRSI(4) bearish (momentum warning)</span><br>
        OBV: 🟢 Accumulation 🔴 Distribution<br>
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
    custom_title: Optional[str] = None,
    scan_params: dict = None,
    custom_tickers: List[str] = None
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
    
    html_body = build_email_body(results, mode, use_v2, cboe_text, total_scanned, div_threshold, scan_params=scan_params, custom_tickers=custom_tickers)
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
                       help='Minimum implied forward EPS growth %% (from PE ratios)')
    parser.add_argument('--rev', type=float, default=None,
                       help='Minimum revenue growth %%')
    parser.add_argument('--mc', type=float, default=None,
                       help='Minimum market cap in millions (default 5000 = $5B)')
    parser.add_argument('--adr', action='store_true',
                       help='Include ADR stocks')
    parser.add_argument('--rvol', type=float, default=None,
                       help='Minimum relative volume (today vs 10-day avg). Range: 0.1-100. E.g., 1.5 = 150%% of avg')
    
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
    parser.add_argument('--tickers-file', type=str, default=None,
                       help='Custom tickers file path (overrides mystocks.txt)')
    parser.add_argument('--div', type=float, default=2.0,
                       help='Minimum dividend yield %% for dividend section (default: 2.0)')
    parser.add_argument('-t', '--title', type=str, default=None,
                       help='Custom email subject title')
    parser.add_argument('--skip-options', action='store_true',
                       help='Skip fetching options data (for shorts scan when rate limited)')
    
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
    
    # Get CBOE data (includes Total P/C and VIX P/C ratios)
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
        'rvol_filter': args.rvol,
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
        scanner = PortfolioScanner(tickers_file=args.tickers_file, **kwargs)
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
        
        # Collect all results WITH filtering applied
        # EXCEPTION: --tickers bypasses all filters (user explicitly requested these)
        results = []
        filtered_count = 0
        ticker_list = scanner.get_tickers()
        bypass_filters = custom_tickers is not None
        
        for ticker, source in ticker_list:
            result = scanner.scan_ticker(ticker, source)
            if result:
                if bypass_filters or scanner.filter_result(result):  # Bypass filters for custom tickers
                    results.append(result)
                else:
                    filtered_count += 1
        
        if not args.quiet:
            print("\n")  # Clear progress bar
            if filtered_count > 0:
                print(f"  Filtered out {filtered_count} stocks (EPS/Rev/Market Cap criteria)")
        
        # Special handling for shorts mode
        if mode in ['Shorts', 'ShortScan'] and analyze_short_candidate:
            # Analyze results as short candidates
            from analysis.shorts import ShortCandidate
            
            if not args.quiet:
                print(f"\n  🐻 Analyzing {len(results)} stocks for short opportunities...")
            
            # First pass: Score all stocks WITHOUT fetching options (fast)
            all_candidates = []
            
            for r in results:
                # Get PRSI-4 data (fast signal for shorts)
                prsi4_bearish = not getattr(r, 'prsi_fast_bullish', True)
                # Try prsi_fast_days_since_flip first, fall back to prsi_days_since_flip
                prsi4_days = getattr(r, 'prsi_fast_days_since_flip', None)
                if prsi4_days is None:
                    prsi4_days = r.prsi_days_since_flip if prsi4_bearish else 0
                
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
                    psar_gap_slope=getattr(r, 'psar_gap_slope', 0),
                    prsi4_bearish=prsi4_bearish,
                    prsi4_days=prsi4_days,
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
                    # Delay 2 seconds between each request to avoid rate limiting
                    if i > 0:
                        time.sleep(2.0)
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
                
                short_candidates = []
                skipped = []
                
                # Skip options fetching if flag is set
                if args.skip_options:
                    if not args.quiet:
                        print(f"\n  ⏭️ Skipping options fetch (--skip-options)")
                    short_candidates = top_for_options
                else:
                    # Second pass: Fetch options with delay to avoid rate limiting
                    from analysis.shorts import get_put_spread_recommendation
                    import time
                    
                    if top_for_options and not args.quiet:
                        print(f"\n  📊 Fetching put spreads for top {len(top_for_options)} candidates...")
                    
                    for i, candidate in enumerate(top_for_options):
                        # Delay 2 seconds between each request to avoid rate limiting
                        if i > 0:
                            time.sleep(2.0)
                        
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
                    
                    # FALLBACK: If all rate limited, show candidates WITHOUT options data
                    if len(short_candidates) == 0 and len(skipped) > 0:
                        print(f"\n  ⚠️ Rate limited - showing candidates without options data")
                        short_candidates = skipped[:25]  # Show top 25 anyway
                        skipped = []
                
                # Print console summary
                if not args.quiet:
                    print(f"\n{'='*60}")
                    print(f"SHORT SCAN COMPLETE: {len(results)} stocks analyzed")
                    print(f"{'='*60}")
                    print(f"  🔴 Short Candidates: {len(short_candidates)}")
                    if skipped:
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
                # Build scan params for display
                scan_params = {
                    'market_cap': args.mc,
                    'eps_growth': args.eps,
                    'rev_growth': args.rev,
                    'rvol': args.rvol,
                    'include_adr': args.adr,
                    'div_threshold': args.div
                }
                
                send_email(
                    results=results,
                    mode=mode,
                    use_v2=use_v2,
                    cboe_text=cboe_text,
                    total_scanned=summary.total_scanned,
                    additional_email=args.email_to,
                    div_threshold=args.div,
                    custom_title=args.title,
                    scan_params=scan_params,
                    custom_tickers=custom_tickers
                )
            
            # Save HTML if requested
            if args.html:
                scan_params = {
                    'market_cap': args.mc,
                    'eps_growth': args.eps,
                    'rev_growth': args.rev,
                    'rvol': args.rvol,
                    'include_adr': args.adr,
                    'div_threshold': args.div
                }
                html = build_email_body(results, mode, use_v2, cboe_text, summary.total_scanned, args.div, scan_params=scan_params, custom_tickers=custom_tickers)
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

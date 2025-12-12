"""
PSAR (Parabolic Stop and Reverse) Indicator
============================================
Calculates Price PSAR and provides gap analysis.

In v2, PSAR is used as a RISK FILTER, not the primary signal.
- Gap < 3% = low risk entry
- Gap 3-5% = medium risk
- Gap > 5% = NO ENTRY (too much risk)

The primary signal is PRSI (PSAR on RSI) - see prsi.py
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, Optional

# Import config - handle both direct run and module import
try:
    from utils.config import (
        PSAR_AF, PSAR_MAX_AF,
        GAP_EXCELLENT, GAP_ACCEPTABLE, GAP_MAX,
        PSAR_STRONG_BUY, PSAR_BUY, PSAR_NEUTRAL_LOW, PSAR_NEUTRAL_HIGH, PSAR_SELL
    )
except ImportError:
    # Fallback defaults if config not available
    PSAR_AF = 0.02
    PSAR_MAX_AF = 0.2
    GAP_EXCELLENT = 3.0
    GAP_ACCEPTABLE = 5.0
    GAP_MAX = 5.0
    PSAR_STRONG_BUY = 5.0
    PSAR_BUY = 0.0
    PSAR_NEUTRAL_LOW = -2.0
    PSAR_NEUTRAL_HIGH = 2.0
    PSAR_SELL = -5.0


def calculate_psar(df: pd.DataFrame, af: float = None, max_af: float = None) -> pd.Series:
    """
    Calculate Parabolic SAR for a price series.
    
    Args:
        df: DataFrame with 'High', 'Low', 'Close' columns
        af: Acceleration factor (default from config)
        max_af: Maximum acceleration factor (default from config)
    
    Returns:
        Series of PSAR values
    """
    if af is None:
        af = PSAR_AF
    if max_af is None:
        max_af = PSAR_MAX_AF
    
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    length = len(df)
    psar = pd.Series(index=df.index, dtype=float)
    af_series = pd.Series(index=df.index, dtype=float)
    trend = pd.Series(index=df.index, dtype=int)  # 1 = uptrend, -1 = downtrend
    ep = pd.Series(index=df.index, dtype=float)   # Extreme point
    
    # Initialize
    trend.iloc[0] = 1  # Start assuming uptrend
    psar.iloc[0] = low.iloc[0]
    ep.iloc[0] = high.iloc[0]
    af_series.iloc[0] = af
    
    for i in range(1, length):
        # Previous values
        prev_psar = psar.iloc[i-1]
        prev_af = af_series.iloc[i-1]
        prev_ep = ep.iloc[i-1]
        prev_trend = trend.iloc[i-1]
        
        if prev_trend == 1:  # Was in uptrend
            # Calculate new PSAR
            new_psar = prev_psar + prev_af * (prev_ep - prev_psar)
            
            # PSAR cannot be above prior two lows
            new_psar = min(new_psar, low.iloc[i-1])
            if i >= 2:
                new_psar = min(new_psar, low.iloc[i-2])
            
            # Check for trend reversal
            if low.iloc[i] < new_psar:
                # Reversal to downtrend
                trend.iloc[i] = -1
                psar.iloc[i] = prev_ep  # PSAR becomes the previous EP
                ep.iloc[i] = low.iloc[i]
                af_series.iloc[i] = af
            else:
                # Continue uptrend
                trend.iloc[i] = 1
                psar.iloc[i] = new_psar
                
                # Update EP if new high
                if high.iloc[i] > prev_ep:
                    ep.iloc[i] = high.iloc[i]
                    af_series.iloc[i] = min(prev_af + af, max_af)
                else:
                    ep.iloc[i] = prev_ep
                    af_series.iloc[i] = prev_af
        
        else:  # Was in downtrend
            # Calculate new PSAR
            new_psar = prev_psar + prev_af * (prev_ep - prev_psar)
            
            # PSAR cannot be below prior two highs
            new_psar = max(new_psar, high.iloc[i-1])
            if i >= 2:
                new_psar = max(new_psar, high.iloc[i-2])
            
            # Check for trend reversal
            if high.iloc[i] > new_psar:
                # Reversal to uptrend
                trend.iloc[i] = 1
                psar.iloc[i] = prev_ep  # PSAR becomes the previous EP
                ep.iloc[i] = high.iloc[i]
                af_series.iloc[i] = af
            else:
                # Continue downtrend
                trend.iloc[i] = -1
                psar.iloc[i] = new_psar
                
                # Update EP if new low
                if low.iloc[i] < prev_ep:
                    ep.iloc[i] = low.iloc[i]
                    af_series.iloc[i] = min(prev_af + af, max_af)
                else:
                    ep.iloc[i] = prev_ep
                    af_series.iloc[i] = prev_af
    
    return psar


def calculate_psar_gap(price: float, psar: float) -> float:
    """
    Calculate the percentage gap between price and PSAR.
    
    Positive = price above PSAR (bullish)
    Negative = price below PSAR (bearish)
    
    Args:
        price: Current price
        psar: Current PSAR value
    
    Returns:
        Gap as percentage (e.g., 5.2 for 5.2%)
    """
    if psar == 0:
        return 0.0
    return ((price - psar) / psar) * 100


def get_psar_trend(price: float, psar: float) -> str:
    """
    Determine if price is above or below PSAR.
    
    Args:
        price: Current price
        psar: Current PSAR value
    
    Returns:
        'bullish' if price > PSAR, 'bearish' if price < PSAR
    """
    return 'bullish' if price > psar else 'bearish'


def classify_psar_zone_v1(gap_percent: float) -> str:
    """
    V1 CLASSIC: Classify zone based on PSAR gap (used as primary signal).
    
    This is the OLD logic - kept for --classic mode comparison.
    
    Args:
        gap_percent: PSAR gap percentage
    
    Returns:
        Zone name (STRONG_BUY, BUY, NEUTRAL, WEAK, SELL)
    """
    if gap_percent >= PSAR_STRONG_BUY:
        return 'STRONG_BUY'
    elif gap_percent >= PSAR_BUY:
        return 'BUY'
    elif gap_percent >= PSAR_NEUTRAL_LOW:
        return 'NEUTRAL'
    elif gap_percent >= PSAR_SELL:
        return 'WEAK'
    else:
        return 'SELL'


def get_entry_risk(gap_percent: float) -> Dict[str, any]:
    """
    V2: Assess entry risk based on PSAR gap.
    
    In v2, PSAR gap is used for RISK assessment, not signal generation.
    
    Args:
        gap_percent: Absolute PSAR gap percentage
    
    Returns:
        Dict with risk assessment:
        - risk_level: 'low', 'medium', 'high', 'no_entry'
        - gap_score: 0-25 points for timing score
        - entry_allowed: bool
        - reason: explanation
    """
    abs_gap = abs(gap_percent)
    
    if abs_gap < GAP_EXCELLENT:
        return {
            'risk_level': 'low',
            'gap_score': 25,
            'entry_allowed': True,
            'reason': f'Gap {abs_gap:.1f}% < {GAP_EXCELLENT}% - excellent entry point'
        }
    elif abs_gap < GAP_ACCEPTABLE:
        return {
            'risk_level': 'medium',
            'gap_score': 15,
            'entry_allowed': True,
            'reason': f'Gap {abs_gap:.1f}% - acceptable but elevated risk'
        }
    else:
        return {
            'risk_level': 'high',
            'gap_score': 0,
            'entry_allowed': False,
            'reason': f'Gap {abs_gap:.1f}% > {GAP_MAX}% - NO ENTRY, wait for pullback'
        }


def get_psar_data(df: pd.DataFrame) -> Dict[str, any]:
    """
    Calculate all PSAR-related data for a stock.
    
    Args:
        df: DataFrame with OHLC data
    
    Returns:
        Dict with:
        - psar: current PSAR value
        - price: current price
        - gap_percent: gap as percentage
        - trend: 'bullish' or 'bearish'
        - v1_zone: classic zone classification
        - entry_risk: v2 risk assessment
        - days_in_trend: consecutive days in current trend
        - gap_slope: change in gap over 3 days (positive = widening)
        - cross_direction: 'up' (bullish cross), 'down' (bearish cross/breakdown), or None
        - is_broken: True if recently crossed DOWN (was bullish, now bearish)
    """
    if len(df) < 10:
        return None
    
    psar_series = calculate_psar(df)
    current_psar = psar_series.iloc[-1]
    current_price = df['Close'].iloc[-1]
    
    gap_percent = calculate_psar_gap(current_price, current_psar)
    trend = get_psar_trend(current_price, current_psar)
    
    # Count days in current trend
    days_in_trend = 1
    for i in range(len(df) - 2, -1, -1):
        price = df['Close'].iloc[i]
        psar = psar_series.iloc[i]
        if get_psar_trend(price, psar) == trend:
            days_in_trend += 1
        else:
            break
    
    # Detect cross direction (what direction did price cross PSAR?)
    cross_direction = None
    is_broken = False
    
    if days_in_trend <= 5:  # Recent cross (within 5 days)
        # Look at the day before the cross
        cross_idx = len(df) - days_in_trend - 1
        if cross_idx >= 0:
            prev_price = df['Close'].iloc[cross_idx]
            prev_psar = psar_series.iloc[cross_idx]
            prev_trend = get_psar_trend(prev_price, prev_psar)
            
            if trend == 'bullish' and prev_trend == 'bearish':
                cross_direction = 'up'  # Bullish cross - price broke UP through PSAR
            elif trend == 'bearish' and prev_trend == 'bullish':
                cross_direction = 'down'  # Bearish cross - price broke DOWN through PSAR
                is_broken = True  # This is a BREAKDOWN, not consolidation
    
    # Calculate gap slope (only using data SINCE the cross)
    # Day 1: slope = 0 (no prior data in this trend)
    # Day 2: slope = today_gap - day1_gap
    # Day 3+: slope = today_gap - gap_N_days_ago (where N = min(3, days_in_trend-1))
    gap_slope = 0.0
    
    if days_in_trend >= 2 and len(df) >= 2 and len(psar_series) >= 2:
        # How many days back can we look within this trend?
        lookback = min(3, days_in_trend - 1)
        
        if lookback >= 1:
            price_lookback = df['Close'].iloc[-(lookback + 1)]
            psar_lookback = psar_series.iloc[-(lookback + 1)]
            gap_lookback = calculate_psar_gap(price_lookback, psar_lookback)
            gap_slope = gap_percent - gap_lookback
    
    return {
        'psar': current_psar,
        'price': current_price,
        'gap_percent': gap_percent,
        'trend': trend,
        'v1_zone': classify_psar_zone_v1(gap_percent),
        'entry_risk': get_entry_risk(gap_percent),
        'days_in_trend': days_in_trend,
        'gap_slope': gap_slope,
        'cross_direction': cross_direction,  # 'up' or 'down' or None
        'is_broken': is_broken,  # True if recently broke DOWN through PSAR
        'psar_series': psar_series  # Full series for charting
    }


def format_psar_display(gap_percent: float, include_emoji: bool = True) -> str:
    """
    Format PSAR gap for display in reports.
    
    Args:
        gap_percent: PSAR gap percentage
        include_emoji: Whether to include trend emoji
    
    Returns:
        Formatted string like "+5.2% 📈" or "-3.1% 📉"
    """
    sign = '+' if gap_percent >= 0 else ''
    emoji = ''
    if include_emoji:
        if gap_percent >= 5:
            emoji = ' 🔥'  # Very extended
        elif gap_percent >= 0:
            emoji = ' 📈'
        elif gap_percent >= -5:
            emoji = ' 📉'
        else:
            emoji = ' ⚠️'  # Very negative
    
    return f"{sign}{gap_percent:.1f}%{emoji}"


# =============================================================================
# STANDALONE TESTING
# =============================================================================
if __name__ == "__main__":
    # Test with sample data
    print("PSAR Module Test")
    print("=" * 50)
    
    # Create sample data
    import yfinance as yf
    
    ticker = "AAPL"
    print(f"\nFetching data for {ticker}...")
    
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="6mo")
        
        if len(df) > 0:
            result = get_psar_data(df)
            
            print(f"\nResults for {ticker}:")
            print(f"  Price: ${result['price']:.2f}")
            print(f"  PSAR: ${result['psar']:.2f}")
            print(f"  Gap: {format_psar_display(result['gap_percent'])}")
            print(f"  Trend: {result['trend']}")
            print(f"  Days in trend: {result['days_in_trend']}")
            print(f"  V1 Zone: {result['v1_zone']}")
            print(f"  Entry Risk: {result['entry_risk']['risk_level']}")
            print(f"  Entry Allowed: {result['entry_risk']['entry_allowed']}")
            print(f"  Reason: {result['entry_risk']['reason']}")
        else:
            print("No data received")
    except Exception as e:
        print(f"Error: {e}")

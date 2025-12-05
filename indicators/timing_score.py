"""
Timing Score Indicator
======================
Combines mean-reversion indicators into a single score (0-100).

Components:
- Williams %R (25 pts): Not at extremes (-80 to -20)
- Bollinger Position (25 pts): Near middle band
- RSI Position (25 pts): RSI 40-60 ideal
- PSAR Gap (25 pts): Gap < 3% = full points

V2 ROLE: ENTRY TIMING
High Timing Score = Good time to enter (not overbought/oversold)
Used to decide WHEN to enter, not which stocks to trade.

Key insight: Trend Score tells you WHAT to trade,
Timing Score tells you WHEN to enter.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional

try:
    from utils.config import (
        WILLIAMS_R_PERIOD, WILLIAMS_R_OVERBOUGHT, WILLIAMS_R_OVERSOLD,
        BOLLINGER_PERIOD, BOLLINGER_STD,
        RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD,
        GAP_EXCELLENT, GAP_ACCEPTABLE, GAP_MAX,
        TIMING_SCORE_OVERBOUGHT, TIMING_SCORE_OVERSOLD,
        TIMING_SCORE_IDEAL_MIN, TIMING_SCORE_IDEAL_MAX,
        TIMING_SCORE_WEIGHTS
    )
except ImportError:
    WILLIAMS_R_PERIOD = 14
    WILLIAMS_R_OVERBOUGHT = -20
    WILLIAMS_R_OVERSOLD = -80
    BOLLINGER_PERIOD = 20
    BOLLINGER_STD = 2.0
    RSI_PERIOD = 14
    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30
    GAP_EXCELLENT = 3.0
    GAP_ACCEPTABLE = 5.0
    GAP_MAX = 5.0
    TIMING_SCORE_OVERBOUGHT = 80
    TIMING_SCORE_OVERSOLD = 30
    TIMING_SCORE_IDEAL_MIN = 40
    TIMING_SCORE_IDEAL_MAX = 70
    TIMING_SCORE_WEIGHTS = {'williams_r': 25, 'bollinger': 25, 'rsi_position': 25, 'psar_gap': 25}


def calculate_williams_r(df: pd.DataFrame, period: int = None) -> pd.Series:
    """Calculate Williams %R."""
    if period is None:
        period = WILLIAMS_R_PERIOD
    
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    highest_high = high.rolling(window=period).max()
    lowest_low = low.rolling(window=period).min()
    
    williams_r = -100 * (highest_high - close) / (highest_high - lowest_low)
    return williams_r


def calculate_williams_score(df: pd.DataFrame, max_points: int = 25) -> Dict[str, any]:
    """
    Calculate Williams %R component of timing score.
    
    Best entry zone: -80 to -20 (not at extremes)
    
    Scoring:
    - Between -60 and -40: 25 pts (ideal)
    - Between -70 and -30: 20 pts (good)
    - Between -80 and -20: 15 pts (acceptable)
    - Outside range: 5-10 pts (overbought/oversold)
    """
    williams = calculate_williams_r(df)
    current = williams.iloc[-1]
    
    if -60 <= current <= -40:
        score = 25
        zone = "Ideal entry zone"
    elif -70 <= current <= -30:
        score = 20
        zone = "Good entry zone"
    elif -80 <= current <= -20:
        score = 15
        zone = "Acceptable"
    elif current > WILLIAMS_R_OVERBOUGHT:
        score = 5
        zone = "Overbought"
    elif current < WILLIAMS_R_OVERSOLD:
        score = 10  # Slightly better - potential bounce
        zone = "Oversold"
    else:
        score = 10
        zone = "Neutral"
    
    return {
        'score': min(score, max_points),
        'max': max_points,
        'value': current,
        'zone': zone,
        'is_oversold': current < WILLIAMS_R_OVERSOLD,
        'is_overbought': current > WILLIAMS_R_OVERBOUGHT,
        'details': [f"Williams %R {current:.1f}: {zone} (+{score})"]
    }


def calculate_bollinger_bands(df: pd.DataFrame, period: int = None, 
                               std: float = None) -> Dict[str, pd.Series]:
    """Calculate Bollinger Bands."""
    if period is None:
        period = BOLLINGER_PERIOD
    if std is None:
        std = BOLLINGER_STD
    
    close = df['Close']
    
    middle = close.rolling(window=period).mean()
    rolling_std = close.rolling(window=period).std()
    
    upper = middle + (rolling_std * std)
    lower = middle - (rolling_std * std)
    
    return {
        'upper': upper,
        'middle': middle,
        'lower': lower
    }


def calculate_bollinger_score(df: pd.DataFrame, max_points: int = 25) -> Dict[str, any]:
    """
    Calculate Bollinger position component of timing score.
    
    Best entry: Near middle band (not at extremes)
    
    Scoring:
    - Within 20% of middle: 25 pts (ideal)
    - Within 40% of middle: 20 pts (good)
    - Within 60% of middle: 15 pts (acceptable)
    - Near bands: 5-10 pts (extreme)
    """
    bb = calculate_bollinger_bands(df)
    close = df['Close'].iloc[-1]
    
    upper = bb['upper'].iloc[-1]
    middle = bb['middle'].iloc[-1]
    lower = bb['lower'].iloc[-1]
    
    # Calculate position as percentage of band width
    band_width = upper - lower
    if band_width == 0:
        return {'score': 15, 'max': max_points, 'position': 0.5, 'zone': 'N/A'}
    
    position = (close - lower) / band_width  # 0 = at lower, 1 = at upper
    distance_from_middle = abs(position - 0.5) * 2  # 0 = at middle, 1 = at band
    
    if distance_from_middle <= 0.2:
        score = 25
        zone = "Near middle band"
    elif distance_from_middle <= 0.4:
        score = 20
        zone = "Good position"
    elif distance_from_middle <= 0.6:
        score = 15
        zone = "Acceptable"
    elif position > 0.8:
        score = 5
        zone = "Near upper band (overbought)"
    elif position < 0.2:
        score = 10
        zone = "Near lower band (oversold)"
    else:
        score = 10
        zone = "Extended"
    
    return {
        'score': min(score, max_points),
        'max': max_points,
        'position': position,
        'distance_from_middle': distance_from_middle,
        'zone': zone,
        'upper': upper,
        'middle': middle,
        'lower': lower,
        'details': [f"BB position {position:.2f}: {zone} (+{score})"]
    }


def calculate_rsi(df: pd.DataFrame, period: int = None) -> pd.Series:
    """Calculate RSI."""
    if period is None:
        period = RSI_PERIOD
    
    close = df['Close']
    delta = close.diff()
    
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_rsi_position_score(df: pd.DataFrame, max_points: int = 25) -> Dict[str, any]:
    """
    Calculate RSI position component of timing score.
    
    Ideal entry: RSI 40-60 (not extreme)
    
    Scoring:
    - RSI 45-55: 25 pts (ideal)
    - RSI 40-60: 20 pts (good)
    - RSI 35-65: 15 pts (acceptable)
    - RSI > 70 or < 30: 5-10 pts (extreme)
    """
    rsi = calculate_rsi(df)
    current = rsi.iloc[-1]
    
    if 45 <= current <= 55:
        score = 25
        zone = "Ideal RSI zone"
    elif 40 <= current <= 60:
        score = 20
        zone = "Good RSI zone"
    elif 35 <= current <= 65:
        score = 15
        zone = "Acceptable RSI"
    elif current >= RSI_OVERBOUGHT:
        score = 5
        zone = "RSI Overbought"
    elif current <= RSI_OVERSOLD:
        score = 10  # Potential bounce
        zone = "RSI Oversold"
    else:
        score = 12
        zone = "RSI Extended"
    
    return {
        'score': min(score, max_points),
        'max': max_points,
        'value': current,
        'zone': zone,
        'is_overbought': current >= RSI_OVERBOUGHT,
        'is_oversold': current <= RSI_OVERSOLD,
        'details': [f"RSI {current:.1f}: {zone} (+{score})"]
    }


def calculate_gap_score(psar_gap: float, max_points: int = 25) -> Dict[str, any]:
    """
    Calculate PSAR gap component of timing score.
    
    Best entry: Gap < 3% (low risk)
    
    Scoring:
    - Gap < 2%: 25 pts (excellent)
    - Gap < 3%: 20 pts (good)
    - Gap < 4%: 15 pts (acceptable)
    - Gap < 5%: 10 pts (elevated risk)
    - Gap >= 5%: 0 pts (NO ENTRY)
    """
    abs_gap = abs(psar_gap)
    
    if abs_gap < 2:
        score = 25
        risk = "Excellent entry - minimal gap"
    elif abs_gap < GAP_EXCELLENT:
        score = 20
        risk = "Good entry - low risk"
    elif abs_gap < 4:
        score = 15
        risk = "Acceptable - moderate risk"
    elif abs_gap < GAP_MAX:
        score = 10
        risk = "Elevated risk"
    else:
        score = 0
        risk = "NO ENTRY - gap too large"
    
    return {
        'score': min(score, max_points),
        'max': max_points,
        'gap': psar_gap,
        'abs_gap': abs_gap,
        'risk': risk,
        'entry_allowed': abs_gap < GAP_MAX,
        'details': [f"Gap {psar_gap:+.1f}%: {risk} (+{score})"]
    }


def calculate_timing_score(df: pd.DataFrame, psar_gap: float = 0) -> Dict[str, any]:
    """
    Calculate complete Timing Score (0-100).
    
    Args:
        df: DataFrame with OHLC data
        psar_gap: PSAR gap percentage from psar.py
    
    Returns:
        Dict with total score and component breakdown
    """
    if len(df) < 30:
        return {'error': 'Insufficient data', 'score': 50}
    
    williams = calculate_williams_score(df, TIMING_SCORE_WEIGHTS['williams_r'])
    bollinger = calculate_bollinger_score(df, TIMING_SCORE_WEIGHTS['bollinger'])
    rsi = calculate_rsi_position_score(df, TIMING_SCORE_WEIGHTS['rsi_position'])
    gap = calculate_gap_score(psar_gap, TIMING_SCORE_WEIGHTS['psar_gap'])
    
    total_score = williams['score'] + bollinger['score'] + rsi['score'] + gap['score']
    
    # Determine overall assessment
    if total_score >= TIMING_SCORE_OVERBOUGHT:
        assessment = "Overbought - wait for pullback"
        emoji = "🔥"
        entry_quality = "C"
    elif total_score >= TIMING_SCORE_IDEAL_MAX:
        assessment = "Good entry timing"
        emoji = "✅"
        entry_quality = "B"
    elif total_score >= TIMING_SCORE_IDEAL_MIN:
        assessment = "Ideal entry timing"
        emoji = "✨"
        entry_quality = "A"
    elif total_score >= TIMING_SCORE_OVERSOLD:
        assessment = "Oversold - watch for bounce"
        emoji = "❄️"
        entry_quality = "B"
    else:
        assessment = "Poor timing - wait"
        emoji = "⚠️"
        entry_quality = "C"
    
    # Check if entry is blocked by gap
    if not gap['entry_allowed']:
        assessment = "NO ENTRY - gap > 5%"
        emoji = "🚫"
        entry_quality = "X"
    
    return {
        'score': total_score,
        'max': 100,
        'assessment': assessment,
        'emoji': emoji,
        'entry_quality': entry_quality,
        'is_ideal': TIMING_SCORE_IDEAL_MIN <= total_score <= TIMING_SCORE_IDEAL_MAX,
        'is_overbought': total_score >= TIMING_SCORE_OVERBOUGHT,
        'is_oversold': total_score < TIMING_SCORE_OVERSOLD,
        'entry_allowed': gap['entry_allowed'],
        'components': {
            'williams': williams,
            'bollinger': bollinger,
            'rsi_position': rsi,
            'psar_gap': gap
        },
        'display': f"{total_score}{emoji}"
    }


def get_entry_grade(trend_score: int, timing_score: int, 
                    gap_allowed: bool = True) -> Dict[str, any]:
    """
    Combine Trend and Timing scores into entry grade.
    
    NOTE: We no longer block on gap. PRSI is primary signal.
    Gap affects grade quality, not eligibility.
    
    Args:
        trend_score: From trend_score.py (0-100)
        timing_score: From this module (0-100)
        gap_allowed: Whether gap is < 5% (affects grade, doesn't block)
    
    Returns:
        Dict with grade and recommendation
    """
    # Grade based primarily on trend score (stock quality)
    # Timing and gap affect the grade level
    
    # Strong trend = A or B
    if trend_score >= 70:
        if gap_allowed and 40 <= timing_score <= 70:
            return {
                'grade': 'A',
                'score': trend_score,
                'color': 'green',
                'action': 'STRONG ENTRY',
                'description': 'Strong trend + ideal timing + low gap'
            }
        else:
            return {
                'grade': 'B',
                'score': trend_score,
                'color': 'yellow',
                'action': 'GOOD ENTRY',
                'description': 'Strong trend (gap or timing not ideal)'
            }
    
    # Decent trend = B or C
    if trend_score >= 50:
        if gap_allowed:
            return {
                'grade': 'B',
                'score': trend_score,
                'color': 'yellow',
                'action': 'ENTER with caution',
                'description': 'Decent trend'
            }
        else:
            return {
                'grade': 'C',
                'score': trend_score,
                'color': 'orange',
                'action': 'CAUTION - extended',
                'description': 'Decent trend but gap large'
            }
    
    # Weak trend = C or D
    if trend_score >= 30:
        return {
            'grade': 'C',
            'score': trend_score,
            'color': 'orange',
            'action': 'WAIT',
            'description': 'Weak trend'
        }
    
    return {
        'grade': 'D',
        'score': trend_score,
        'color': 'red',
        'action': 'AVOID',
        'description': 'Very weak trend'
    }


# =============================================================================
# STANDALONE TESTING
# =============================================================================
if __name__ == "__main__":
    print("Timing Score Module Test")
    print("=" * 60)
    
    import yfinance as yf
    
    test_cases = [
        ("AAPL", 5.0),   # Simulated PSAR gap
        ("NVDA", -6.0),  # Negative gap (below PSAR)
        ("MSTR", -9.0),  # Large negative gap
        ("META", 7.0),   # Large positive gap
    ]
    
    for ticker, mock_gap in test_cases:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="6mo")
            
            if len(df) > 0:
                data = calculate_timing_score(df, psar_gap=mock_gap)
                print(f"\n{ticker} (gap: {mock_gap:+.1f}%): {data['display']} ({data['score']}/100)")
                print(f"  Assessment: {data['assessment']}")
                print(f"  Entry Quality: {data['entry_quality']}")
                print(f"  Entry Allowed: {'✅' if data['entry_allowed'] else '❌'}")
                print(f"  Components:")
                for name, comp in data['components'].items():
                    print(f"    {name}: {comp['score']}/{comp['max']} - {comp.get('zone', comp.get('risk', ''))}")
        except Exception as e:
            print(f"\n{ticker}: Error - {e}")

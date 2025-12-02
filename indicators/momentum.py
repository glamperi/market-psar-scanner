"""
Momentum Indicator
==================
Calculates momentum score and provides v2 interpretation.

V2 KEY CHANGE:
- v1: High momentum (9-10) = STRONG BUY (wrong - buying exhaustion)
- v2: High momentum (9-10) = HOLD ONLY (already extended, no new entries)
- v2: Ideal entry = Momentum 5-7 (accelerating, not exhausted)

Momentum measures the strength and persistence of a trend since
the PSAR signal started. A high score means the trend has been
going for a while - good for holding, bad for new entries.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple

# Import config - handle both direct run and module import
try:
    from utils.config import (
        MOMENTUM_EXHAUSTED_MIN, MOMENTUM_STRONG_MIN,
        MOMENTUM_IDEAL_MIN, MOMENTUM_IDEAL_MAX,
        MOMENTUM_WEAK_MAX, MOMENTUM_LOOKBACK
    )
except ImportError:
    MOMENTUM_EXHAUSTED_MIN = 9
    MOMENTUM_STRONG_MIN = 7
    MOMENTUM_IDEAL_MIN = 5
    MOMENTUM_IDEAL_MAX = 7
    MOMENTUM_WEAK_MAX = 3
    MOMENTUM_LOOKBACK = 10


def calculate_momentum_score(df: pd.DataFrame, psar_series: pd.Series = None) -> int:
    """
    Calculate momentum score (1-10) based on price action since PSAR signal.
    
    The score measures:
    - Days since PSAR flip
    - Consistency of direction
    - Rate of change
    
    Args:
        df: DataFrame with OHLC data
        psar_series: Optional PSAR series (calculates if not provided)
    
    Returns:
        Momentum score 1-10
    """
    if len(df) < MOMENTUM_LOOKBACK:
        return 5  # Neutral default
    
    close = df['Close']
    
    # If no PSAR provided, use simple price momentum
    if psar_series is None:
        # Calculate based on recent price action
        lookback = min(MOMENTUM_LOOKBACK, len(df) - 1)
        
        # Count up days vs down days
        changes = close.diff().iloc[-lookback:]
        up_days = (changes > 0).sum()
        down_days = (changes < 0).sum()
        
        # Calculate rate of change
        roc = ((close.iloc[-1] / close.iloc[-lookback]) - 1) * 100
        
        # Determine trend direction
        if close.iloc[-1] > close.iloc[-lookback]:
            # Uptrend - score based on consistency and strength
            consistency = up_days / lookback
            
            if roc > 15 and consistency > 0.7:
                score = 10
            elif roc > 10 and consistency > 0.6:
                score = 9
            elif roc > 7 and consistency > 0.5:
                score = 8
            elif roc > 5 and consistency > 0.5:
                score = 7
            elif roc > 3:
                score = 6
            elif roc > 0:
                score = 5
            else:
                score = 4
        else:
            # Downtrend
            consistency = down_days / lookback
            
            if roc < -15 and consistency > 0.7:
                score = 1
            elif roc < -10 and consistency > 0.6:
                score = 2
            elif roc < -5 and consistency > 0.5:
                score = 3
            elif roc < 0:
                score = 4
            else:
                score = 5
    else:
        # Use PSAR to determine momentum
        current_price = close.iloc[-1]
        current_psar = psar_series.iloc[-1]
        
        # Determine if bullish or bearish
        is_bullish = current_price > current_psar
        
        # Count days in current trend
        days_in_trend = 1
        for i in range(len(df) - 2, max(0, len(df) - 50), -1):
            price = close.iloc[i]
            psar = psar_series.iloc[i]
            if (price > psar) == is_bullish:
                days_in_trend += 1
            else:
                break
        
        # Calculate gap percentage
        gap_pct = abs((current_price - current_psar) / current_psar) * 100
        
        if is_bullish:
            # Score based on days and gap
            if days_in_trend >= 20 and gap_pct > 10:
                score = 10
            elif days_in_trend >= 15 and gap_pct > 7:
                score = 9
            elif days_in_trend >= 10 and gap_pct > 5:
                score = 8
            elif days_in_trend >= 7 and gap_pct > 3:
                score = 7
            elif days_in_trend >= 5:
                score = 6
            elif days_in_trend >= 3:
                score = 5
            else:
                score = 4
        else:
            # Bearish - lower score
            if days_in_trend >= 15 and gap_pct > 10:
                score = 1
            elif days_in_trend >= 10 and gap_pct > 7:
                score = 2
            elif days_in_trend >= 7 and gap_pct > 5:
                score = 3
            elif days_in_trend >= 5:
                score = 4
            else:
                score = 5
    
    return max(1, min(10, score))


def interpret_momentum_v1(score: int) -> Dict[str, any]:
    """
    V1 CLASSIC interpretation - kept for --classic mode.
    
    v1 logic: Higher momentum = better buy signal (WRONG)
    
    Args:
        score: Momentum score 1-10
    
    Returns:
        Dict with interpretation
    """
    if score >= 9:
        return {
            'zone': 'STRONG_BUY',
            'action': 'Buy aggressively',
            'description': 'Very strong momentum',
            'emoji': '🔥🔥'
        }
    elif score >= 7:
        return {
            'zone': 'BUY',
            'action': 'Buy',
            'description': 'Strong momentum',
            'emoji': '🔥'
        }
    elif score >= 5:
        return {
            'zone': 'NEUTRAL',
            'action': 'Hold',
            'description': 'Neutral momentum',
            'emoji': ''
        }
    elif score >= 3:
        return {
            'zone': 'WEAK',
            'action': 'Caution',
            'description': 'Weak momentum',
            'emoji': '📉'
        }
    else:
        return {
            'zone': 'SELL',
            'action': 'Sell/Avoid',
            'description': 'Very weak momentum',
            'emoji': '⚠️'
        }


def interpret_momentum_v2(score: int) -> Dict[str, any]:
    """
    V2 NEW interpretation - momentum indicates entry timing, not strength.
    
    Key insight: High momentum means the move already happened.
    You want to enter when momentum is BUILDING (5-7), not when it's EXHAUSTED (9-10).
    
    Args:
        score: Momentum score 1-10
    
    Returns:
        Dict with interpretation
    """
    if score >= MOMENTUM_EXHAUSTED_MIN:  # 9-10
        return {
            'zone': 'HOLD_ONLY',
            'action': 'HOLD existing, NO new entries',
            'description': 'Exhausted - trend extended, high risk for new entries',
            'emoji': '⏸️',
            'entry_allowed': False,
            'entry_quality_penalty': -20,  # Subtract from entry quality score
        }
    elif score >= MOMENTUM_STRONG_MIN:  # 7-8
        return {
            'zone': 'STRONG',
            'action': 'Enter with caution',
            'description': 'Strong trend - good for holding, late for entries',
            'emoji': '🔥',
            'entry_allowed': True,
            'entry_quality_penalty': -10,
        }
    elif score >= MOMENTUM_IDEAL_MIN:  # 5-7
        return {
            'zone': 'IDEAL_ENTRY',
            'action': 'IDEAL entry zone',
            'description': 'Accelerating - best time to enter',
            'emoji': '✨',
            'entry_allowed': True,
            'entry_quality_penalty': 0,  # No penalty, this is ideal
        }
    elif score >= MOMENTUM_WEAK_MAX:  # 3-4
        return {
            'zone': 'BUILDING',
            'action': 'Watch closely',
            'description': 'Momentum building - wait for confirmation',
            'emoji': '👀',
            'entry_allowed': True,
            'entry_quality_penalty': -5,
        }
    else:  # 1-2
        return {
            'zone': 'WEAK',
            'action': 'Avoid or watch for bounce',
            'description': 'Weak/negative momentum - capitulation zone',
            'emoji': '❄️',
            'entry_allowed': False,
            'entry_quality_penalty': -25,
        }


def calculate_momentum_acceleration(df: pd.DataFrame, lookback: int = 5) -> Dict[str, any]:
    """
    Calculate if momentum is accelerating or decelerating.
    
    This helps distinguish between:
    - Momentum 7 and rising (good entry)
    - Momentum 7 and falling (late entry)
    
    Args:
        df: DataFrame with OHLC data
        lookback: Days to measure acceleration
    
    Returns:
        Dict with acceleration info
    """
    if len(df) < lookback + 5:
        return {'acceleration': 0, 'direction': 'neutral', 'emoji': '➡️'}
    
    close = df['Close']
    
    # Calculate short-term and medium-term rate of change
    roc_short = ((close.iloc[-1] / close.iloc[-3]) - 1) * 100
    roc_medium = ((close.iloc[-3] / close.iloc[-lookback]) - 1) * 100
    
    # Acceleration = change in velocity
    acceleration = roc_short - roc_medium
    
    if acceleration > 2:
        return {
            'acceleration': acceleration,
            'direction': 'accelerating',
            'emoji': '🚀',
            'description': 'Momentum accelerating'
        }
    elif acceleration > 0.5:
        return {
            'acceleration': acceleration,
            'direction': 'increasing',
            'emoji': '📈',
            'description': 'Momentum increasing'
        }
    elif acceleration > -0.5:
        return {
            'acceleration': acceleration,
            'direction': 'steady',
            'emoji': '➡️',
            'description': 'Momentum steady'
        }
    elif acceleration > -2:
        return {
            'acceleration': acceleration,
            'direction': 'decreasing',
            'emoji': '📉',
            'description': 'Momentum decreasing'
        }
    else:
        return {
            'acceleration': acceleration,
            'direction': 'decelerating',
            'emoji': '🔻',
            'description': 'Momentum decelerating'
        }


def get_momentum_data(df: pd.DataFrame, psar_series: pd.Series = None, 
                      use_v2: bool = True) -> Dict[str, any]:
    """
    Get complete momentum analysis.
    
    Args:
        df: DataFrame with OHLC data
        psar_series: Optional PSAR series
        use_v2: Use v2 interpretation (default True)
    
    Returns:
        Dict with complete momentum data
    """
    score = calculate_momentum_score(df, psar_series)
    
    if use_v2:
        interpretation = interpret_momentum_v2(score)
    else:
        interpretation = interpret_momentum_v1(score)
    
    acceleration = calculate_momentum_acceleration(df)
    
    return {
        'score': score,
        'interpretation': interpretation,
        'acceleration': acceleration,
        'is_ideal_entry': MOMENTUM_IDEAL_MIN <= score <= MOMENTUM_IDEAL_MAX,
        'is_exhausted': score >= MOMENTUM_EXHAUSTED_MIN,
        'entry_allowed': interpretation.get('entry_allowed', True),
        'display': format_momentum_display(score, interpretation, acceleration)
    }


def format_momentum_display(score: int, interpretation: Dict, 
                            acceleration: Dict = None) -> str:
    """
    Format momentum for display in reports.
    
    Args:
        score: Momentum score
        interpretation: From interpret_momentum_v2
        acceleration: From calculate_momentum_acceleration
    
    Returns:
        Formatted string like "7🔥🚀" or "10⏸️🔻"
    """
    emoji = interpretation.get('emoji', '')
    accel_emoji = acceleration.get('emoji', '') if acceleration else ''
    
    return f"{score}{emoji}{accel_emoji}"


def is_momentum_favorable_for_entry(score: int, acceleration_direction: str = None) -> bool:
    """
    Quick check if momentum is favorable for a new entry.
    
    Args:
        score: Momentum score
        acceleration_direction: 'accelerating', 'increasing', 'steady', etc.
    
    Returns:
        True if favorable for new entry
    """
    # Exhausted momentum = no entry
    if score >= MOMENTUM_EXHAUSTED_MIN:
        return False
    
    # Very weak momentum = no entry (except for bounce plays)
    if score <= 2:
        return False
    
    # Ideal zone = yes
    if MOMENTUM_IDEAL_MIN <= score <= MOMENTUM_IDEAL_MAX:
        return True
    
    # Strong momentum (7-8) - only if not decelerating
    if score >= MOMENTUM_STRONG_MIN:
        if acceleration_direction in ['decelerating', 'decreasing']:
            return False
        return True
    
    # Building momentum (3-4) - only if accelerating
    if score <= 4:
        if acceleration_direction in ['accelerating', 'increasing']:
            return True
        return False
    
    return True


# =============================================================================
# STANDALONE TESTING
# =============================================================================
if __name__ == "__main__":
    print("Momentum Indicator Module Test")
    print("=" * 60)
    
    # Test interpretation differences
    print("\nV1 vs V2 Interpretation Comparison:")
    print("-" * 60)
    print(f"{'Score':<8} {'V1 Zone':<15} {'V2 Zone':<15} {'V2 Entry?':<10}")
    print("-" * 60)
    
    for score in range(1, 11):
        v1 = interpret_momentum_v1(score)
        v2 = interpret_momentum_v2(score)
        entry = "✅" if v2.get('entry_allowed', True) else "❌"
        print(f"{score:<8} {v1['zone']:<15} {v2['zone']:<15} {entry:<10}")
    
    print("\n" + "=" * 60)
    print("Live Stock Test:")
    print("-" * 60)
    
    import yfinance as yf
    
    test_tickers = ["AAPL", "NVDA", "MSTR", "META"]
    
    for ticker in test_tickers:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="6mo")
            
            if len(df) > 0:
                data = get_momentum_data(df, use_v2=True)
                
                print(f"\n{ticker}:")
                print(f"  Score: {data['score']}")
                print(f"  Zone: {data['interpretation']['zone']}")
                print(f"  Action: {data['interpretation']['action']}")
                print(f"  Acceleration: {data['acceleration']['direction']} {data['acceleration']['emoji']}")
                print(f"  Entry Allowed: {'✅' if data['entry_allowed'] else '❌'}")
                print(f"  Display: {data['display']}")
        except Exception as e:
            print(f"\n{ticker}: Error - {e}")

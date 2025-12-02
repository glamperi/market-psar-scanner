"""
ATR (Average True Range) Indicator
==================================
Measures volatility and overbought/oversold conditions.

V2 ROLE: OVERBOUGHT/OVERSOLD FILTER
- ATR > +3% = Overbought (price extended above EMA)
- ATR < -3% = Oversold (price extended below EMA)
- Used to filter entries and identify extreme conditions

The ATR% in reports shows how far price is from its EMA
relative to the stock's typical volatility.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional

try:
    from utils.config import (
        ATR_PERIOD, ATR_EMA_PERIOD,
        ATR_OVERBOUGHT, ATR_OVERSOLD,
        ATR_EXTREME_OVERBOUGHT, ATR_EXTREME_OVERSOLD
    )
except ImportError:
    ATR_PERIOD = 14
    ATR_EMA_PERIOD = 8
    ATR_OVERBOUGHT = 3.0
    ATR_OVERSOLD = -3.0
    ATR_EXTREME_OVERBOUGHT = 5.0
    ATR_EXTREME_OVERSOLD = -5.0


def calculate_true_range(df: pd.DataFrame) -> pd.Series:
    """
    Calculate True Range.
    
    TR = max(High-Low, abs(High-PrevClose), abs(Low-PrevClose))
    """
    high = df['High']
    low = df['Low']
    close = df['Close']
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = abs(high - prev_close)
    tr3 = abs(low - prev_close)
    
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range


def calculate_atr(df: pd.DataFrame, period: int = None) -> pd.Series:
    """
    Calculate Average True Range.
    
    Args:
        df: DataFrame with OHLC data
        period: ATR period (default from config)
    
    Returns:
        Series of ATR values
    """
    if period is None:
        period = ATR_PERIOD
    
    true_range = calculate_true_range(df)
    atr = true_range.ewm(span=period, adjust=False).mean()
    return atr


def calculate_atr_percent(df: pd.DataFrame, ema_period: int = None) -> float:
    """
    Calculate how far price is from EMA as a percentage of ATR.
    
    This is the "ATR%" shown in reports.
    Positive = price above EMA (extended up)
    Negative = price below EMA (extended down)
    
    Args:
        df: DataFrame with OHLC data
        ema_period: EMA period to compare against
    
    Returns:
        ATR percentage (-10 to +10 typical range)
    """
    if ema_period is None:
        ema_period = ATR_EMA_PERIOD
    
    if len(df) < max(ATR_PERIOD, ema_period) + 5:
        return 0.0
    
    close = df['Close']
    current_price = close.iloc[-1]
    
    # Calculate EMA
    ema = close.ewm(span=ema_period, adjust=False).mean()
    current_ema = ema.iloc[-1]
    
    # Calculate ATR
    atr = calculate_atr(df)
    current_atr = atr.iloc[-1]
    
    if current_atr == 0:
        return 0.0
    
    # Distance from EMA as multiple of ATR
    distance = current_price - current_ema
    atr_percent = (distance / current_atr) * 100
    
    # Normalize to roughly -10 to +10 range
    # (distance / ATR gives us ATR multiples, * 100 / ~30 normalizes)
    normalized = (distance / current_price) * 100
    
    return normalized


def get_atr_status(atr_percent: float) -> Dict[str, any]:
    """
    Get overbought/oversold status based on ATR%.
    
    Args:
        atr_percent: From calculate_atr_percent()
    
    Returns:
        Dict with status info
    """
    if atr_percent >= ATR_EXTREME_OVERBOUGHT:
        return {
            'status': 'extreme_overbought',
            'emoji': '🔥🔥',
            'description': f'Extremely overbought (+{atr_percent:.1f}%)',
            'entry_penalty': -25,
            'action': 'NO ENTRY - wait for pullback'
        }
    elif atr_percent >= ATR_OVERBOUGHT:
        return {
            'status': 'overbought',
            'emoji': '🔥',
            'description': f'Overbought (+{atr_percent:.1f}%)',
            'entry_penalty': -15,
            'action': 'Caution - extended above average'
        }
    elif atr_percent <= ATR_EXTREME_OVERSOLD:
        return {
            'status': 'extreme_oversold',
            'emoji': '❄️❄️',
            'description': f'Extremely oversold ({atr_percent:.1f}%)',
            'entry_penalty': -10,  # Less penalty - could be bounce opportunity
            'action': 'Watch for bounce - capitulation zone'
        }
    elif atr_percent <= ATR_OVERSOLD:
        return {
            'status': 'oversold',
            'emoji': '❄️',
            'description': f'Oversold ({atr_percent:.1f}%)',
            'entry_penalty': -5,
            'action': 'Potential support - watch for reversal'
        }
    else:
        return {
            'status': 'neutral',
            'emoji': '',
            'description': f'Neutral ({atr_percent:+.1f}%)',
            'entry_penalty': 0,
            'action': 'Normal range'
        }


def get_atr_data(df: pd.DataFrame) -> Dict[str, any]:
    """
    Get complete ATR analysis.
    
    Args:
        df: DataFrame with OHLC data
    
    Returns:
        Dict with complete ATR data
    """
    if len(df) < 20:
        return {'error': 'Insufficient data', 'atr_percent': 0, 'status': None}
    
    atr = calculate_atr(df)
    atr_percent = calculate_atr_percent(df)
    status = get_atr_status(atr_percent)
    
    return {
        'atr': atr.iloc[-1],
        'atr_percent': atr_percent,
        'status': status['status'],
        'emoji': status['emoji'],
        'description': status['description'],
        'entry_penalty': status['entry_penalty'],
        'action': status['action'],
        'display': format_atr_display(atr_percent, status)
    }


def format_atr_display(atr_percent: float, status: Dict) -> str:
    """Format ATR% for display."""
    sign = '+' if atr_percent >= 0 else ''
    emoji = status.get('emoji', '')
    return f"{sign}{atr_percent:.0f}%{emoji}"


# =============================================================================
# STANDALONE TESTING
# =============================================================================
if __name__ == "__main__":
    print("ATR Indicator Module Test")
    print("=" * 50)
    
    import yfinance as yf
    
    test_tickers = ["AAPL", "NVDA", "MSTR", "META"]
    
    for ticker in test_tickers:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="6mo")
            
            if len(df) > 0:
                data = get_atr_data(df)
                print(f"\n{ticker}:")
                print(f"  ATR: ${data['atr']:.2f}")
                print(f"  ATR%: {data['display']}")
                print(f"  Status: {data['status']}")
                print(f"  Action: {data['action']}")
        except Exception as e:
            print(f"\n{ticker}: Error - {e}")

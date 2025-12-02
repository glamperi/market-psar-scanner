"""
OBV (On-Balance Volume) Indicator
=================================
Measures buying vs selling pressure through volume flow.

V2 ROLE: CONFIRMATION SIGNAL
OBV confirms or warns against PRSI signals:
- PRSI Bullish + OBV Green = Strong confirmation ✅
- PRSI Bullish + OBV Red = Warning - divergence ⚠️
- PRSI Bearish + OBV Green = Potential bounce setup ❄️
- PRSI Bearish + OBV Red = Strong confirmation of downtrend 🔴

Key Insight from Analysis:
Your "SELL" stocks (NVDA, MSTR) had GREEN OBV = accumulation on dip = bounce likely
Your "STRONG BUY" stocks (META) had RED OBV = distribution at top = pullback likely
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple

# Import config - handle both direct run and module import
try:
    from utils.config import OBV_MA_PERIOD, OBV_LOOKBACK
except ImportError:
    OBV_MA_PERIOD = 20
    OBV_LOOKBACK = 5


def calculate_obv(df: pd.DataFrame) -> pd.Series:
    """
    Calculate On-Balance Volume.
    
    OBV adds volume on up days and subtracts on down days.
    Rising OBV = accumulation (buying pressure)
    Falling OBV = distribution (selling pressure)
    
    Args:
        df: DataFrame with 'Close' and 'Volume' columns
    
    Returns:
        Series of OBV values
    """
    close = df['Close']
    volume = df['Volume']
    
    # Calculate price direction
    direction = np.sign(close.diff())
    
    # First value has no direction, set to 0
    direction.iloc[0] = 0
    
    # OBV = cumulative sum of signed volume
    obv = (volume * direction).cumsum()
    
    return obv


def calculate_obv_ma(df: pd.DataFrame, period: int = None) -> pd.Series:
    """
    Calculate moving average of OBV for trend smoothing.
    
    Args:
        df: DataFrame with OHLC and Volume
        period: MA period (default from config)
    
    Returns:
        Series of OBV moving average
    """
    if period is None:
        period = OBV_MA_PERIOD
    
    obv = calculate_obv(df)
    return obv.rolling(window=period).mean()


def get_obv_trend(df: pd.DataFrame, lookback: int = None) -> Dict[str, any]:
    """
    Determine OBV trend direction.
    
    Args:
        df: DataFrame with OHLC and Volume
        lookback: Days to analyze (default from config)
    
    Returns:
        Dict with trend info
    """
    if lookback is None:
        lookback = OBV_LOOKBACK
    
    if len(df) < lookback + 5:
        return {
            'trend': 'neutral',
            'is_bullish': None,
            'emoji': '⚪',
            'color': 'gray'
        }
    
    obv = calculate_obv(df)
    obv_ma = calculate_obv_ma(df)
    
    current_obv = obv.iloc[-1]
    current_ma = obv_ma.iloc[-1]
    
    # Check short-term trend
    obv_start = obv.iloc[-lookback]
    obv_change = current_obv - obv_start
    obv_change_pct = (obv_change / abs(obv_start)) * 100 if obv_start != 0 else 0
    
    # Determine trend based on:
    # 1. OBV above/below its MA
    # 2. Recent direction of OBV
    obv_above_ma = current_obv > current_ma
    obv_rising = obv_change > 0
    
    if obv_above_ma and obv_rising:
        return {
            'trend': 'strong_accumulation',
            'is_bullish': True,
            'emoji': '🟢',
            'color': 'green',
            'description': 'Strong buying pressure - accumulation',
            'change_pct': obv_change_pct
        }
    elif obv_rising:
        return {
            'trend': 'accumulation',
            'is_bullish': True,
            'emoji': '🟢',
            'color': 'green',
            'description': 'Buying pressure increasing',
            'change_pct': obv_change_pct
        }
    elif not obv_above_ma and not obv_rising:
        return {
            'trend': 'strong_distribution',
            'is_bullish': False,
            'emoji': '🔴',
            'color': 'red',
            'description': 'Strong selling pressure - distribution',
            'change_pct': obv_change_pct
        }
    elif not obv_rising:
        return {
            'trend': 'distribution',
            'is_bullish': False,
            'emoji': '🔴',
            'color': 'red',
            'description': 'Selling pressure increasing',
            'change_pct': obv_change_pct
        }
    else:
        return {
            'trend': 'neutral',
            'is_bullish': None,
            'emoji': '⚪',
            'color': 'gray',
            'description': 'Mixed volume signals',
            'change_pct': obv_change_pct
        }


def detect_obv_divergence(df: pd.DataFrame, lookback: int = 20) -> Dict[str, any]:
    """
    Detect divergence between price and OBV.
    
    Bullish divergence: Price falling but OBV rising (accumulation on dip)
    Bearish divergence: Price rising but OBV falling (distribution at top)
    
    THIS IS THE KEY SIGNAL that caught NVDA/MSTR vs META!
    
    Args:
        df: DataFrame with OHLC and Volume
        lookback: Days to analyze
    
    Returns:
        Dict with divergence info or None
    """
    if len(df) < lookback + 5:
        return None
    
    close = df['Close']
    obv = calculate_obv(df)
    
    # Get price and OBV changes over lookback
    price_start = close.iloc[-lookback]
    price_end = close.iloc[-1]
    price_change = ((price_end / price_start) - 1) * 100
    
    obv_start = obv.iloc[-lookback]
    obv_end = obv.iloc[-1]
    obv_change = ((obv_end - obv_start) / abs(obv_start)) * 100 if obv_start != 0 else 0
    
    # Bullish divergence: Price down, OBV up
    if price_change < -3 and obv_change > 5:
        return {
            'type': 'bullish',
            'strength': min(5, int(abs(obv_change) / 5)),
            'description': f'Bullish divergence: Price {price_change:.1f}% but OBV +{obv_change:.1f}%',
            'emoji': '📈',
            'action': 'Accumulation on dip - watch for bounce'
        }
    
    # Bearish divergence: Price up, OBV down
    if price_change > 3 and obv_change < -5:
        return {
            'type': 'bearish',
            'strength': min(5, int(abs(obv_change) / 5)),
            'description': f'Bearish divergence: Price +{price_change:.1f}% but OBV {obv_change:.1f}%',
            'emoji': '📉',
            'action': 'Distribution at top - consider exit'
        }
    
    return None


def get_obv_confirmation(obv_is_bullish: bool, prsi_is_bullish: bool, 
                         price_psar_bullish: bool) -> Dict[str, any]:
    """
    Get OBV confirmation status relative to other signals.
    
    Args:
        obv_is_bullish: True if OBV trend is bullish
        prsi_is_bullish: True if PRSI is bullish
        price_psar_bullish: True if price is above PSAR
    
    Returns:
        Dict with confirmation analysis
    """
    # All aligned bullish
    if obv_is_bullish and prsi_is_bullish and price_psar_bullish:
        return {
            'status': 'confirmed',
            'strength': 'strong',
            'emoji': '✅',
            'description': 'All signals aligned bullish - high confidence',
            'score_bonus': 15
        }
    
    # All aligned bearish
    if not obv_is_bullish and not prsi_is_bullish and not price_psar_bullish:
        return {
            'status': 'confirmed',
            'strength': 'strong',
            'emoji': '🔴',
            'description': 'All signals aligned bearish - avoid',
            'score_bonus': 0
        }
    
    # OBV bullish but price/PRSI bearish = accumulation on dip
    if obv_is_bullish and (not prsi_is_bullish or not price_psar_bullish):
        return {
            'status': 'divergence',
            'strength': 'potential_bounce',
            'emoji': '❄️',
            'description': 'OBV shows accumulation despite price weakness - watch for bounce',
            'score_bonus': 5
        }
    
    # OBV bearish but price/PRSI bullish = distribution at top
    if not obv_is_bullish and (prsi_is_bullish or price_psar_bullish):
        return {
            'status': 'divergence',
            'strength': 'warning',
            'emoji': '⚠️',
            'description': 'OBV shows distribution despite price strength - caution',
            'score_bonus': -10
        }
    
    # Mixed
    return {
        'status': 'mixed',
        'strength': 'neutral',
        'emoji': '⚪',
        'description': 'Mixed signals - wait for clarity',
        'score_bonus': 0
    }


def get_obv_data(df: pd.DataFrame) -> Dict[str, any]:
    """
    Get complete OBV analysis.
    
    Args:
        df: DataFrame with OHLC and Volume
    
    Returns:
        Dict with complete OBV data
    """
    if len(df) < 10:
        return {
            'error': 'Insufficient data',
            'trend': None,
            'is_bullish': None,
            'emoji': '❓'
        }
    
    obv_series = calculate_obv(df)
    obv_ma = calculate_obv_ma(df)
    trend = get_obv_trend(df)
    divergence = detect_obv_divergence(df)
    
    return {
        'obv': obv_series.iloc[-1],
        'obv_ma': obv_ma.iloc[-1],
        'trend': trend['trend'],
        'is_bullish': trend['is_bullish'],
        'emoji': trend['emoji'],
        'color': trend['color'],
        'description': trend['description'],
        'divergence': divergence,
        'obv_series': obv_series,
        'display': format_obv_display(trend, divergence)
    }


def format_obv_display(trend: Dict, divergence: Dict = None) -> str:
    """
    Format OBV for display in reports.
    
    Args:
        trend: From get_obv_trend()
        divergence: From detect_obv_divergence()
    
    Returns:
        Formatted string like "🟢" or "🔴 📉"
    """
    display = trend['emoji']
    
    if divergence:
        display += f" {divergence['emoji']}"
    
    return display


def is_obv_favorable(df: pd.DataFrame, for_long: bool = True) -> bool:
    """
    Quick check if OBV is favorable for a trade direction.
    
    Args:
        df: DataFrame with OHLC and Volume
        for_long: True for long trades, False for shorts
    
    Returns:
        True if OBV supports the trade direction
    """
    trend = get_obv_trend(df)
    
    if for_long:
        return trend['is_bullish'] == True
    else:
        return trend['is_bullish'] == False


# =============================================================================
# STANDALONE TESTING
# =============================================================================
if __name__ == "__main__":
    print("OBV (On-Balance Volume) Module Test")
    print("=" * 60)
    
    import yfinance as yf
    
    # Test the stocks from the analysis
    test_cases = [
        ("NVDA", "Was SELL with green OBV - should show accumulation"),
        ("MSTR", "Was SELL with green OBV - should show accumulation"),
        ("META", "Was STRONG_BUY with red OBV - should show distribution"),
        ("AAPL", "Control stock"),
    ]
    
    for ticker, expected in test_cases:
        print(f"\n{ticker} - {expected}")
        print("-" * 50)
        
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="6mo")
            
            if len(df) > 0:
                data = get_obv_data(df)
                
                print(f"  OBV Trend: {data['trend']} {data['emoji']}")
                print(f"  Is Bullish: {data['is_bullish']}")
                print(f"  Description: {data['description']}")
                
                if data['divergence']:
                    div = data['divergence']
                    print(f"  Divergence: {div['type']} {div['emoji']}")
                    print(f"    {div['description']}")
                    print(f"    Action: {div['action']}")
                else:
                    print(f"  Divergence: None detected")
                
                # Test confirmation
                # Simulate PRSI and Price PSAR being bearish for SELL stocks
                if ticker in ['NVDA', 'MSTR']:
                    confirm = get_obv_confirmation(
                        obv_is_bullish=data['is_bullish'],
                        prsi_is_bullish=False,  # These were SELL
                        price_psar_bullish=False
                    )
                else:
                    confirm = get_obv_confirmation(
                        obv_is_bullish=data['is_bullish'],
                        prsi_is_bullish=True,  # These were BUY
                        price_psar_bullish=True
                    )
                
                print(f"  Confirmation: {confirm['emoji']} {confirm['status']}")
                print(f"    {confirm['description']}")
                
        except Exception as e:
            print(f"  Error: {e}")

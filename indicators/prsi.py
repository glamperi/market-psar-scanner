"""
PRSI - PSAR on RSI (Parabolic SAR applied to RSI)
=================================================
THE PRIMARY SIGNAL IN V2

Why PRSI is better than Price PSAR as the primary signal:
1. RSI leads price - RSI often turns 1-3 days before price does
2. Catches turns earlier - PRSI flips before Price PSAR
3. Avoids exhaustion buys - Won't buy Momentum 10 if PRSI rolling over
4. Avoids capitulation shorts - Won't short if PRSI about to flip bullish

Signal Interpretation:
- PRSI Bullish (↗️) + Price PSAR Positive = Confirmed uptrend
- PRSI Bullish (↗️) + Price PSAR Negative = EARLY BUY (catching the turn)
- PRSI Bearish (↘️) + Price PSAR Positive = WARNING (momentum fading)
- PRSI Bearish (↘️) + Price PSAR Negative = Confirmed downtrend
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple

# Import config - handle both direct run and module import
try:
    from utils.config import (
        RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD,
        PSAR_AF, PSAR_MAX_AF
    )
except ImportError:
    RSI_PERIOD = 14
    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30
    PSAR_AF = 0.02
    PSAR_MAX_AF = 0.2


def calculate_rsi(df: pd.DataFrame, period: int = None) -> pd.Series:
    """
    Calculate RSI (Relative Strength Index).
    
    Args:
        df: DataFrame with 'Close' column
        period: RSI period (default from config)
    
    Returns:
        Series of RSI values (0-100)
    """
    if period is None:
        period = RSI_PERIOD
    
    close = df['Close']
    delta = close.diff()
    
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    
    # Use exponential moving average for smoothing
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_psar_on_series(series: pd.Series, af: float = None, max_af: float = None) -> Tuple[pd.Series, pd.Series]:
    """
    Calculate Parabolic SAR on any series (RSI, price, etc).
    
    Args:
        series: The data series to calculate PSAR on
        af: Acceleration factor
        max_af: Maximum acceleration factor
    
    Returns:
        Tuple of (psar_series, trend_series)
        trend_series: 1 = bullish, -1 = bearish
    """
    if af is None:
        af = PSAR_AF
    if max_af is None:
        max_af = PSAR_MAX_AF
    
    length = len(series)
    psar = pd.Series(index=series.index, dtype=float)
    trend = pd.Series(index=series.index, dtype=int)
    
    if length < 2:
        return psar, trend
    
    # Drop NaN values and get valid data
    valid_series = series.dropna()
    if len(valid_series) < 2:
        return psar, trend
    
    # Find first valid index
    first_valid_idx = valid_series.index[0]
    first_valid_pos = series.index.get_loc(first_valid_idx)
    
    # Initialize at first valid position
    if valid_series.iloc[1] > valid_series.iloc[0]:
        trend.iloc[first_valid_pos] = 1  # Start bullish
        psar.iloc[first_valid_pos] = valid_series.iloc[0] - 5  # Start below
        ep = valid_series.iloc[0]  # Extreme point
    else:
        trend.iloc[first_valid_pos] = -1  # Start bearish
        psar.iloc[first_valid_pos] = valid_series.iloc[0] + 5  # Start above
        ep = valid_series.iloc[0]
    
    current_af = af
    
    # Iterate from first valid position + 1
    for i in range(first_valid_pos + 1, length):
        # Skip if current value is NaN
        if pd.isna(series.iloc[i]):
            continue
            
        prev_psar = psar.iloc[i-1]
        prev_trend = trend.iloc[i-1]
        
        # Handle if prev values are NaN (shouldn't happen but be safe)
        if pd.isna(prev_psar) or pd.isna(prev_trend):
            # Find last valid psar and trend
            for j in range(i-1, -1, -1):
                if not pd.isna(psar.iloc[j]) and not pd.isna(trend.iloc[j]):
                    prev_psar = psar.iloc[j]
                    prev_trend = trend.iloc[j]
                    break
            else:
                continue  # No valid previous data
        
        if prev_trend == 1:  # Was bullish
            # Calculate new PSAR
            new_psar = prev_psar + current_af * (ep - prev_psar)
            
            # PSAR cannot be above prior values for bullish trend
            if not pd.isna(series.iloc[i-1]):
                new_psar = min(new_psar, series.iloc[i-1])
            if i >= 2 and not pd.isna(series.iloc[i-2]):
                new_psar = min(new_psar, series.iloc[i-2])
            
            # Check for reversal
            if series.iloc[i] < new_psar:
                # Flip to bearish
                trend.iloc[i] = -1
                psar.iloc[i] = ep
                ep = series.iloc[i]
                current_af = af
            else:
                # Continue bullish
                trend.iloc[i] = 1
                psar.iloc[i] = new_psar
                
                if series.iloc[i] > ep:
                    ep = series.iloc[i]
                    current_af = min(current_af + af, max_af)
        
        else:  # Was bearish
            # Calculate new PSAR
            new_psar = prev_psar + current_af * (ep - prev_psar)
            
            # PSAR cannot be below prior values for bearish trend
            if not pd.isna(series.iloc[i-1]):
                new_psar = max(new_psar, series.iloc[i-1])
            if i >= 2 and not pd.isna(series.iloc[i-2]):
                new_psar = max(new_psar, series.iloc[i-2])
            
            # Check for reversal
            if series.iloc[i] > new_psar:
                # Flip to bullish
                trend.iloc[i] = 1
                psar.iloc[i] = ep
                ep = series.iloc[i]
                current_af = af
            else:
                # Continue bearish
                trend.iloc[i] = -1
                psar.iloc[i] = new_psar
                
                if series.iloc[i] < ep:
                    ep = series.iloc[i]
                    current_af = min(current_af + af, max_af)
    
    return psar, trend


def calculate_prsi(df: pd.DataFrame, rsi_period: int = None, af: float = None) -> Dict[str, any]:
    """
    Calculate PRSI (PSAR applied to RSI).
    
    This is the PRIMARY SIGNAL in v2.
    
    Args:
        df: DataFrame with OHLC data
        rsi_period: RSI calculation period
        af: PSAR acceleration factor
    
    Returns:
        Dict with:
        - rsi: current RSI value
        - prsi_psar: current PSAR value on RSI
        - is_bullish: True if RSI > PRSI PSAR
        - trend_direction: 'up' or 'down'
        - days_since_flip: days since last trend change
        - rsi_series: full RSI series
        - prsi_series: full PSAR-on-RSI series
        - trend_series: full trend series (1/-1)
    """
    if len(df) < 20:
        return None
    
    # Calculate RSI
    rsi = calculate_rsi(df, rsi_period)
    
    # Calculate PSAR on RSI
    prsi_psar, trend = calculate_psar_on_series(rsi, af)
    
    # Current values
    current_rsi = rsi.iloc[-1]
    current_prsi = prsi_psar.iloc[-1]
    current_trend = trend.iloc[-1]
    
    is_bullish = current_trend == 1
    
    # Count days since last flip
    days_since_flip = 1
    for i in range(len(trend) - 2, -1, -1):
        if trend.iloc[i] == current_trend:
            days_since_flip += 1
        else:
            break
    
    return {
        'rsi': current_rsi,
        'prsi_psar': current_prsi,
        'is_bullish': is_bullish,
        'trend_direction': 'up' if is_bullish else 'down',
        'days_since_flip': days_since_flip,
        'rsi_series': rsi,
        'prsi_series': prsi_psar,
        'trend_series': trend
    }


def get_prsi_signal(prsi_data: Dict, price_psar_trend: str) -> Dict[str, any]:
    """
    Generate trading signal based on PRSI and Price PSAR combination.
    
    Args:
        prsi_data: Output from calculate_prsi()
        price_psar_trend: 'bullish' or 'bearish' from price PSAR
    
    Returns:
        Dict with:
        - signal: EARLY_BUY, CONFIRMED_BUY, WARNING, CONFIRMED_SELL, etc.
        - strength: 1-5 rating
        - description: explanation
        - emoji: display emoji
    """
    if prsi_data is None:
        return {
            'signal': 'UNKNOWN',
            'strength': 0,
            'description': 'Insufficient data',
            'emoji': '❓'
        }
    
    prsi_bullish = prsi_data['is_bullish']
    days = prsi_data['days_since_flip']
    rsi = prsi_data['rsi']
    
    # PRSI Bullish + Price PSAR Bullish = Confirmed Uptrend
    if prsi_bullish and price_psar_trend == 'bullish':
        strength = min(5, 3 + (days // 3))  # Stronger with more days
        return {
            'signal': 'CONFIRMED_BUY',
            'strength': strength,
            'description': f'Confirmed uptrend ({days}d). RSI and Price both bullish.',
            'emoji': '✅'
        }
    
    # PRSI Bullish + Price PSAR Bearish = EARLY BUY (the key signal!)
    elif prsi_bullish and price_psar_trend == 'bearish':
        # This is the EARLY ENTRY signal - momentum turning before price
        strength = 4 if days <= 3 else 3  # Stronger if recent flip
        return {
            'signal': 'EARLY_BUY',
            'strength': strength,
            'description': f'EARLY BUY - RSI turned bullish {days}d ago, price catching up.',
            'emoji': '⚡'
        }
    
    # PRSI Bearish + Price PSAR Bullish = WARNING (momentum fading)
    elif not prsi_bullish and price_psar_trend == 'bullish':
        strength = 2 if days <= 3 else 3  # More concerning with more days
        return {
            'signal': 'WARNING',
            'strength': strength,
            'description': f'WARNING - RSI turned bearish {days}d ago, price may follow.',
            'emoji': '⚠️'
        }
    
    # PRSI Bearish + Price PSAR Bearish = Confirmed Downtrend
    else:
        # Check if oversold - potential bounce
        if rsi < RSI_OVERSOLD:
            return {
                'signal': 'OVERSOLD_WATCH',
                'strength': 2,
                'description': f'Oversold (RSI {rsi:.0f}). Watch for PRSI flip for bounce.',
                'emoji': '❄️'
            }
        else:
            strength = min(5, 3 + (days // 3))
            return {
                'signal': 'CONFIRMED_SELL',
                'strength': strength,
                'description': f'Confirmed downtrend ({days}d). RSI and Price both bearish.',
                'emoji': '🔴'
            }


def get_prsi_trend_emoji(is_bullish: bool) -> str:
    """Get arrow emoji for PRSI trend direction."""
    return '↗️' if is_bullish else '↘️'


def format_prsi_display(prsi_data: Dict) -> str:
    """
    Format PRSI data for display in reports.
    
    Args:
        prsi_data: Output from calculate_prsi()
    
    Returns:
        Formatted string like "RSI:55 ↗️ (3d)"
    """
    if prsi_data is None:
        return "N/A"
    
    rsi = prsi_data['rsi']
    trend = get_prsi_trend_emoji(prsi_data['is_bullish'])
    days = prsi_data['days_since_flip']
    
    return f"RSI:{rsi:.0f} {trend} ({days}d)"


def detect_prsi_divergence(df: pd.DataFrame, lookback: int = 10) -> Dict[str, any]:
    """
    Detect divergence between price and PRSI.
    
    Bullish divergence: Price making lower lows, RSI making higher lows
    Bearish divergence: Price making higher highs, RSI making lower highs
    
    Args:
        df: DataFrame with OHLC data
        lookback: Number of days to look back
    
    Returns:
        Dict with divergence info or None if no divergence
    """
    if len(df) < lookback + 5:
        return None
    
    rsi = calculate_rsi(df)
    
    # Get recent lows and highs
    recent_price = df['Close'].iloc[-lookback:]
    recent_rsi = rsi.iloc[-lookback:]
    
    # Find local minima and maxima
    price_min_idx = recent_price.idxmin()
    price_max_idx = recent_price.idxmax()
    rsi_min_idx = recent_rsi.idxmin()
    rsi_max_idx = recent_rsi.idxmax()
    
    current_price = df['Close'].iloc[-1]
    current_rsi = rsi.iloc[-1]
    
    # Check for bullish divergence
    # Price at or near recent low, but RSI higher than its low
    price_near_low = current_price <= recent_price.min() * 1.02
    rsi_above_low = current_rsi > recent_rsi.min() + 5
    
    if price_near_low and rsi_above_low:
        return {
            'type': 'bullish',
            'description': 'Bullish divergence: Price at low but RSI shows strength',
            'emoji': '📈'
        }
    
    # Check for bearish divergence
    # Price at or near recent high, but RSI lower than its high
    price_near_high = current_price >= recent_price.max() * 0.98
    rsi_below_high = current_rsi < recent_rsi.max() - 5
    
    if price_near_high and rsi_below_high:
        return {
            'type': 'bearish',
            'description': 'Bearish divergence: Price at high but RSI shows weakness',
            'emoji': '📉'
        }
    
    return None


def get_full_prsi_analysis(df: pd.DataFrame, price_psar_trend: str = None, price_psar_gap: float = None) -> Dict[str, any]:
    """
    Complete PRSI analysis including signal, divergence, and recommendations.
    
    Args:
        df: DataFrame with OHLC data
        price_psar_trend: 'bullish' or 'bearish' from price PSAR
        price_psar_gap: Gap percentage from price PSAR
    
    Returns:
        Comprehensive analysis dict
    """
    prsi_data = calculate_prsi(df)
    
    if prsi_data is None:
        return {'error': 'Insufficient data for PRSI calculation'}
    
    # Get signal if price PSAR info provided
    signal = None
    if price_psar_trend:
        signal = get_prsi_signal(prsi_data, price_psar_trend)
    
    # Check for divergence
    divergence = detect_prsi_divergence(df)
    
    # Determine RSI zone
    rsi = prsi_data['rsi']
    if rsi >= RSI_OVERBOUGHT:
        rsi_zone = 'overbought'
    elif rsi <= RSI_OVERSOLD:
        rsi_zone = 'oversold'
    elif rsi >= 50:
        rsi_zone = 'bullish_neutral'
    else:
        rsi_zone = 'bearish_neutral'
    
    return {
        'prsi_data': prsi_data,
        'signal': signal,
        'divergence': divergence,
        'rsi_zone': rsi_zone,
        'is_bullish': prsi_data['is_bullish'],
        'days_since_flip': prsi_data['days_since_flip'],
        'display': format_prsi_display(prsi_data),
        'trend_emoji': get_prsi_trend_emoji(prsi_data['is_bullish'])
    }


# =============================================================================
# STANDALONE TESTING
# =============================================================================
if __name__ == "__main__":
    print("PRSI (PSAR on RSI) Module Test")
    print("=" * 60)
    
    import yfinance as yf
    
    # Test with a few tickers
    test_tickers = ["AAPL", "NVDA", "MSTR"]
    
    for ticker in test_tickers:
        print(f"\n{ticker}")
        print("-" * 40)
        
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="6mo")
            
            if len(df) > 0:
                # Get PRSI analysis
                prsi_data = calculate_prsi(df)
                
                # Simulate price PSAR (just check if close > open for simplicity)
                price_trend = 'bullish' if df['Close'].iloc[-1] > df['Close'].iloc[-5] else 'bearish'
                
                signal = get_prsi_signal(prsi_data, price_trend)
                divergence = detect_prsi_divergence(df)
                
                print(f"  RSI: {prsi_data['rsi']:.1f}")
                print(f"  PRSI Trend: {get_prsi_trend_emoji(prsi_data['is_bullish'])} ({prsi_data['days_since_flip']}d)")
                print(f"  Price Trend: {price_trend}")
                print(f"  Signal: {signal['emoji']} {signal['signal']}")
                print(f"  Description: {signal['description']}")
                
                if divergence:
                    print(f"  Divergence: {divergence['emoji']} {divergence['type']}")
            else:
                print("  No data")
        except Exception as e:
            print(f"  Error: {e}")

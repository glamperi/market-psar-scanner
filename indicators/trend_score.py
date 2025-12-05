"""
Trend Score Indicator
=====================
Combines multiple trend indicators into a single score (0-100).

Components:
- MACD (30 pts): MACD above signal, histogram rising
- Coppock (20 pts): Coppock curve rising from bottom
- ADX (25 pts): ADX > 25 = strong trend
- MA Alignment (25 pts): Price > EMA8 > EMA21 > SMA50

V2 ROLE: STOCK SELECTION
High Trend Score = Good stock to trade (strong trend)
Used to SELECT which stocks to trade, not WHEN to enter.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional

try:
    from utils.config import (
        MACD_FAST, MACD_SLOW, MACD_SIGNAL,
        COPPOCK_WMA, COPPOCK_ROC1, COPPOCK_ROC2,
        ADX_PERIOD, ADX_STRONG_TREND, ADX_WEAK_TREND,
        EMA_FAST, EMA_MEDIUM, SMA_SLOW,
        TREND_SCORE_STRONG, TREND_SCORE_MIN, TREND_SCORE_WEIGHTS
    )
except ImportError:
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9
    COPPOCK_WMA = 10
    COPPOCK_ROC1 = 14
    COPPOCK_ROC2 = 11
    ADX_PERIOD = 14
    ADX_STRONG_TREND = 25
    ADX_WEAK_TREND = 20
    EMA_FAST = 8
    EMA_MEDIUM = 21
    SMA_SLOW = 50
    TREND_SCORE_STRONG = 70
    TREND_SCORE_MIN = 50
    TREND_SCORE_WEIGHTS = {'macd': 30, 'coppock': 20, 'adx': 25, 'ma_alignment': 25}


def calculate_macd(df: pd.DataFrame) -> Dict[str, pd.Series]:
    """Calculate MACD, Signal line, and Histogram."""
    close = df['Close']
    
    ema_fast = close.ewm(span=MACD_FAST, adjust=False).mean()
    ema_slow = close.ewm(span=MACD_SLOW, adjust=False).mean()
    
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=MACD_SIGNAL, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return {
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    }


def calculate_macd_score(df: pd.DataFrame, max_points: int = 30) -> Dict[str, any]:
    """
    Calculate MACD component of trend score.
    
    Scoring:
    - MACD > Signal: 15 pts
    - Histogram positive: 10 pts
    - Histogram rising: 5 pts
    """
    macd_data = calculate_macd(df)
    macd = macd_data['macd'].iloc[-1]
    signal = macd_data['signal'].iloc[-1]
    hist = macd_data['histogram'].iloc[-1]
    hist_prev = macd_data['histogram'].iloc[-2] if len(df) > 1 else 0
    
    score = 0
    details = []
    
    if macd > signal:
        score += 15
        details.append("MACD > Signal (+15)")
    
    if hist > 0:
        score += 10
        details.append("Histogram positive (+10)")
    
    if hist > hist_prev:
        score += 5
        details.append("Histogram rising (+5)")
    
    return {
        'score': min(score, max_points),
        'max': max_points,
        'details': details,
        'macd': macd,
        'signal': signal,
        'histogram': hist
    }


def calculate_rsi_for_trend(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate RSI for trend score component."""
    close = df['Close']
    delta = close.diff()
    
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_rsi_zone_score(df: pd.DataFrame, max_points: int = 20) -> Dict[str, any]:
    """
    Calculate RSI Zone component of trend score.
    
    Replaces Coppock. In a bull trend, RSI tends to stay between 40-90.
    RSI < 50 suggests the trend is weak or broken.
    
    Scoring:
    - RSI > 60: 20 pts (strong bullish zone)
    - RSI > 50: 15 pts (bullish zone)
    - RSI > 40: 10 pts (neutral, trend may be weakening)
    - RSI <= 40: 0 pts (bearish zone, trend broken)
    """
    rsi = calculate_rsi_for_trend(df)
    current = rsi.iloc[-1]
    
    if current > 60:
        score = 20
        zone = "Strong bullish zone"
    elif current > 50:
        score = 15
        zone = "Bullish zone"
    elif current > 40:
        score = 10
        zone = "Neutral zone"
    else:
        score = 0
        zone = "Bearish zone"
    
    return {
        'score': min(score, max_points),
        'max': max_points,
        'details': [f"RSI {current:.1f}: {zone} (+{score})"],
        'rsi': current,
        'zone': zone
    }


def calculate_adx(df: pd.DataFrame, period: int = None) -> pd.Series:
    """Calculate ADX (Average Directional Index)."""
    if period is None:
        period = ADX_PERIOD
    
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    plus_dm = high.diff()
    minus_dm = -low.diff()
    
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
    
    tr = pd.concat([
        high - low,
        abs(high - close.shift(1)),
        abs(low - close.shift(1))
    ], axis=1).max(axis=1)
    
    atr = tr.ewm(span=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.ewm(span=period, adjust=False).mean()
    
    return adx, plus_di, minus_di


def get_dmi_state(plus_di: float, minus_di: float, tangled_threshold: float = 5.0) -> str:
    """
    Determine DMI state based on +DI and -DI relationship.
    
    Returns:
        'bullish': +DI > -DI (bulls control)
        'bearish': -DI > +DI (bears control)
        'choppy': Lines tangled (indecision)
    """
    diff = plus_di - minus_di
    if abs(diff) < tangled_threshold:
        return 'choppy'
    elif diff > 0:
        return 'bullish'
    else:
        return 'bearish'


def calculate_adx_score(df: pd.DataFrame, max_points: int = 25) -> Dict[str, any]:
    """
    Calculate ADX component of trend score.
    
    NEW LOGIC: ADX measures strength, DMI measures direction.
    Only award points if ADX is strong AND +DI > -DI (bullish).
    
    Scoring:
    - ADX > 25 AND +DI > -DI: 25 pts (strong bullish trend)
    - ADX > 25 AND choppy: 10 pts (strong but directionless)
    - ADX > 25 AND -DI > +DI: 0 pts (strong bearish - bad!)
    - ADX > 20 AND +DI > -DI: 15 pts (moderate bullish trend)
    - ADX <= 20: 5 pts (weak/no trend)
    """
    adx, plus_di, minus_di = calculate_adx(df)
    current_adx = adx.iloc[-1]
    current_plus_di = plus_di.iloc[-1]
    current_minus_di = minus_di.iloc[-1]
    
    dmi_state = get_dmi_state(current_plus_di, current_minus_di)
    dmi_diff = current_plus_di - current_minus_di
    
    # Determine score based on ADX strength AND direction
    if current_adx > 25:
        if dmi_state == 'bullish':
            score = 25
            strength = "Strong bullish trend"
        elif dmi_state == 'choppy':
            score = 10
            strength = "Strong but choppy"
        else:  # bearish
            score = 0
            strength = "Strong BEARISH trend"
    elif current_adx > 20:
        if dmi_state == 'bullish':
            score = 15
            strength = "Moderate bullish trend"
        elif dmi_state == 'choppy':
            score = 8
            strength = "Moderate, choppy"
        else:
            score = 0
            strength = "Moderate bearish"
    else:
        score = 5
        strength = "Weak/no trend"
    
    return {
        'score': min(score, max_points),
        'max': max_points,
        'details': [f"ADX {current_adx:.1f}, +DI {current_plus_di:.1f}, -DI {current_minus_di:.1f}: {strength} (+{score})"],
        'adx': current_adx,
        'plus_di': current_plus_di,
        'minus_di': current_minus_di,
        'dmi_state': dmi_state,
        'dmi_diff': dmi_diff,
        'strength': strength
    }


def calculate_ma_alignment_score(df: pd.DataFrame, max_points: int = 30) -> Dict[str, any]:
    """
    Calculate MA alignment component of trend score.
    
    Perfect bullish alignment: Price > EMA8 > EMA21 > SMA50
    
    Scoring (30 pts max):
    - Price > EMA8: 8 pts
    - EMA8 > EMA21: 8 pts
    - EMA21 > SMA50: 7 pts
    - Price > SMA50: 7 pts
    """
    close = df['Close']
    current_price = close.iloc[-1]
    
    ema8 = close.ewm(span=EMA_FAST, adjust=False).mean().iloc[-1]
    ema21 = close.ewm(span=EMA_MEDIUM, adjust=False).mean().iloc[-1]
    sma50 = close.rolling(window=SMA_SLOW).mean().iloc[-1]
    
    score = 0
    details = []
    alignment = []
    
    if current_price > ema8:
        score += 8
        details.append("Price > EMA8 (+8)")
        alignment.append("P>8")
    
    if ema8 > ema21:
        score += 8
        details.append("EMA8 > EMA21 (+8)")
        alignment.append("8>21")
    
    if ema21 > sma50:
        score += 7
        details.append("EMA21 > SMA50 (+7)")
        alignment.append("21>50")
    
    if current_price > sma50:
        score += 7
        details.append("Price > SMA50 (+7)")
        alignment.append("P>50")
    
    return {
        'score': min(score, max_points),
        'max': max_points,
        'details': details,
        'alignment': ' '.join(alignment) if alignment else "No alignment",
        'price': current_price,
        'ema8': ema8,
        'ema21': ema21,
        'sma50': sma50
    }


def calculate_trend_score(df: pd.DataFrame) -> Dict[str, any]:
    """
    Calculate complete Trend Score (0-100).
    
    NEW WEIGHTS (total 100):
    - MA Stack: 30 pts (Price > EMA8 > EMA21 > SMA50)
    - ADX Power: 25 pts (ADX > 25 AND +DI > -DI)
    - MACD Velocity: 25 pts (MACD > Signal)
    - RSI Zone: 20 pts (RSI > 50, replaces Coppock)
    
    Args:
        df: DataFrame with OHLC data
    
    Returns:
        Dict with total score and component breakdown
    """
    if len(df) < 60:
        return {'error': 'Insufficient data', 'score': 50, 'dmi_state': 'choppy', 'dmi_diff': 0}
    
    # New weights
    ma = calculate_ma_alignment_score(df, 30)  # Increased to 30
    adx = calculate_adx_score(df, 25)
    macd = calculate_macd_score(df, 25)
    rsi_zone = calculate_rsi_zone_score(df, 20)  # Replaces Coppock
    
    total_score = ma['score'] + adx['score'] + macd['score'] + rsi_zone['score']
    
    # Get DMI state from ADX calculation
    dmi_state = adx.get('dmi_state', 'choppy')
    dmi_diff = adx.get('dmi_diff', 0)
    
    # Determine overall assessment
    if total_score >= TREND_SCORE_STRONG:
        assessment = "Strong trend - good for trading"
        emoji = "📈"
    elif total_score >= TREND_SCORE_MIN:
        assessment = "Moderate trend - proceed with caution"
        emoji = "➡️"
    else:
        assessment = "Weak trend - avoid or wait"
        emoji = "📉"
    
    return {
        'score': total_score,
        'max': 100,
        'assessment': assessment,
        'emoji': emoji,
        'is_tradeable': total_score >= TREND_SCORE_MIN,
        'is_strong': total_score >= TREND_SCORE_STRONG,
        'dmi_state': dmi_state,
        'dmi_diff': dmi_diff,
        'plus_di': adx.get('plus_di', 0),
        'minus_di': adx.get('minus_di', 0),
        'components': {
            'ma_alignment': ma,
            'adx': adx,
            'macd': macd,
            'rsi_zone': rsi_zone
        },
        'display': f"{total_score}{emoji}"
    }


# =============================================================================
# STANDALONE TESTING
# =============================================================================
if __name__ == "__main__":
    print("Trend Score Module Test")
    print("=" * 60)
    
    import yfinance as yf
    
    test_tickers = ["AAPL", "NVDA", "MSTR", "SPY"]
    
    for ticker in test_tickers:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="6mo")
            
            if len(df) > 0:
                data = calculate_trend_score(df)
                print(f"\n{ticker}: {data['display']} ({data['score']}/100)")
                print(f"  Assessment: {data['assessment']}")
                print(f"  Components:")
                for name, comp in data['components'].items():
                    print(f"    {name}: {comp['score']}/{comp['max']}")
        except Exception as e:
            print(f"\n{ticker}: Error - {e}")

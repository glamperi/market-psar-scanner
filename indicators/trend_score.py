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


def calculate_coppock(df: pd.DataFrame) -> pd.Series:
    """Calculate Coppock Curve."""
    close = df['Close']
    
    roc1 = ((close / close.shift(COPPOCK_ROC1)) - 1) * 100
    roc2 = ((close / close.shift(COPPOCK_ROC2)) - 1) * 100
    
    coppock = (roc1 + roc2).rolling(window=COPPOCK_WMA).mean()
    return coppock


def calculate_coppock_score(df: pd.DataFrame, max_points: int = 20) -> Dict[str, any]:
    """
    Calculate Coppock component of trend score.
    
    Scoring:
    - Coppock > 0: 10 pts
    - Coppock rising: 10 pts
    """
    coppock = calculate_coppock(df)
    current = coppock.iloc[-1]
    prev = coppock.iloc[-2] if len(df) > 1 else current
    
    score = 0
    details = []
    
    if current > 0:
        score += 10
        details.append("Coppock positive (+10)")
    
    if current > prev:
        score += 10
        details.append("Coppock rising (+10)")
    
    return {
        'score': min(score, max_points),
        'max': max_points,
        'details': details,
        'coppock': current,
        'rising': current > prev
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
    
    return adx


def calculate_adx_score(df: pd.DataFrame, max_points: int = 25) -> Dict[str, any]:
    """
    Calculate ADX component of trend score.
    
    Scoring:
    - ADX > 40: 25 pts (very strong trend)
    - ADX > 30: 20 pts (strong trend)
    - ADX > 25: 15 pts (trending)
    - ADX > 20: 10 pts (weak trend)
    - ADX <= 20: 5 pts (no trend)
    """
    adx = calculate_adx(df)
    current = adx.iloc[-1]
    
    if current > 40:
        score = 25
        strength = "Very strong trend"
    elif current > 30:
        score = 20
        strength = "Strong trend"
    elif current > ADX_STRONG_TREND:
        score = 15
        strength = "Trending"
    elif current > ADX_WEAK_TREND:
        score = 10
        strength = "Weak trend"
    else:
        score = 5
        strength = "No clear trend"
    
    return {
        'score': min(score, max_points),
        'max': max_points,
        'details': [f"ADX {current:.1f}: {strength} (+{score})"],
        'adx': current,
        'strength': strength
    }


def calculate_ma_alignment_score(df: pd.DataFrame, max_points: int = 25) -> Dict[str, any]:
    """
    Calculate MA alignment component of trend score.
    
    Perfect bullish alignment: Price > EMA8 > EMA21 > SMA50
    
    Scoring:
    - Price > EMA8: 7 pts
    - EMA8 > EMA21: 6 pts
    - EMA21 > SMA50: 6 pts
    - Price > SMA50: 6 pts
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
        score += 7
        details.append("Price > EMA8 (+7)")
        alignment.append("P>8")
    
    if ema8 > ema21:
        score += 6
        details.append("EMA8 > EMA21 (+6)")
        alignment.append("8>21")
    
    if ema21 > sma50:
        score += 6
        details.append("EMA21 > SMA50 (+6)")
        alignment.append("21>50")
    
    if current_price > sma50:
        score += 6
        details.append("Price > SMA50 (+6)")
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
    
    Args:
        df: DataFrame with OHLC data
    
    Returns:
        Dict with total score and component breakdown
    """
    if len(df) < 60:
        return {'error': 'Insufficient data', 'score': 50}
    
    macd = calculate_macd_score(df, TREND_SCORE_WEIGHTS['macd'])
    coppock = calculate_coppock_score(df, TREND_SCORE_WEIGHTS['coppock'])
    adx = calculate_adx_score(df, TREND_SCORE_WEIGHTS['adx'])
    ma = calculate_ma_alignment_score(df, TREND_SCORE_WEIGHTS['ma_alignment'])
    
    total_score = macd['score'] + coppock['score'] + adx['score'] + ma['score']
    
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
        'components': {
            'macd': macd,
            'coppock': coppock,
            'adx': adx,
            'ma_alignment': ma
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

"""
Market Scanner V2 - Indicators Module
=====================================

This module contains all technical indicators used by the scanner.

Key Changes in V2:
- PRSI (PSAR on RSI) is the PRIMARY signal
- Price PSAR is used as a RISK FILTER (5% max gap)
- IR is split into Trend Score + Timing Score
- Momentum 9-10 = HOLD (exhausted), not BUY
- OBV is required for CONFIRMATION

Signal Hierarchy:
1. PRSI - Primary trend/entry signal
2. OBV - Confirmation (money flow)
3. Trend Score - Is this a good stock to trade?
4. Timing Score - Is NOW a good time to enter?
5. Price PSAR - Risk filter (gap < 5%)
6. ATR - Overbought/Oversold filter

Usage:
    from indicators import (
        get_psar_data,
        get_full_prsi_analysis,
        get_momentum_data,
        get_obv_data,
        get_atr_data,
        calculate_trend_score,
        calculate_timing_score
    )
"""

# PSAR - Price PSAR (Risk Filter)
from .psar import (
    calculate_psar,
    calculate_psar_gap,
    get_psar_trend,
    classify_psar_zone_v1,
    get_entry_risk,
    get_psar_data,
    format_psar_display
)

# PRSI - PSAR on RSI (Primary Signal)
from .prsi import (
    calculate_rsi,
    calculate_prsi,
    get_prsi_signal,
    get_prsi_trend_emoji,
    format_prsi_display,
    detect_prsi_divergence,
    get_full_prsi_analysis
)

# Momentum (with v2 interpretation)
from .momentum import (
    calculate_momentum_score,
    interpret_momentum_v1,
    interpret_momentum_v2,
    calculate_momentum_acceleration,
    get_momentum_data,
    format_momentum_display,
    is_momentum_favorable_for_entry
)

# OBV - On-Balance Volume (Confirmation)
from .obv import (
    calculate_obv,
    calculate_obv_ma,
    get_obv_trend,
    detect_obv_divergence,
    get_obv_confirmation,
    get_obv_data,
    format_obv_display,
    is_obv_favorable
)

# ATR - Overbought/Oversold
from .atr import (
    calculate_true_range,
    calculate_atr,
    calculate_atr_percent,
    get_atr_status,
    get_atr_data,
    format_atr_display
)

# Trend Score (MA + ADX/DMI + MACD + RSI Zone)
from .trend_score import (
    calculate_macd,
    calculate_macd_score,
    calculate_rsi_for_trend,
    calculate_rsi_zone_score,
    calculate_adx,
    get_dmi_state,
    calculate_adx_score,
    calculate_ma_alignment_score,
    calculate_trend_score
)

# Timing Score (Williams + Bollinger + RSI + Gap)
from .timing_score import (
    calculate_williams_r,
    calculate_williams_score,
    calculate_bollinger_bands,
    calculate_bollinger_score,
    calculate_rsi_position_score,
    calculate_gap_score,
    calculate_timing_score,
    get_entry_grade
)


# Convenience function to get all indicators at once
def get_all_indicators(df, use_v2: bool = True):
    """
    Calculate all indicators for a stock.
    
    Args:
        df: DataFrame with OHLC and Volume data
        use_v2: Use v2 interpretation (default True)
    
    Returns:
        Dict with all indicator data
    """
    # Get PSAR first (needed for other calculations)
    psar_data = get_psar_data(df)
    if psar_data is None:
        return {'error': 'Insufficient data'}
    
    psar_gap = psar_data['gap_percent']
    price_psar_trend = psar_data['trend']
    
    # Get all other indicators
    prsi_data = get_full_prsi_analysis(df, price_psar_trend, psar_gap)
    momentum_data = get_momentum_data(df, psar_data.get('psar_series'), use_v2)
    obv_data = get_obv_data(df)
    atr_data = get_atr_data(df)
    trend_score = calculate_trend_score(df)
    timing_score = calculate_timing_score(df, psar_gap)
    
    # Get OBV confirmation
    obv_confirmation = get_obv_confirmation(
        obv_is_bullish=obv_data.get('is_bullish', False),
        prsi_is_bullish=prsi_data.get('is_bullish', False),
        price_psar_bullish=(price_psar_trend == 'bullish')
    )
    
    # Get entry grade
    entry_grade = get_entry_grade(
        trend_score=trend_score.get('score', 50),
        timing_score=timing_score.get('score', 50),
        gap_allowed=psar_data['entry_risk']['entry_allowed']
    )
    
    return {
        'psar': psar_data,
        'prsi': prsi_data,
        'momentum': momentum_data,
        'obv': obv_data,
        'obv_confirmation': obv_confirmation,
        'atr': atr_data,
        'trend_score': trend_score,
        'timing_score': timing_score,
        'entry_grade': entry_grade,
        
        # Quick access to key values
        'price': psar_data['price'],
        'psar_gap': psar_gap,
        'psar_days_in_trend': psar_data.get('days_in_trend', 0),
        'prsi_bullish': prsi_data.get('is_bullish', False),
        'prsi_signal': prsi_data.get('signal', {}),
        'momentum_score': momentum_data.get('score', 5),
        'obv_bullish': obv_data.get('is_bullish', False),
        'atr_percent': atr_data.get('atr_percent', 0),
        'trend_score_value': trend_score.get('score', 50),
        'timing_score_value': timing_score.get('score', 50),
        'entry_allowed': psar_data['entry_risk']['entry_allowed'] and timing_score.get('entry_allowed', True),
        'grade': entry_grade['grade'],
        
        # Checkboxes for new display
        'dmi_bullish': trend_score.get('dmi_state', 'choppy') == 'bullish',
        'adx_strong': trend_score.get('components', {}).get('adx', {}).get('adx', 0) > 25,
        'adx_value': trend_score.get('components', {}).get('adx', {}).get('adx', 0),
        'macd_bullish': trend_score.get('components', {}).get('macd', {}).get('value', 0) > trend_score.get('components', {}).get('macd', {}).get('signal', 0),
        'williams_r': timing_score.get('components', {}).get('williams', {}).get('value', -50)
    }


__all__ = [
    # PSAR
    'calculate_psar', 'calculate_psar_gap', 'get_psar_trend',
    'classify_psar_zone_v1', 'get_entry_risk', 'get_psar_data', 'format_psar_display',
    
    # PRSI
    'calculate_rsi', 'calculate_prsi', 'get_prsi_signal',
    'get_prsi_trend_emoji', 'format_prsi_display', 'detect_prsi_divergence',
    'get_full_prsi_analysis',
    
    # Momentum
    'calculate_momentum_score', 'interpret_momentum_v1', 'interpret_momentum_v2',
    'calculate_momentum_acceleration', 'get_momentum_data', 'format_momentum_display',
    'is_momentum_favorable_for_entry',
    
    # OBV
    'calculate_obv', 'calculate_obv_ma', 'get_obv_trend',
    'detect_obv_divergence', 'get_obv_confirmation', 'get_obv_data',
    'format_obv_display', 'is_obv_favorable',
    
    # ATR
    'calculate_true_range', 'calculate_atr', 'calculate_atr_percent',
    'get_atr_status', 'get_atr_data', 'format_atr_display',
    
    # Trend Score
    'calculate_macd', 'calculate_macd_score', 'calculate_rsi_for_trend',
    'calculate_rsi_zone_score', 'calculate_adx', 'get_dmi_state',
    'calculate_adx_score', 'calculate_ma_alignment_score', 'calculate_trend_score',
    
    # Timing Score
    'calculate_williams_r', 'calculate_williams_score',
    'calculate_bollinger_bands', 'calculate_bollinger_score',
    'calculate_rsi_position_score', 'calculate_gap_score',
    'calculate_timing_score', 'get_entry_grade',
    
    # All-in-one
    'get_all_indicators'
]

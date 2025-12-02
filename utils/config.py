"""
Market Scanner v2 Configuration
================================
Central configuration for all scanner parameters and thresholds.

Key Changes from v1:
- PRSI is now the primary signal (not Price PSAR)
- Split IR into Trend Score + Timing Score
- Momentum 9-10 = exhausted (HOLD), not STRONG BUY
- 5% gap max rule for entries
- Smart Short never shorts RSI < 35
"""

# =============================================================================
# PSAR SETTINGS
# =============================================================================
PSAR_AF = 0.02          # Acceleration factor
PSAR_MAX_AF = 0.2       # Maximum acceleration factor

# =============================================================================
# GAP THRESHOLDS (Price distance from PSAR)
# =============================================================================
GAP_EXCELLENT = 3.0     # < 3% = low risk, excellent entry
GAP_ACCEPTABLE = 5.0    # 3-5% = medium risk, acceptable entry
GAP_MAX = 5.0           # > 5% = NO ENTRY regardless of other signals

# =============================================================================
# ZONE CLASSIFICATION (v2 - PRSI Primary)
# =============================================================================
# Price PSAR thresholds (used as risk filter, not primary signal)
PSAR_STRONG_BUY = 5.0   # > 5% above PSAR (but need PRSI + OBV confirmation)
PSAR_BUY = 0.0          # > 0% (above PSAR line)
PSAR_NEUTRAL_LOW = -2.0 # Neutral zone
PSAR_NEUTRAL_HIGH = 2.0
PSAR_SELL = -5.0        # < -5% below PSAR

# =============================================================================
# TREND SCORE THRESHOLDS (0-100)
# =============================================================================
TREND_SCORE_STRONG = 70     # > 70 = strong trend worth trading
TREND_SCORE_MIN = 50        # < 50 = weak trend, avoid
TREND_SCORE_WEIGHTS = {
    'macd': 30,             # MACD above signal line, histogram rising
    'coppock': 20,          # Coppock curve rising
    'adx': 25,              # ADX > 25 = strong trend
    'ma_alignment': 25,     # Price > EMA8 > EMA21 > SMA50
}

# =============================================================================
# TIMING SCORE THRESHOLDS (0-100)
# =============================================================================
TIMING_SCORE_OVERBOUGHT = 80    # > 80 = overbought, wait for pullback
TIMING_SCORE_OVERSOLD = 30      # < 30 = oversold, caution
TIMING_SCORE_IDEAL_MIN = 40     # Ideal entry zone
TIMING_SCORE_IDEAL_MAX = 70
TIMING_SCORE_WEIGHTS = {
    'williams_r': 25,           # Not at extremes (-80 to -20)
    'bollinger': 25,            # Near middle band
    'rsi_position': 25,         # RSI 40-60 ideal
    'psar_gap': 25,             # Gap < 3% = full points
}

# =============================================================================
# MOMENTUM INTERPRETATION (v2 - Changed!)
# =============================================================================
# v1: High momentum = BUY (wrong - buying exhaustion)
# v2: High momentum = HOLD (already extended)
MOMENTUM_EXHAUSTED_MIN = 9      # 9-10 = no new entries, HOLD only
MOMENTUM_STRONG_MIN = 7         # 7-8 = strong, good if PRSI confirms
MOMENTUM_IDEAL_MIN = 5          # 5-7 = best entry zone (accelerating)
MOMENTUM_IDEAL_MAX = 7
MOMENTUM_WEAK_MAX = 3           # 1-3 = weak, avoid or watch for bounce
MOMENTUM_LOOKBACK = 10          # Days to calculate momentum

# =============================================================================
# RSI SETTINGS
# =============================================================================
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# For Smart Buy/Short logic
RSI_SMART_BUY_MIN = 45          # Don't buy if RSI < 45 (too weak)
RSI_SMART_BUY_MAX = 65          # Don't buy if RSI > 65 (overheated)
RSI_SMART_SHORT_MIN = 40        # Don't short if RSI < 40 (too oversold)
RSI_SMART_SHORT_MAX = 60        # Don't short if RSI > 60 (too strong)
RSI_NO_SHORT_BELOW = 35         # NEVER short below this (capitulation)

# =============================================================================
# ATR SETTINGS (Overbought/Oversold)
# =============================================================================
ATR_PERIOD = 14
ATR_EMA_PERIOD = 8              # Compare price to EMA8
ATR_OVERBOUGHT = 3.0            # Price > EMA8 + 3% of ATR = overbought
ATR_OVERSOLD = -3.0             # Price < EMA8 - 3% of ATR = oversold
ATR_EXTREME_OVERBOUGHT = 5.0    # Extreme extension
ATR_EXTREME_OVERSOLD = -5.0

# =============================================================================
# OBV SETTINGS
# =============================================================================
OBV_MA_PERIOD = 20              # Moving average for OBV trend
OBV_LOOKBACK = 5                # Days to determine OBV direction

# =============================================================================
# WILLIAMS %R SETTINGS
# =============================================================================
WILLIAMS_R_PERIOD = 14
WILLIAMS_R_OVERBOUGHT = -20     # > -20 = overbought
WILLIAMS_R_OVERSOLD = -80       # < -80 = oversold

# =============================================================================
# BOLLINGER BANDS SETTINGS
# =============================================================================
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2.0

# =============================================================================
# MACD SETTINGS
# =============================================================================
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# =============================================================================
# COPPOCK CURVE SETTINGS
# =============================================================================
COPPOCK_WMA = 10
COPPOCK_ROC1 = 14
COPPOCK_ROC2 = 11

# =============================================================================
# MOVING AVERAGE SETTINGS
# =============================================================================
EMA_FAST = 8
EMA_MEDIUM = 21
SMA_SLOW = 50
SMA_LONG = 200

# =============================================================================
# ADX SETTINGS
# =============================================================================
ADX_PERIOD = 14
ADX_STRONG_TREND = 25           # ADX > 25 = strong trend
ADX_WEAK_TREND = 20             # ADX < 20 = weak/no trend

# =============================================================================
# DATA FETCH SETTINGS
# =============================================================================
HISTORY_DAYS = 200              # Days of history to fetch
MIN_HISTORY_DAYS = 50           # Minimum required for calculations

# =============================================================================
# MARKET CAP FILTER (in millions)
# =============================================================================
DEFAULT_MIN_MARKET_CAP = 500    # $500M minimum by default

# =============================================================================
# SCAN MODES
# =============================================================================
SCAN_MODES = {
    'market': 'Full market scan (S&P 500 + NASDAQ 100 + Russell 2000 + IBD)',
    'mystocks': 'Portfolio scan with position values',
    'friends': 'Friends watchlist scan',
    'shorts': 'Short candidates scan',
}

# =============================================================================
# DATA FILE PATHS
# =============================================================================
DATA_FILES_DIR = 'data_files'

TICKER_FILES = {
    'sp500': f'{DATA_FILES_DIR}/sp500_tickers.csv',
    'nasdaq100': f'{DATA_FILES_DIR}/nasdaq100_tickers.csv',
    'russell2000': f'{DATA_FILES_DIR}/russell2000_tickers.csv',
}

IBD_FILES = {
    'ibd_50': f'{DATA_FILES_DIR}/ibd_50.csv',
    'ibd_bigcap20': f'{DATA_FILES_DIR}/ibd_bigcap20.csv',
    'ibd_sector': f'{DATA_FILES_DIR}/ibd_sector.csv',
    'ibd_ipo': f'{DATA_FILES_DIR}/ibd_ipo.csv',
    'ibd_spotlight': f'{DATA_FILES_DIR}/ibd_spotlight.csv',
}

USER_FILES = {
    'mystocks': f'{DATA_FILES_DIR}/mystocks.txt',
    'friends': f'{DATA_FILES_DIR}/friends.txt',
    'shorts': f'{DATA_FILES_DIR}/shorts.txt',
    'watchlist': f'{DATA_FILES_DIR}/custom_watchlist.txt',
    'positions': f'{DATA_FILES_DIR}/mypositions.csv',
}

# =============================================================================
# IBD LIST URL MAPPING
# =============================================================================
IBD_LIST_MAP = {
    'ibd_50': 'ibd50',
    'ibd_bigcap20': 'bigcap20',
    'ibd_sector': 'sectorleaders',
    'ibd_ipo': 'ipo-leaders',
    'ibd_spotlight': 'stock-spotlight',
}

# =============================================================================
# CBOE SETTINGS
# =============================================================================
CBOE_URL = "https://ww2.cboe.com/us/options/market_statistics/?iframe=1"

# Put/Call Ratio interpretation thresholds
PCR_EXTREME_COMPLACENCY = 0.50  # < 0.50 = potential market TOP
PCR_HIGH_GREED = 0.60           # < 0.60 = high greed, correction possible
PCR_BULLISH = 0.70              # 0.60-0.70 = bullish sentiment
PCR_NEUTRAL_LOW = 0.70          # 0.70-0.90 = neutral
PCR_NEUTRAL_HIGH = 0.90
PCR_ELEVATED_FEAR = 1.00        # 0.90-1.00 = elevated fear, buying opportunity
PCR_HIGH_FEAR = 1.20            # 1.00-1.20 = high fear, good buying opportunity
PCR_EXTREME_FEAR = 1.20         # > 1.20 = extreme fear, contrarian BUY

# =============================================================================
# EMAIL SETTINGS
# =============================================================================
EMAIL_SUBJECT_PREFIX = "📊"
EMAIL_MAX_STOCKS_PER_SECTION = 30

# =============================================================================
# REPORT DISPLAY SETTINGS
# =============================================================================
ZONE_COLORS = {
    'STRONG_BUY': '#27ae60',    # Green
    'BUY': '#2ecc71',           # Light green
    'EARLY_BUY': '#3498db',     # Blue (new zone)
    'HOLD': '#f39c12',          # Orange (new zone)
    'NEUTRAL': '#95a5a6',       # Gray
    'WARNING': '#e67e22',       # Dark orange (new zone)
    'WEAK': '#e74c3c',          # Red
    'SELL': '#c0392b',          # Dark red
    'OVERSOLD_WATCH': '#9b59b6', # Purple (new zone)
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

# Entry quality grades
ENTRY_GRADES = {
    'A': 'Excellent - all signals aligned, low risk',
    'B': 'Good - most signals aligned, moderate risk',
    'C': 'Poor - conflicting signals or high risk, wait',
}

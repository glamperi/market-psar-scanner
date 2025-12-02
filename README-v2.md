# Market PSAR Scanner v2 - Refactor Branch

## Overview

This is a major refactor of the market scanner that addresses fundamental flaws in the original signal logic:

### Problems with v1:
1. **Buying Exhaustion**: Momentum 9-10 + High PSAR% = buying after the move is done
2. **Shorting Capitulation**: Deep negative PSAR = shorting into support after crash
3. **Conflicting IR Score**: Trend indicators (MACD) fight mean-reversion indicators (Bollinger)
4. **Late Entries**: Price PSAR confirms too late - missing early moves

### v2 Solutions:
1. **PRSI as Primary Signal**: PSAR on RSI leads price by 1-3 days
2. **Split Scores**: Separate Trend Score from Timing Score
3. **OBV Confirmation**: Volume flow confirms or warns against signals
4. **5% Gap Rule**: Never enter when price is >5% from PSAR (too risky)
5. **Smart Buy/Short Logic**: Buy pullbacks in uptrends, short rallies in downtrends

---

## New Signal Hierarchy

| Priority | Indicator | Purpose |
|----------|-----------|---------|
| 1 | **PRSI** (PSAR on RSI) | Primary trend/entry signal |
| 2 | **OBV** | Confirmation (money flow) |
| 3 | **Trend Score** | Is this a strong trend worth trading? |
| 4 | **Timing Score** | Is NOW a good time to enter? |
| 5 | **Price PSAR %** | Risk filter (gap < 5%) |
| 6 | **ATR Status** | Overbought/Oversold filter |

---

## New Zone Classification

| Zone | Criteria | Action |
|------|----------|--------|
| **STRONG BUY** | PRSI ↗️ + OBV 🟢 + Gap < 5% + Timing neutral | Enter now |
| **BUY** | PRSI ↗️ + (OBV 🟢 OR Gap < 3%) | Enter with caution |
| **EARLY BUY** | PRSI ↗️ + Price PSAR still negative | Catching the turn early |
| **HOLD** | PRSI ↗️ + Gap > 5% | Wait for pullback |
| **WARNING** | PRSI ↘️ + Price PSAR positive | Momentum fading, consider exit |
| **SELL** | PRSI ↘️ + OBV 🔴 | Exit position |
| **OVERSOLD WATCH** | PRSI ↘️ + OBV 🟢 + Williams ✓ | Potential bounce setup |

---

## Score Definitions

### Trend Score (0-100) - "Is this a good stock to trade?"

| Component | Points | Criteria |
|-----------|--------|----------|
| MACD | 0-30 | MACD > Signal line, histogram rising |
| Coppock | 0-20 | Coppock curve rising from bottom |
| ADX | 0-25 | ADX > 25 = strong trend |
| MA Alignment | 0-25 | Price > EMA8 > EMA21 > SMA50 |
| **Total** | **0-100** | |

**Usage**: Only trade stocks with Trend Score > 60

### Timing Score (0-100) - "Is NOW a good time to enter?"

| Component | Points | Criteria |
|-----------|--------|----------|
| Williams %R | 0-25 | Between -80 and -20 (not extreme) |
| Bollinger Position | 0-25 | Near middle band, not at edges |
| RSI Position | 0-25 | Between 40-60 (neutral zone) |
| PSAR Gap | 0-25 | Gap < 3% = 25pts, 3-5% = 15pts, >5% = 0pts |
| **Total** | **0-100** | |

**Usage**: 
- Timing 60-80 = Good entry
- Timing > 80 = Overbought, wait
- Timing < 40 = Oversold, caution

---

## Momentum Reinterpretation

### Old Logic (v1):
- Momentum 9-10 = STRONG BUY ❌ (actually exhaustion)

### New Logic (v2):
| Momentum | Interpretation | Action |
|----------|---------------|--------|
| 1-3 | Weak/Capitulating | Avoid (or watch for bounce) |
| 4-5 | Stabilizing | Watch for PRSI flip |
| **6-7** | **Accelerating** | **Best entry zone** |
| 8 | Strong | Good if PRSI confirms |
| 9-10 | Exhausted | HOLD only, no new entries |

---

## Smart Buy Logic

**Target**: Catching a stock trending up but pulling back to support

```
Criteria:
  - Price > 50-Day MA (uptrend)
  - RSI between 45-65 (healthy, not overheated)
  - PSAR Gap < 3% OR Price touching 20-Day MA
  - PRSI is Bullish (↗️)
  - OBV is Green (accumulation)
```

---

## Smart Short Logic

**Target**: Shorting a weak stock that bounces into resistance

```
Criteria:
  - Price < 50-Day MA (downtrend)
  - RSI between 40-60 (recovered from crash, not capitulating)
  - Price rallying toward resistance (Price > EMA8)
  - PRSI is Bearish (↘️) or just flipped
  - HARD RULE: Never short if RSI < 35 (too oversold)
```

---

## The 5% Gap Rule

**Hard constraint applied to ALL signals:**

```python
gap_percent = abs(price - psar) / price * 100

if gap_percent > 5.0:
    # Disqualify from new entries
    # Too much risk - wait for pullback/rally to close the gap
    entry_allowed = False
```

**Rationale**: A 5% gap means if PSAR flips against you, you lose 5% immediately. That's too much risk for a new position.

---

## File Structure

```
market_scanner/
│
├── indicators/
│   ├── __init__.py
│   ├── psar.py              # Price PSAR calculation
│   ├── prsi.py              # PSAR on RSI (primary signal)
│   ├── trend_score.py       # MACD + Coppock + ADX + MA alignment
│   ├── timing_score.py      # Williams + Bollinger + RSI + Gap
│   ├── obv.py               # On-Balance Volume status
│   ├── atr.py               # ATR-based overbought/oversold
│   └── momentum.py          # Momentum calculation & interpretation
│
├── signals/
│   ├── __init__.py
│   ├── zone_classifier.py   # New PRSI-primary zone logic
│   ├── entry_quality.py     # A/B/C entry grading
│   ├── warnings.py          # Overbought, Divergence, Bounce warnings
│   └── gap_filter.py        # 5% gap rule enforcement
│
├── scanners/
│   ├── __init__.py
│   ├── base_scanner.py      # Common scanner functionality
│   ├── market_scanner.py    # Full market scan (S&P, NASDAQ, Russell, IBD)
│   ├── portfolio.py         # Portfolio scan (-mystocks)
│   ├── friends.py           # Friends watchlist scan (-friends)
│   ├── shorts.py            # Short candidates scan (-shorts)
│   ├── smart_buy.py         # Smart buy signal scanner
│   ├── smart_short.py       # Smart short signal scanner
│   └── dividend.py          # Dividend stock scanner
│
├── reports/
│   ├── __init__.py
│   ├── email_report.py      # Market scan email report
│   ├── portfolio_report.py  # Portfolio HTML report (-mystocks, -friends)
│   ├── console_report.py    # Terminal output
│   └── formatters.py        # Common formatting (zones, colors, etc.)
│
├── data/
│   ├── __init__.py
│   ├── fetcher.py           # yfinance wrapper with caching
│   ├── ibd_utils.py         # IBD file loading & URL generation ⭐
│   ├── cboe.py              # CBOE P/C ratio scraper
│   └── ticker_lists.py      # Load SP500, NASDAQ100, Russell2000, etc.
│
├── utils/
│   ├── __init__.py
│   ├── config.py            # Configuration constants
│   ├── filters.py           # EPS, Revenue, Market Cap filters
│   └── helpers.py           # Misc utility functions
│
├── data_files/              # User data files (gitignored)
│   ├── mystocks.csv         # Portfolio positions
│   ├── friends.csv          # Friends watchlist
│   ├── shorts.csv           # Short candidates
│   ├── watchlist.csv        # Priority tickers
│   ├── sp500_tickers.csv    # S&P 500 list
│   ├── nasdaq100_tickers.csv
│   ├── russell2000_tickers.csv
│   ├── ibd_50.csv           # IBD lists (Excel format)
│   ├── ibd_bigcap20.csv
│   ├── ibd_sector.csv
│   ├── ibd_ipo.csv
│   └── ibd_spotlight.csv
│
├── main.py                  # Main CLI entry point
├── requirements.txt
└── README.md
```

---

## Module Descriptions

### indicators/

#### `psar.py`
```python
def calculate_psar(df, af=0.02, max_af=0.2):
    """Calculate Parabolic SAR and return PSAR value, direction, gap%"""
    
def get_psar_zone(gap_percent):
    """Classify gap into zone (for risk filtering only)"""
```

#### `prsi.py` 
```python
def calculate_prsi(df, rsi_period=14, af=0.02):
    """
    Calculate PSAR on RSI - THE PRIMARY SIGNAL
    Returns: prsi_bullish (bool), prsi_value, days_since_flip
    """

def get_prsi_trend(prsi_history):
    """Determine if PRSI is trending up, down, or neutral"""
```

#### `trend_score.py`
```python
def calculate_trend_score(df):
    """
    Trend Score (0-100): Is this a good stock to trade?
    - MACD alignment (0-30)
    - Coppock curve (0-20)  
    - ADX strength (0-25)
    - MA alignment (0-25)
    """
```

#### `timing_score.py`
```python
def calculate_timing_score(df, psar_gap):
    """
    Timing Score (0-100): Is NOW a good entry?
    - Williams %R position (0-25)
    - Bollinger position (0-25)
    - RSI position (0-25)
    - PSAR gap size (0-25)
    """
```

### signals/

#### `zone_classifier.py`
```python
def classify_zone(prsi_bullish, obv_status, psar_gap, timing_score, momentum):
    """
    New PRSI-primary zone classification
    Returns: zone, entry_quality, warnings
    """
```

#### `entry_quality.py`
```python
def grade_entry(psar_gap, prsi_confirms, obv_confirms, timing_score):
    """
    Grade entry quality A/B/C
    A = Excellent (gap <3%, all confirm)
    B = Good (gap 3-5%, most confirm)
    C = Poor (gap >5% or conflicting signals)
    """
```

#### `warnings.py`
```python
def check_warnings(indicators):
    """
    Generate warning flags:
    - 🔥 OVERBOUGHT: ATR > +3% AND (OBV Red OR Mom 9-10)
    - ❄️ OVERSOLD BOUNCE: PSAR < -5% AND OBV Green AND Williams ✓
    - ⚡ EARLY ENTRY: Price PSAR negative BUT PRSI bullish
    - ⚠️ DIVERGENCE: PRSI disagrees with Price PSAR
    """
```

### scanners/

#### `smart_buy.py`
```python
class SmartBuyScanner:
    """
    Finds stocks to buy using new logic:
    - Above 50 MA (uptrend)
    - RSI 45-65 (healthy)
    - Gap < 3% or at 20 MA (low risk entry)
    - PRSI bullish
    - OBV green
    """
```

#### `smart_short.py`
```python
class SmartShortScanner:
    """
    Finds stocks to short using new logic:
    - Below 50 MA (downtrend)
    - RSI 40-60 (not capitulating)
    - Rallying toward resistance
    - PRSI bearish
    - NEVER short RSI < 35
    """
```

#### `portfolio.py`
```python
class PortfolioScanner:
    """
    Scans user's portfolio positions (-mystocks mode)
    - Reads from mystocks.csv with position values
    - Includes covered call recommendations
    - Shows concentrated positions
    - Tracks position value by zone
    """
```

#### `friends.py`
```python
class FriendsScanner:
    """
    Scans friend's stock list (-friends mode)
    - Reads from friends.csv (ticker list only)
    - Same analysis without position values
    - Can send separate email reports
    """
```

#### `shorts.py`
```python
class ShortsScanner:
    """
    Scans user's short watchlist (-shorts mode)
    - Reads from shorts.csv
    - Uses Smart Short logic
    - Identifies best short candidates
    """
```

#### `dividend.py`
```python
class DividendScanner:
    """
    Filters for dividend-paying stocks
    - Minimum yield threshold
    - Combines with zone analysis
    - Good for income-focused portfolios
    """
```

---

## Existing Features (Preserved)

### Input Files

| File | Purpose | Format |
|------|---------|--------|
| `mystocks.csv` | Portfolio positions | `ticker,shares,cost_basis` |
| `friends.csv` | Friend's watchlist | `ticker` (one per line) |
| `shorts.csv` | Short candidates | `ticker` (one per line) |
| `watchlist.csv` | Priority scan list | `ticker` (one per line) |
| `sp500_tickers.csv` | S&P 500 list | `Symbol,Name` |
| `nasdaq100_tickers.csv` | NASDAQ 100 list | `Symbol,Name` |
| `russell2000_tickers.csv` | Russell 2000 list | `Symbol,Name` |
| `ibd_50.csv` | IBD 50 list | Excel format with ratings |
| `ibd_bigcap20.csv` | IBD Big Cap 20 | Excel format with ratings |
| `ibd_sector.csv` | IBD Sector Leaders | Excel format with ratings |
| `ibd_ipo.csv` | IBD IPO Leaders | Excel format with ratings |
| `ibd_spotlight.csv` | IBD Stock Spotlight | Excel format with ratings |

### IBD Integration ⭐

- **IBD Stars**: Stocks on IBD lists show ⭐ in reports
- **IBD Links**: Click ⭐ to go to IBD research page with buy points
- **IBD Ratings**: Composite, EPS, RS, SMR ratings displayed
- **Source Tracking**: Shows which IBD list (IBD 50, Big Cap 20, etc.)

```python
# data/ibd_utils.py
def load_ibd_data():
    """Load all IBD files, extract ratings and company names"""

def get_ibd_url(ticker, ibd_stats, exchange):
    """Generate clickable IBD research URL"""

def format_ibd_ticker(ticker, source, ibd_url):
    """Format ticker with ⭐ link for HTML reports"""
```

### Screening Filters

```bash
# EPS Growth Filter
python market_scanner.py --eps 20    # Only stocks with EPS growth > 20%

# Revenue Growth Filter  
python market_scanner.py --rev 15    # Only stocks with revenue growth > 15%

# Market Cap Filter
python market_scanner.py --mc 1000   # Only stocks with market cap > $1B

# Combine filters
python market_scanner.py --eps 20 --rev 15 --mc 5000

# Include ADRs
python market_scanner.py --adr
```

### Scan Modes

```bash
# Full market scan (S&P 500 + NASDAQ 100 + Russell 2000 + IBD)
python market_scanner.py

# Portfolio scan with position values
python market_scanner.py -mystocks

# Friends watchlist scan
python market_scanner.py -friends

# Short candidates scan
python market_scanner.py -shorts

# Combine with filters
python market_scanner.py -mystocks --eps 10
```

### Report Features

#### Portfolio Report (-mystocks)
- Total portfolio value by zone
- Concentrated positions (>$10K)
- Covered call opportunities with strikes/yields
- Position improving/deteriorating alerts
- Overbought/Oversold position alerts
- Recent exits tracking

#### Email Reports
- HTML formatted emails
- CBOE Put/Call ratio sentiment
- Zone-grouped stock tables
- Dividend stocks section
- IBD stars with clickable links
- Mobile-friendly formatting

### CBOE Market Sentiment

```python
# data/cboe.py
def get_cboe_ratios_and_analyze():
    """
    Scrapes CBOE for Put/Call ratio
    - Total P/C ratio from ww2.cboe.com iframe
    - Sentiment interpretation (fear/greed)
    - Included in report headers
    """
```

| P/C Ratio | Interpretation |
|-----------|----------------|
| < 0.50 | 🚨 Extreme complacency - potential TOP |
| 0.50-0.60 | 🚨 High greed - correction possible |
| 0.60-0.70 | Bullish sentiment - normal |
| 0.70-0.90 | Neutral sentiment |
| 0.90-1.00 | 🟢 Elevated fear - buying opportunity |
| 1.00-1.20 | 🟢 High fear - good buying opportunity |
| > 1.20 | ✅ Extreme fear - contrarian BUY |

---

## Migration Guide

### Running v1 (Classic) vs v2 (New)

```bash
# Classic mode (original logic)
python market_scanner.py --classic

# New mode (PRSI-primary, default in v2)
python market_scanner.py

# Compare both
python market_scanner.py --compare
```

### Key Behavior Changes

| Behavior | v1 (Classic) | v2 (New) |
|----------|--------------|----------|
| Primary Signal | Price PSAR | PRSI |
| Momentum 10 | STRONG BUY | HOLD (exhausted) |
| PSAR -9% | SELL/SHORT | OVERSOLD WATCH |
| IR Score | Single 0-100 | Trend + Timing split |
| Entry Filter | None | 5% gap max |
| OBV Usage | Display only | Confirmation required |

---

## Configuration

### `utils/config.py`

```python
# PSAR Settings
PSAR_AF = 0.02
PSAR_MAX_AF = 0.2

# Gap Thresholds
GAP_EXCELLENT = 3.0    # < 3% = low risk
GAP_ACCEPTABLE = 5.0   # 3-5% = medium risk
GAP_MAX = 5.0          # > 5% = no entry

# Score Thresholds
TREND_SCORE_MIN = 60   # Minimum to consider trading
TIMING_SCORE_OVERBOUGHT = 80
TIMING_SCORE_OVERSOLD = 40

# Momentum Interpretation
MOMENTUM_EXHAUSTED = 9  # 9-10 = no new entries
MOMENTUM_IDEAL_MIN = 6  # 6-7 = best entries
MOMENTUM_IDEAL_MAX = 7

# RSI Thresholds (for Smart Short)
RSI_NO_SHORT_BELOW = 35  # Never short below this

# ATR Thresholds
ATR_OVERBOUGHT = 3.0   # > 3% above = overbought
ATR_OVERSOLD = -3.0    # < -3% = oversold
```

---

## Example Output (v2)

```
====================================================================
MARKET SCAN RESULTS - 2025-12-02
====================================================================
Trend Score Min: 60 | Timing Filter: 40-80 | Max Gap: 5%

⚡ EARLY BUY (3) - PRSI flipped bullish, price catching up
--------------------------------------------------------------------
Ticker  Price   PRSI  OBV  Trend  Timing  Gap%  Mom  Entry
NVDA    $181    ↗️    🟢    72     55     -4.2%   5    B
XYZ     $45     ↗️    🟢    68     62     -2.1%   6    A
ABC     $120    ↗️    🟢    65     58     -3.5%   5    B

✅ STRONG BUY (5) - All signals aligned
--------------------------------------------------------------------
Ticker  Price   PRSI  OBV  Trend  Timing  Gap%  Mom  Entry
AAPL    $283    ↗️    🟢    78     52     +2.1%   7    A
...

⚠️ HOLD - Good trend but wait for pullback (Gap > 5%)
--------------------------------------------------------------------
Ticker  Price   PRSI  OBV  Trend  Timing  Gap%  Mom  Entry
COCO    $54     ↗️    🟢    75     85     +18%   10   C
META    $640    ↗️    🔴    72     78     +7.6%   8    C

❄️ OVERSOLD WATCH - Potential bounce setup
--------------------------------------------------------------------
Ticker  Price   PRSI  OBV  Trend  Timing  Gap%  Mom  Entry
MSTR    $171    ↘️    🟢    45     35     -9.3%   2    WAIT
```

---

## Testing Plan

1. **Parallel Run**: Run v1 and v2 simultaneously for 1 week
2. **Compare Signals**: Track which version's signals perform better
3. **Key Metrics**:
   - Win rate (% of signals that go in predicted direction)
   - Average gain/loss per signal
   - False signal rate (signals that immediately reverse)
4. **Backtest**: Apply new logic to last 30 days of data

---

## Dependencies

```
# requirements.txt
yfinance>=0.2.0
pandas>=2.0.0
numpy>=1.24.0
ta>=0.10.0
selenium>=4.0.0
webdriver-manager>=4.0.0
xlrd>=2.0.0
```

---

## Authors & Version

- **Version**: 2.0.0-beta
- **Branch**: `feature/prsi-primary-refactor`
- **Last Updated**: December 2025

---

## Quick Start

```bash
# Clone and checkout refactor branch
git checkout -b feature/prsi-primary-refactor

# Install dependencies
pip install -r requirements.txt

# Run with new logic
python main.py -mystocks

# Run with classic logic (for comparison)
python main.py -mystocks --classic

# Run market scan with smart buy logic
python main.py --smart-buy

# Run short scan with smart short logic  
python main.py --smart-short
```

---

## Full CLI Reference

```bash
# SCAN MODES
python main.py                    # Full market scan (default)
python main.py -mystocks          # Portfolio scan with values
python main.py -friends           # Friends watchlist scan
python main.py -shorts            # Short candidates scan

# SCREENING FILTERS
python main.py --eps 20           # EPS growth > 20%
python main.py --rev 15           # Revenue growth > 15%
python main.py --mc 1000          # Market cap > $1B (millions)
python main.py --adr              # Include ADR stocks

# SIGNAL MODES (v2)
python main.py --smart-buy        # Use Smart Buy logic
python main.py --smart-short      # Use Smart Short logic

# COMPARISON MODE
python main.py --classic          # Use v1 logic (Price PSAR primary)
python main.py --compare          # Run both v1 and v2, show differences

# EMAIL OPTIONS
python main.py -mystocks --email           # Send to default recipient
python main.py -friends --email user@x.com # Send to specific address

# COMBINE OPTIONS
python main.py -mystocks --eps 10 --email
python main.py -friends --rev 15 --mc 5000
python main.py -shorts --smart-short --email
```

---

## Environment Variables

```bash
# Email Configuration (for --email flag)
export GMAIL_EMAIL="your-email@gmail.com"
export GMAIL_PASSWORD="your-app-password"
export RECIPIENT_EMAIL="recipient@email.com"
```

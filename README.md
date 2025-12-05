# Market PSAR Scanner V2

A technical analysis scanner that uses PRSI (PSAR on RSI) as the primary signal to identify stocks likely to move before price confirms.

## Quick Start

```bash
# Full market scan + email
python main.py

# Your portfolio only
python main.py -mystocks

# Friends watchlist
python main.py -friends

# No email, just console output
python main.py --no-email

# Set minimum market cap (in millions, default $5B)
python main.py --mc 10000  # $10B minimum
```

## Core Concept: PRSI Leads Price

**PRSI (PSAR on RSI)** applies the Parabolic SAR indicator to RSI instead of price. This creates a leading indicator that typically flips 1-3 days before the price-based PSAR.

| Signal | Meaning | Action |
|--------|---------|--------|
| PRSI Bullish ↗️ | RSI trend turning up | Look for entries |
| PRSI Bearish ↘️ | RSI trend turning down | Caution / Exit |

## Categories

### 🟢🟢 Strong Buy (Fresh Signals)
**Criteria:** PRSI bullish + Price crossed above PSAR within 5 days

These are your best opportunities - the trend just confirmed with a fresh PSAR cross.

**Sorted by:**
1. Days since PSAR cross (fewer = fresher = better)
2. OBV (green/accumulation first)
3. Checkbox count (DMI + ADX + MACD)

### 🟢 Buy (Established Trends)
**Criteria:** PRSI bullish + Price above PSAR for >5 days

Confirmed uptrends but not as fresh. Still good, just not as early.

### ⚡ Early Buy (Speculative)
**Criteria:** PRSI bullish + Price still BELOW PSAR

PRSI says "go" but price hasn't confirmed by crossing PSAR yet. Higher risk/reward.

**Sorted by:**
1. Days since PRSI flipped (fresher = better)
2. PSAR gap (less negative = closer to crossing)
3. Williams %R (more oversold = better entry)

### ⏸️ Hold (Portfolio mode only)
**Criteria:** PRSI bearish + Price still above PSAR

Pullback expected - don't add, but don't panic sell yet.

### 🔴 Sell (Portfolio mode only)
**Criteria:** PRSI bearish + Price below PSAR

Confirmed downtrend. Consider reducing position.

### 💰 Dividend Buys (Market mode only)
**Criteria:** Yield ≥2% + In a buy zone + Market cap ≥$1B

## Table Columns

| Column | Description |
|--------|-------------|
| Ticker | Stock symbol (⭐ = IBD stock, click for research) |
| Price | Current price |
| PSAR% | Gap from PSAR (+ = above, - = below) |
| Days | Days since price crossed PSAR (or PRSI flipped for Early Buy) |
| PRSI | ↗️ Bullish or ↘️ Bearish |
| OBV | 🟢 Accumulation, 🔴 Distribution, ⚪ Neutral |
| DMI | ✓ if +DI > -DI (bulls in control) |
| ADX | ✓ if ADX > 25 (strong trend) |
| MACD | ✓ if MACD > Signal (momentum up) |
| Will%R | Williams %R value (Early Buy section only) |
| Yield | Dividend yield (Dividend section only) |

## Sections by Mode

**Market Mode** (`python main.py`):
1. 🟢🟢 Strong Buy
2. 🟢 Buy  
3. ⚡ Early Buy
4. 💰 Dividends

**Portfolio Mode** (`python main.py -mystocks`):
1. 🟢🟢 Strong Buy
2. 🟢 Buy
3. ⏸️ Hold
4. 🔴 Sell
5. ⚡ Early Buy

## Checkboxes Explained

| Checkbox | Criteria | Why it matters |
|----------|----------|----------------|
| **DMI** ✓ | +DI > -DI | Bulls are in control (buying pressure > selling) |
| **ADX** ✓ | ADX > 25 | Trend is strong (not choppy sideways action) |
| **MACD** ✓ | MACD > Signal | Momentum is positive and accelerating |

More checkboxes = stronger confirmation. But a fresh PSAR cross with 0 checkboxes can still work.

## IBD Integration

Stocks on the IBD (Investor's Business Daily) lists are marked with ⭐. Click the star to open the IBD research page.

**Note:** Requires `data/ibd_utils.py` from V1 scanner.

## Files Required

Copy from V1 scanner:
- `data/ibd_utils.py` - For IBD star integration

## Environment Variables

```bash
GMAIL_EMAIL=your-email@gmail.com
GMAIL_PASSWORD=your-app-password
RECIPIENT_EMAIL=recipient@email.com
```

## Example Output

```
🟢🟢 STRONG BUY - Fresh Signals (12 stocks)
Ticker  Price   PSAR%  Days  PRSI  OBV  DMI  ADX  MACD
⭐AAPL  $195    +2.1%   2    ↗️    🟢   ✓    ✓    ✓
MSFT    $380    +1.8%   3    ↗️    🟢   ✓    ✓    ✗
...
```

# Market PSAR Scanner V2

A technical analysis scanner that uses PRSI (PSAR on RSI) as the primary signal to identify stocks likely to move before price confirms. Includes covered call suggestions, short analysis, and market sentiment indicators.

## Quick Start

```bash
# Full market scan + email
python main.py

# Your portfolio only
python main.py -mystocks

# Friends watchlist  
python main.py -friends

# Shorts watchlist (your shorts.txt)
python main.py -shorts

# Market-wide short scan
python main.py -shortscan

# No email, just console output
python main.py --no-email

# Save HTML report
python main.py --html report.html
```

## Command Line Options

| Flag | Description | Example |
|------|-------------|---------|
| `-mystocks` | Scan your portfolio (mystocks.txt) | `python main.py -mystocks` |
| `-friends` | Scan friends watchlist (friends.txt) | `python main.py -friends` |
| `-shorts` | Analyze shorts.txt for short opportunities | `python main.py -shorts` |
| `-shortscan` | Market-wide scan for best shorts | `python main.py -shortscan` |
| `--mc` | Min market cap in millions (default 5000) | `--mc 10000` ($10B) |
| `--eps` | Min EPS growth % | `--eps 15` |
| `--rev` | Min revenue growth % | `--rev 10` |
| `--adr` | Include ADR stocks | `--adr` |
| `--div` | Min dividend yield for dividend section | `--div 3.0` |
| `--tickers` | Scan specific tickers only | `--tickers AAPL,MSFT,GOOGL` |
| `--no-email` | Skip sending email | `--no-email` |
| `--html` | Save HTML report to file | `--html report.html` |
| `--skip-options` | Skip options data (if rate limited) | `--skip-options` |
| `-t, --title` | Custom email subject | `-t "Morning Scan"` |
| `--email-to` | Additional email recipient | `--email-to user@email.com` |
| `--classic` | Use V1 logic (Price PSAR primary) | `--classic` |

## Core Concept: PRSI Leads Price

**PRSI (PSAR on RSI)** applies the Parabolic SAR indicator to RSI instead of price. This creates a leading indicator that typically flips 1-3 days before the price-based PSAR.

| Signal | Meaning | Action |
|--------|---------|--------|
| PRSI Bullish ↗️ | RSI trend turning up | Look for entries |
| PRSI Bearish ↘️ | RSI trend turning down | Caution / Exit |

## Buy Categories

### 🟢🟢 Strong Buy (Fresh Signals)
**Criteria:** PRSI bullish + Price crossed above PSAR within 5 days + ADX ≥ 15

These are your best opportunities - the trend just confirmed with a fresh PSAR cross.

### 🟢 Buy (Established Trends)
**Criteria:** PRSI bullish + Price above PSAR for >5 days

Confirmed uptrends but not as fresh. Still good, just not as early.

### ⚡ Early Buy (Speculative)
**Criteria:** PRSI bullish + Price still BELOW PSAR

PRSI says "go" but price hasn't confirmed by crossing PSAR yet. Higher risk/reward. Shows Williams %R for oversold detection.

### 💰 Dividend Buys
**Criteria:** Yield ≥2% + In a buy zone + Market cap ≥$1B

Quality dividend stocks with bullish technicals.

### ⏸️ Hold (Portfolio mode only)
**Criteria:** PRSI bearish + Price still above PSAR

Pullback expected - don't add, but don't panic sell yet.

### 🔴 Sell (Portfolio mode only)
**Criteria:** PRSI bearish + Price below PSAR

Confirmed downtrend. Consider reducing position.

## Covered Calls 📞

High-ATR stocks (≥5%) get covered call suggestions with:
- **Williams %R** for timing (oversold = wait, overbought = sell calls)
- **ATR %** for volatility (higher = better premiums)
- **ADX** for trend strength (stronger = safer)
- **Delta ~0.09** targeting (~91% probability of profit)
- **2-4 week** expirations

Stocks with high ATR show a 📞 icon in the ATR column - click it to jump to the covered call recommendation.

**Trade column** includes a 📊 link to open the specific option in Fidelity.

## Short Scanning

### Shorts Watchlist Mode (`-shorts`)
Analyzes all stocks in `shorts.txt` and categorizes them:

| Category | Criteria |
|----------|----------|
| 🔴🔴 Prime Shorts | Score ≥70, ≤3 days below PSAR, Williams %R > -70 |
| 🔴 Short Candidates | Score ≥60, below PSAR, Williams %R > -80 |
| ⏳ Not Ready | Score ≥45, PRSI bearish but waiting for confirmation |
| ❌ Avoid | Doesn't meet criteria (shows why) |

### Market Short Scan Mode (`-shortscan`)
Scans entire market for best short opportunities:
- Filters to PRSI bearish + below PSAR
- Ranks by short score
- Fetches put spread recommendations for top 25

### Put Spread Recommendations
For short candidates, suggests bear put spreads:
- **Buy Put:** ~5% ITM (delta ~0.40)
- **Sell Put:** ~15% OTM (delta ~0.15)
- **Expiration:** 2-4 weeks

**Trade column** includes Fidelity links:
- 📈B = Buy Put link
- 📉S = Sell Put link

### Short Interest & Squeeze Risk
- Shows short interest % when available
- Warns about squeeze risk:
  - 🟢 LOW: SI < 15%
  - 🟡 MODERATE: SI 15-25%
  - 🔴 HIGH: SI > 25%

## Market Sentiment

### CBOE Put/Call Ratio
Fetched via Selenium from CBOE website:
- < 0.60: 🚨 High greed, correction possible
- 0.60-0.70: Bullish sentiment (normal)
- 0.70-0.90: Neutral
- 0.90-1.00: 🟢 Elevated fear - buying opportunity
- > 1.20: ✅ EXTREME FEAR - Contrarian BUY

### VIX Put/Call Ratio
From VIX options open interest:
- ≥ 1.20: 📈 CONTRARIAN BUY - Traders betting volatility falls (Bullish)
- 1.00-1.20: 🟢 Elevated VIX puts (Bullish)
- 0.80-1.00: Neutral
- 0.60-0.80: 🟡 Elevated VIX calls - hedging
- < 0.60: 🔴 Extreme VIX calls (Bearish)

## Scan Parameters Display

Each email shows the filters used:
```
🔍 Scan Filters: Market Cap ≥ $5B | EPS Growth ≥ 15% | Dividend ≥ 2.0%
```

## Table Columns

| Column | Description |
|--------|-------------|
| Ticker | Stock symbol (⭐ = IBD stock) |
| Price | Current price |
| PSAR% | Gap from PSAR (+ = above, - = below) |
| Days | Days since PSAR cross (or PRSI flip for Early Buy) |
| PRSI | ↗️ Bullish or ↘️ Bearish |
| OBV | 🟢 Accumulation, 🔴 Distribution, ⚪ Neutral |
| DMI | ✓ if +DI > -DI (bulls in control) |
| ADX | ✓ if ADX > 25 (strong trend) |
| MACD | ✓ if MACD > Signal |
| ATR% | Average True Range % (📞 if ≥5% = covered call candidate) |
| Will%R | Williams %R (-100 to 0, lower = more oversold) |
| Yield | Dividend yield % |

## GitHub Actions

Automated scans via GitHub Actions workflow (`.github/workflows/v2-scanner.yml`):

| Schedule (EST) | Scan Type |
|----------------|-----------|
| 9:35 AM | Market scan |
| 10:30 AM | Short scan |
| 4:05 PM | Portfolio scan |

Manual triggers available with customizable:
- Scan type (market, mystocks, friends, shorts, shortscan)
- Market cap filter
- EPS/Revenue growth filters
- Include ADR toggle
- Custom title
- Extra email recipient

### Setup
1. Add workflow file to `main` branch
2. Add secrets in GitHub repo settings:
   - `GMAIL_EMAIL`
   - `GMAIL_PASSWORD`
   - `RECIPIENT_EMAIL`

## Data Files

| File | Purpose |
|------|---------|
| `mystocks.txt` | Your portfolio tickers (one per line) |
| `friends.txt` | Friends watchlist tickers |
| `shorts.txt` | Shorts watchlist tickers |
| `data_files/short_interest.csv` | Manual short interest overrides |

### short_interest.csv format
```csv
ticker,short_percent
GME,25.5
AMC,18.2
```

## Environment Variables

```bash
GMAIL_EMAIL=your-email@gmail.com
GMAIL_PASSWORD=your-app-password  # Use Gmail App Password
RECIPIENT_EMAIL=recipient@email.com
```

## Requirements

```
yfinance
pandas
numpy
ta
requests
selenium
webdriver-manager
openpyxl
lxml
beautifulsoup4
```

Install: `pip install -r requirements.txt`

## Architecture

```
market_scanner_v2/
├── main.py                 # Entry point, email builder
├── scanners/
│   ├── base_scanner.py     # Core scanning logic
│   ├── smart_buy.py        # Buy signal detection
│   └── smart_short.py      # Short signal detection
├── indicators/
│   ├── prsi.py            # PSAR on RSI (primary signal)
│   ├── psar.py            # Price PSAR
│   ├── obv.py             # On-Balance Volume
│   ├── momentum.py        # DMI, ADX, MACD
│   └── atr.py             # Average True Range
├── analysis/
│   ├── covered_calls.py   # Covered call suggestions
│   └── shorts.py          # Short analysis & put spreads
├── signals/
│   ├── zone_classifier.py # Buy/Sell zone logic
│   └── warnings.py        # Risk warnings
├── data/
│   ├── cboe.py           # CBOE put/call ratio
│   └── ibd_utils.py      # IBD list integration
└── utils/
    └── config.py         # Configuration constants
```

## Version History

### V2 (Current)
- PRSI as primary signal (leads price)
- Covered call suggestions with Williams %R timing
- Short scanning with put spread recommendations
- VIX Put/Call Ratio sentiment
- CBOE Put/Call Ratio sentiment
- Fidelity trade links for options
- Scan parameters display
- GitHub Actions automation
- ADX threshold for Strong Buys

### V1 (Classic)
- Price PSAR as primary signal
- Basic buy/sell zones
- Use `--classic` flag to enable

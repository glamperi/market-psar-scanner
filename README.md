# Market PSAR Scanner V2

A technical analysis scanner that uses PRSI (PSAR on RSI) as the primary signal to identify stocks likely to move before price confirms. Includes covered call suggestions, short analysis, and market sentiment indicators.

## Quick Start

**Use `main.py` for all scanning** (V2 format with Days/DMI/ADX/MACD):

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

# Quick single ticker lookup (market_scanner.py only)
python market_scanner.py -lookup AAPL
```

## Command Line Options

### main.py Options
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

### market_scanner.py Additional Options
| Flag | Description | Example |
|------|-------------|---------|
| `-lookup TICKER` | Quick lookup single ticker (no email) | `python market_scanner.py -lookup AAPL` |
| `-experiment` | Enable experimental features | `python market_scanner.py -mystocks -experiment` |

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

**Trade column** includes:
- **📊 Trade** = Opens in [OptionStrat](https://optionstrat.com) for P&L analysis
- **F-SellC** = Fidelity P&L calculator link for the sell call

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

**Trade column** includes:
- **📊 Trade** = Opens in [OptionStrat](https://optionstrat.com) for P&L analysis
- **F-BuyP** = Fidelity link for buy put leg
- **F-SellP** = Fidelity link for sell put leg

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
| Mom | PSAR Momentum (1-10) - trend strength/trajectory |
| PRSI | ↗️ Bullish or ↘️ Bearish |
| OBV | 🟢 Accumulation, 🔴 Distribution, ⚪ Neutral |
| DMI | ✓ if +DI > -DI (bulls in control) |
| ADX | ✓ if ADX > 25 (strong trend) |
| MACD | ✓ if MACD > Signal |
| ATR% | Average True Range % (📞 if ≥5% = covered call candidate) |
| Will%R | Williams %R (-100 to 0, lower = more oversold) |
| Yield | Dividend yield % |

### Momentum Interpretation (V2)

| Mom | Meaning | Action |
|-----|---------|--------|
| 1-3 | Weak/Capitulating | Avoid (or watch for bounce) |
| 4 | Stabilizing | Watch for PRSI flip |
| **5-7✨** | **Accelerating** | **Best entry zone** |
| 8-9🔥 | Strong but late | Good if PRSI confirms |
| 10⏸️ | Exhausted | HOLD only, no new entries |

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
# Email (required)
GMAIL_EMAIL=your-email@gmail.com
GMAIL_PASSWORD=your-app-password  # Use Gmail App Password
RECIPIENT_EMAIL=recipient@email.com

# Schwab API - Option A: schwabdev library (recommended)
# Just run initial_auth() once, tokens saved to tokens.json

# Schwab API - Option B: Environment variables
SCHWAB_CLIENT_ID=your-client-id
SCHWAB_CLIENT_SECRET=your-client-secret
SCHWAB_REFRESH_TOKEN=your-refresh-token
```

**Note:** Schwab credentials are optional. Without them, the scanner uses yfinance for options data.

## Options Data Sources

The scanner fetches options data for covered calls and put spreads using a fallback chain in `utils/options_data.py`:

| Priority | Source | Notes |
|----------|--------|-------|
| 1 | **Schwab API** | Most reliable, includes Greeks (delta). Requires developer account. |
| 2 | **yfinance** | Default free option. May be rate limited. |
| 3 | **Yahoo HTML scrape** | Fallback when yfinance fails. |
| 4 | **Yahoo Selenium** | Handles consent pages (disabled by default). |

### Schwab API Setup

**Option A: Using schwabdev library (recommended)**
```bash
pip install schwabdev
```

1. Sign up at https://developer.schwab.com
2. Create an application (callback URL: `https://127.0.0.1`)
3. Run initial auth to get tokens:
```python
from data.schwab_options import initial_auth
initial_auth()  # Opens browser for OAuth flow
```
4. Tokens saved to `tokens.json` - auto-refreshes

**Option B: Using environment variables**
```bash
export SCHWAB_CLIENT_ID=your-client-id
export SCHWAB_CLIENT_SECRET=your-client-secret  
export SCHWAB_REFRESH_TOKEN=your-refresh-token
```

### Fallback Behavior

If Schwab credentials are not set or API fails:
- Scanner automatically falls back to yfinance
- If yfinance rate limited, falls back to Yahoo scraping
- No configuration needed - just works with degraded reliability

### GitHub Actions

For CI/CD, Schwab is optional. The scanner works fine with yfinance:
- Don't add Schwab secrets to GitHub → uses yfinance automatically
- Add secrets if you want more reliable options data in CI

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
schwabdev          # Optional - for Schwab API
```

Install: `pip install -r requirements.txt`

**Note:** `schwabdev` is optional. Without it, options data comes from yfinance.

## Architecture

```
market-psar-scanner/
├── main.py                 # V2 Entry point - PRSI primary, Days/DMI/ADX/MACD format
├── market_scanner.py       # Alternative scanner - Mom/IR/Indicators format
├── indicators.py           # Technical indicator calculations
├── signals.py              # Zone classification logic
├── scanners.py             # Scanner classes (SmartBuyScanner, etc.)
├── analysis/
│   ├── covered_calls.py    # Covered call suggestions with trade links
│   └── shorts.py           # Short analysis & put spreads
├── reports/
│   ├── portfolio_report.py # Portfolio HTML builder (used by market_scanner.py)
│   └── shorts_report.py    # Shorts HTML builder
├── data/
│   ├── cboe.py             # CBOE put/call ratio (Selenium)
│   ├── ibd_utils.py        # IBD list integration
│   └── schwab_options.py   # Schwab API client (optional)
├── utils/
│   └── options_data.py     # Unified options fetcher (Schwab → yfinance → Yahoo)
└── data_files/
    ├── mystocks.txt        # Your portfolio tickers
    ├── friends.txt         # Friends watchlist
    ├── shorts.txt          # Shorts watchlist
    └── short_interest.csv  # Manual short interest overrides
```

### Two Scanner Systems

| System | Command | Format | Best For |
|--------|---------|--------|----------|
| **main.py** (V2) | `python main.py -mystocks` | Days/PRSI/OBV/DMI/ADX/MACD/ATR% | Primary use |
| **market_scanner.py** | `python market_scanner.py -mystocks` | Mom/ATR/PRSI/OBV/IR/Indicators | Alternative view |

Both support `-mystocks`, `-friends`, `-shorts`, `-shortscan` flags.

## Version History

### V2.1 (Current)
- **Schwab API integration** for reliable options data
- **OptionStrat trade links** for P&L visualization
- **Fidelity trade links** for covered calls and put spreads
- Unified options fetcher (`utils/options_data.py`) with fallback chain
- Deep ITM put suggestions for shorts
- Dual scanner system (main.py + market_scanner.py)

### V2
- PRSI as primary signal (leads price)
- Covered call suggestions with Williams %R timing
- Short scanning with put spread recommendations
- VIX Put/Call Ratio sentiment
- CBOE Put/Call Ratio sentiment
- Scan parameters display
- GitHub Actions automation
- ADX threshold for Strong Buys

### V1 (Classic)
- Price PSAR as primary signal
- Basic buy/sell zones
- Use `--classic` flag to enable

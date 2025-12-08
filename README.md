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

Zone classification is based on **effective PSAR distance** (% from PSAR, adjusted by momentum):

| Zone | Criteria |
|------|----------|
| 🟢🟢 STRONG_BUY | PSAR distance > +5% |
| 🟢 BUY | PSAR distance ≥ +2% |
| 🟡 NEUTRAL | PSAR distance ≥ -2% |
| 🟠 WEAK | PSAR distance ≥ -5% |
| 🔴 SELL | PSAR distance < -5% |

**Momentum adjustment:** 
- Bearish stocks with strong momentum (≥7) get +2% boost (recovering)
- Bullish stocks with weak momentum (≤3) get -1% penalty (fading)

### 🟢🟢 Strong Buy
Price is >5% above PSAR - strong confirmed uptrend with cushion.

### 🟢 Buy
Price is 2-5% above PSAR - confirmed uptrend.

### ⚡ Early Buy (Speculative)
**Criteria:** PRSI bullish + Price still BELOW PSAR

PRSI says "go" but price hasn't confirmed by crossing PSAR yet. Higher risk/reward. Shows Williams %R for oversold detection.

### 💰 Dividend Buys
**Criteria:** Yield ≥2% + In a buy zone + Market cap ≥$1B

Quality dividend stocks with bullish technicals.

### 🟡 Neutral / ⏸️ Hold
Price is within ±2% of PSAR - no clear direction. Wait for confirmation.

### 🟠 Weak
Price is 2-5% below PSAR - downtrend starting but not severe.

### 🔴 Sell
Price is >5% below PSAR - confirmed downtrend. Consider reducing position.

## Sorting Within Zones

Within each zone, stocks are sorted by **confirmation strength** (not IR score):

| Priority | Indicator | What it means |
|----------|-----------|---------------|
| 1 | Days since signal | Day 1 first, Day 2 second, etc. |
| 2 | OBV CONFIRM | Volume confirms price direction |
| 3 | PRSI bullish | RSI trend is up |
| 4 | MACD bullish | MACD > Signal line |
| 5 | Above 50MA | Price above 50-day moving average |

**Why this order?**
- Fresh signals (Day 1-2) are most actionable
- OBV confirms institutional money flow
- PRSI leads price by 1-3 days
- MACD and 50MA provide additional confirmation

> **Note:** The classic `-classic` mode uses IR scoring instead. See the IR Score section in Table Columns.

## Covered Calls 📞

High-ATR stocks (≥5%) get covered call suggestions with:
- **Williams %R** for timing (oversold = wait, overbought = sell calls)
- **ATR %** for volatility (higher = better premiums)
- **ADX** for trend strength (stronger = safer)
- **Delta ~0.09** targeting (~91% probability of profit)
- **2-4 week** expirations

Stocks with high ATR show a 📞 icon in the ATR column - click it to jump to the covered call recommendation.

**Trade column** includes clickable links:
- **📊 Trade** = Opens in OptionStrat with pre-filled covered call (100 shares + sell call) for P&L analysis
- **F-SellC** = Fidelity P&L calculator for the sell call leg

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

**Trade column** includes clickable links:
- **📊 Trade** = Opens in OptionStrat with pre-filled bear put spread for P&L analysis
- **F-BuyP** = Fidelity P&L calculator for the buy put leg
- **F-SellP** = Fidelity P&L calculator for the sell put leg

> **Note:** OptionStrat does not integrate with brokers for execution. Use it to visualize the trade, then enter manually at your broker.

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

All data files are stored in the `data_files/` directory:

| File | Purpose |
|------|---------|
| `data_files/mystocks.txt` | Your portfolio tickers (one per line) |
| `data_files/friends.txt` | Friends watchlist tickers |
| `data_files/shorts.txt` | Shorts watchlist tickers |
| `data_files/custom_watchlist.txt` | Priority watchlist for market scans |
| `data_files/short_interest.csv` | Manual short interest overrides |
| `data_files/sp500_tickers.csv` | S&P 500 ticker list |
| `data_files/nasdaq100_tickers.csv` | NASDAQ 100 ticker list |
| `data_files/russell2000_tickers.csv` | Russell 2000 ticker list |
| `data_files/ibd_*.csv` | IBD stock lists (50, BigCap20, Sector, IPO, Spotlight) |

### short_interest.csv format
```csv
Symbol,ShortPercent,DaysToCover
GME,25.5,2.1
AMC,18.2,1.5
```

> **Note:** Short interest data from yfinance may be unavailable on GitHub Actions due to rate limiting. Add stocks to this CSV for manual overrides.

## Environment Variables

```bash
# Email (required)
GMAIL_EMAIL=your-email@gmail.com
GMAIL_PASSWORD=your-app-password  # Use Gmail App Password
RECIPIENT_EMAIL=recipient@email.com

# Schwab API (optional - for reliable options data)
SCHWAB_CLIENT_ID=your-client-id
SCHWAB_CLIENT_SECRET=your-client-secret
SCHWAB_REFRESH_TOKEN=your-refresh-token
```

## Options Data Sources

The scanner fetches options data for covered calls and put spreads using a fallback chain:

| Priority | Source | Notes |
|----------|--------|-------|
| 1 | Schwab API | Most reliable, requires developer account |
| 2 | yfinance | Default, may be rate limited on GitHub Actions |
| 3 | Yahoo HTML scrape | Fallback when yfinance fails |

### Schwab API Setup (Recommended)

Schwab API provides reliable options data without rate limiting. Setup steps:

1. **Create Developer Account**
   - Go to https://developer.schwab.com
   - Sign up with your Schwab brokerage credentials
   - Wait for approval (may take 1-2 business days)

2. **Create an Application**
   - In the developer portal, create a new app
   - Set callback URL to `https://127.0.0.1:8000/callback`
   - Note your **Client ID** and **Client Secret**

3. **Complete OAuth Flow**
   - Run the OAuth helper script to get your refresh token:
   ```bash
   python utils/schwab_oauth.py
   ```
   - Follow the browser prompts to authorize
   - Copy the **Refresh Token** that's generated

4. **Configure Environment**
   ```bash
   # Add to .env file or export in shell
   export SCHWAB_CLIENT_ID="your-client-id"
   export SCHWAB_CLIENT_SECRET="your-client-secret"
   export SCHWAB_REFRESH_TOKEN="your-refresh-token"
   ```

5. **For GitHub Actions**, add these as repository secrets:
   - `SCHWAB_CLIENT_ID`
   - `SCHWAB_CLIENT_SECRET`
   - `SCHWAB_REFRESH_TOKEN`

If Schwab credentials are not set, the scanner automatically falls back to yfinance, then Yahoo scraping.

### Rate Limiting Notes

- **yfinance** works well locally but GitHub Actions IPs are often rate-limited by Yahoo
- **Short interest data** also comes from yfinance and may show "-" on GitHub Actions
- For reliable CI/CD runs, Schwab API is strongly recommended

## Trade Links (OptionStrat & Fidelity)

The scanner generates clickable trade links for options strategies:

### OptionStrat Links
Opens pre-filled strategies in [OptionStrat](https://optionstrat.com) for:
- P&L diagram visualization
- Greeks analysis
- Probability calculations
- What-if scenarios

**URL Formats:**
```
# Bear Put Spread
https://optionstrat.com/build/bear-put-spread/MRK/-251219P85,251219P105

# Covered Call
https://optionstrat.com/build/covered-call/MRK/MRKx100,-.MRK251219C110

# Long Put
https://optionstrat.com/build/long-put/MRK/251219P105
```

### Fidelity P&L Links
Opens Fidelity's Profit & Loss Calculator for individual legs:
- **F-BuyP** = Buy put leg
- **F-SellP** = Sell put leg  
- **F-SellC** = Sell call leg (covered calls)

> **Note:** Neither OptionStrat nor Fidelity P&L links execute trades directly. Use them to analyze, then enter trades manually at your broker.

## Virtual Environment Setup

A virtual environment (venv) isolates Python packages for this project. This is **required** on macOS which blocks system-wide pip installs.

### Create and Activate venv

```bash
# Navigate to project directory
cd ~/Dev/Python/Investing/market-psar-scanner

# Create virtual environment
python3 -m venv venv

# Activate it (do this each session)
source venv/bin/activate

# Your prompt will show (venv) when active
(venv) $ python3 market_scanner.py -mystocks

# Deactivate when done
deactivate
```

### Install Dependencies

```bash
# With venv activated
pip install -r requirements.txt
```

### Why venv?

| Without venv | With venv |
|--------------|-----------|
| macOS blocks `pip install` | `pip install` works |
| Version conflicts between projects | Isolated packages per project |
| Hard to replicate setup | `requirements.txt` recreates exact setup |

> **Tip:** GitHub Actions automatically creates its own venv from `requirements.txt`, so CI works without manual setup.

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

Install (with venv activated): `pip install -r requirements.txt`

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

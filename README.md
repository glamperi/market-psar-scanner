# PSAR Market Scanner

A stock market scanner that tells you what to BUY and SELL based on trend analysis.

## Quick Reference

| Zone | Meaning | Action |
|------|---------|--------|
| 🟢🟢🟢 TOP TIER | Best opportunities | BUY with confidence |
| 🟢🟢 STRONG BUY | Strong uptrend | BUY / Hold |
| 🟢 BUY | Healthy uptrend | Hold / Watch |
| 🟡 NEUTRAL | Could go either way | Watch closely |
| 🟠 WEAK | Downtrend, might reverse | Caution / Covered calls |
| 🔴 SELL | Confirmed downtrend | Exit or hedge |

| Indicator | What It Tells You |
|-----------|-------------------|
| **PSAR %** | Trend strength (+5% = strong up, -5% = strong down) |
| **Momentum (1-10)** | Is trend strengthening (8-10) or weakening (1-4)? |
| **IR (0-100)** | How many indicators confirm the signal? (40+ = good) |
| **OBV** | Is volume confirming? (🟢=yes, 🔴=warning) |

## Table of Contents
- [Overview](#overview)
- [Technical Methodology](#technical-methodology)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [File Formats](#file-formats)
- [GitHub Actions Setup](#github-actions-setup)
- [Understanding the Reports](#understanding-the-reports)

---

## Overview

This scanner analyzes ~2,500 stocks from:
- S&P 500 (503 stocks)
- NASDAQ 100 (100 stocks)
- Russell 2000 (~2000 stocks)
- IBD (Investor's Business Daily) growth stocks

**Default filter:** $10B+ market cap (configurable with `-mc` flag)

The scanner classifies stocks into **PSAR Zones** based on:
1. **Trend direction** (up or down)
2. **Trend strength** (how far from the flip point)
3. **Momentum** (strengthening or weakening)
4. **Confirmation** (do other indicators agree?)

---

## Technical Methodology

### The Big Picture: What This Scanner Does

The scanner answers one question: **"Which stocks should I buy or sell right now?"**

It uses a **traffic light system**:
- 🟢 **Green zones** = BUY territory (price trending UP)
- 🟡 **Yellow zone** = NEUTRAL (could go either way)
- 🔴 **Red zones** = SELL territory (price trending DOWN)

---

### Core Indicator: Parabolic SAR (PSAR)

**What is PSAR?**

PSAR (Parabolic Stop and Reverse) is a trend-following indicator that tells you:
- **Is the stock going UP or DOWN?**
- **How strong is the trend?**

Think of PSAR as a "trailing stop" that follows price. When price crosses the PSAR line, the trend has reversed.

**PSAR Distance** = How far price is from the PSAR line (as a percentage)
- **Positive (+5%)** = Price is ABOVE PSAR = Uptrend = BULLISH
- **Negative (-5%)** = Price is BELOW PSAR = Downtrend = BEARISH
- **Near zero** = Trend is weak, could flip either way

---

### PSAR Zones Explained

**Zones classify stocks by trend strength:**

| Zone | PSAR Distance | What It Means | What To Do |
|------|---------------|---------------|------------|
| 🟢🟢🟢 **TOP TIER** | > +5% | Everything is perfect - strong uptrend, volume confirms, indicators agree | **Best buys** - highest conviction |
| 🟢🟢 **STRONG BUY** | > +5% | Confirmed uptrend, price well above PSAR | **Buy** - hold existing, add on dips |
| 🟢 **BUY** | +2% to +5% | Healthy uptrend, but not as strong | **Hold** - watch for strengthening |
| 🟡 **NEUTRAL** | -2% to +2% | Trend is weak, sitting on the fence | **Watch closely** - could break either way |
| 🟠 **WEAK** | -5% to -2% | Downtrend, but might reverse soon | **Caution** - consider covered calls, tight stops |
| 🔴 **SELL** | < -5% | Confirmed downtrend, price well below PSAR | **Exit or hedge** - don't fight the trend |

**Simple rule:** Green = good, Red = bad, Yellow = be careful.

---

### Momentum Score (1-10): Is the Trend Getting Stronger or Weaker?

**The Problem:** A stock might be in the "STRONG BUY" zone today, but is it getting stronger or about to fall?

**The Solution:** Momentum Score compares where the stock was when the signal started vs. where it is now.

**Example:**
```
Stock ABC started a BUY signal 30 days ago at +3% PSAR distance.
Today it's at +8% PSAR distance.
→ It's STRENGTHENING → Momentum = 8-9 (high)

Stock XYZ started a BUY signal 30 days ago at +10% PSAR distance.  
Today it's at +6% PSAR distance.
→ It's WEAKENING → Momentum = 3-4 (low)
```

| Momentum Score | Meaning |
|----------------|---------|
| **8-10** | Trend is **strengthening** - best signals |
| **5-7** | Trend is **stable** - normal |
| **1-4** | Trend is **weakening** - be cautious |

**For SELL zones, momentum works in reverse:**
- High momentum (7-10) = Improving, might flip to BUY soon
- Low momentum (1-3) = Getting worse, stay away

---

### Indicator Rating (IR): Do Other Indicators Agree?

**The Problem:** PSAR alone can give false signals. We want confirmation from other indicators.

**The Solution:** IR adds up points from 5 different indicators (max 100 points):

| Indicator | Points | What It Detects |
|-----------|--------|-----------------|
| **MACD** | +30 | Momentum shifting bullish |
| **Ultimate Oscillator** | +30 | Stock is oversold (good time to buy) |
| **Williams %R** | +20 | Stock is oversold |
| **Bollinger Bands** | +10 | Price at lower band (support) |
| **Coppock Curve** | +10 | Long-term momentum turning up |

**How to read IR:**
- **IR = 0-20**: No confirmation - PSAR signal alone
- **IR = 30-40**: Some confirmation - 1-2 indicators agree
- **IR = 50+**: Strong confirmation - multiple indicators agree

**For Top Tier, we require IR ≥ 40** (at least 2 strong indicators confirming the buy signal).

---

### OBV (On-Balance Volume): Is "Smart Money" Buying?

**The Problem:** Price can rise on low volume, which often fails. We want volume to confirm the move.

**The Solution:** OBV tracks whether volume is flowing IN or OUT of a stock.

| OBV Status | Display | Meaning |
|------------|---------|---------|
| **CONFIRM** | 🟢 | Volume rising with price - institutions are buying |
| **NEUTRAL** | 🟡 | Volume flat - no strong conviction either way |
| **DIVERGE** | 🔴 | Volume FALLING while price rising - **WARNING!** |

**Why 🔴 OBV matters:**
- Price going up but volume going down = "weak rally"
- Often means smart money is selling into strength
- Rally could fail soon
- **A 🔴 OBV disqualifies a stock from Top Tier**

---

### Top Tier: The Best of the Best

A stock qualifies for **Top Tier** only if ALL of these are true:

| Criteria | Why It Matters |
|----------|----------------|
| PSAR Distance > +5% | Strong uptrend |
| Momentum Score ≥ 7 | Trend is strengthening |
| IR ≥ 40 | At least 2 indicators confirm |
| Above 50-day MA | Healthy trend structure |
| OBV = 🟢 | Volume confirms the move |

**If any one criteria fails, stock drops to "Strong Buy" instead of "Top Tier".**

---

### IBD Integration

Stocks marked with ⭐ are from Investor's Business Daily lists:
- High-quality growth stocks
- Strong fundamentals (EPS, RS ratings)
- IBD stocks bypass the market cap filter

IBD provides Composite/EPS/RS ratings (1-99 scale):
- **Composite**: Overall IBD rating
- **EPS**: Earnings strength
- **RS**: Relative Strength vs market
- 80+ is considered strong

---

## Installation

### Prerequisites
```bash
pip install yfinance pandas ta smtplib --break-system-packages
```

### Required Files
```
market_scanner/
├── market_scanner.py      # Main scanner
├── email_report.py        # Market-wide email report
├── portfolio_report.py    # Portfolio-specific report
├── config.py              # Configuration
├── sp500_tickers.csv      # S&P 500 list
├── nasdaq100_tickers.csv  # NASDAQ 100 list
├── russell2000_tickers.csv # Russell 2000 list
├── ibd_stats.csv          # IBD ratings (optional)
├── custom_watchlist.txt   # Your priority watchlist
├── mystocks.txt           # Your portfolio tickers
├── mypositions.csv        # Your position values
└── friends.txt            # Friend's portfolio
```

---

## Configuration

### Environment Variables

Set these in your environment or `.env` file:

```bash
export GMAIL_EMAIL="your.email@gmail.com"
export GMAIL_PASSWORD="your-app-password"
export RECIPIENT_EMAIL="recipient@example.com"
```

**Gmail App Password Setup:**
1. Go to Google Account → Security
2. Enable 2-Factor Authentication
3. Go to App Passwords
4. Generate a new app password for "Mail"
5. Use this 16-character password (not your regular password)

### config.py

```python
# Email settings (can also use env vars)
GMAIL_EMAIL = "your.email@gmail.com"
GMAIL_PASSWORD = "xxxx-xxxx-xxxx-xxxx"
RECIPIENT_EMAIL = "you@example.com"

# Scanner settings
MARKET_CAP_MIN = 10_000_000_000  # $10B minimum
SCAN_PERIOD = "6mo"              # Historical data period
```

---

## Usage

### Full Market Scan
```bash
python market_scanner.py
```
Scans ~2,500 stocks, filters to $10B+ market cap, emails report.

### Your Portfolio Only
```bash
python market_scanner.py -mystocks
```
Scans only tickers in `mystocks.txt`, uses position values from `mypositions.csv`.

### Friend's Portfolio
```bash
python market_scanner.py -friends -t "Edward's Stocks" -e "edward@gmail.com"
```
- `-friends`: Use `friends.txt` ticker list
- `-t "Title"`: Custom report title
- `-e "email"`: Send copy to additional email

### Command Line Options

| Flag | Description | Example |
|------|-------------|---------|
| `-mystocks` | Scan only mystocks.txt | `python market_scanner.py -mystocks` |
| `-friends` | Scan only friends.txt | `python market_scanner.py -friends` |
| `-shorts` | Scan only shorts.txt (short candidates) | `python market_scanner.py -shorts` |
| `-shortscan` | Full market scan for short candidates | `python market_scanner.py -shortscan -mc 5` |
| `-t "Title"` | Custom report title (with -friends) | `-t "Edward's Stocks"` |
| `-e "email"` | Additional email recipient | `-e "friend@gmail.com"` |
| `-mc 5` | Min market cap in billions (default: 10) | `-mc 1` for $1B+ |
| `-eps 20` | Filter: EPS growth ≥ 20% | `-eps 25` |
| `-rev 15` | Filter: Revenue growth ≥ 15% | `-rev 10` |
| `-adr` | Include international ADRs | `-adr` |

### Market Cap Filter

```bash
# Default: $10B+ market cap
python market_scanner.py

# Smaller companies: $1B+
python market_scanner.py -mc 1

# Mid-cap: $5B+
python market_scanner.py -mc 5

# Mega-cap only: $100B+
python market_scanner.py -mc 100
```

### International ADRs

Include ~130 major international companies (American Depositary Receipts):

```bash
# Add international stocks to the scan
python market_scanner.py -adr

# Combine with market cap filter
python market_scanner.py -mc 1 -adr

# Full scan with all options
python market_scanner.py -mc 5 -adr -eps 10 -rev 10
```

**ADRs included:** BABA, JD, PDD, NIO (China), TSM (Taiwan), TM, SONY (Japan), INFY, HDB (India), VALE, NU, MELI (Latin America), BP, SHEL, AZN, ASML, NVO (Europe), and ~100 more.

You can also create `adr_tickers.csv` with a `Symbol` column to use your own custom ADR list.

### Growth Filters

Filter to only show stocks with strong growth estimates:

```bash
# Only stocks with 20%+ EPS growth expected
python market_scanner.py -eps 20

# Only stocks with 15%+ revenue growth expected  
python market_scanner.py -rev 15

# Combine both filters
python market_scanner.py -eps 20 -rev 15

# Apply to friends list
python market_scanner.py -friends -t "High Growth Picks" -eps 25
```

**Note:** Growth data comes from Yahoo Finance analyst estimates. Not all stocks have estimates available - those without data are filtered out when using these flags.

### Short Candidates

Two ways to find short candidates:

**Option 1: Watchlist scan (`-shorts`)**

Scan your own list of potential shorts in `shorts.txt`:

```bash
python market_scanner.py -shorts
```

Create a `shorts.txt` file with tickers you're considering shorting:

```
# Potential short candidates
BYND
IREN
CIFR
# Meme stocks
GME
AMC
```

**Option 2: Market-wide scan (`-shortscan`)**

Scan the entire market and find all stocks in SELL zones:

```bash
# Scan market for short candidates ($5B+ market cap)
python market_scanner.py -shortscan -mc 5

# Include international ADRs
python market_scanner.py -shortscan -mc 5 -adr

# Smaller companies
python market_scanner.py -shortscan -mc 1 -adr
```

**Short Score Components (max 100 points):**

| Factor | Points | Why It Matters |
|--------|--------|----------------|
| Deep SELL zone (PSAR < -5%) | +25 | Confirmed downtrend |
| Below 50-day MA | +15 | Bearish structure |
| Low momentum (1-4) | +20 | Still deteriorating |
| OBV confirms downtrend | +15 | Volume supports the drop |
| Negative EPS growth | +15 | Fundamental weakness |
| Low short interest (<5%) | +10 | Trade not crowded |

**Penalties (avoid these):**

| Warning | Penalty | Risk |
|---------|---------|------|
| High short interest (>25%) | -30 | 🔴 SQUEEZE RISK |
| High momentum (7+) | -20 | Trend improving |
| RSI oversold (<30) | -15 | Bounce risk |
| In BUY zone | -20 | Wrong direction |

**Squeeze Risk Levels:**
- 🟢 Low (<15% SI) - Safe to short
- 🟡 Moderate (15-25% SI) - Caution
- 🔴 High (>25% SI) - SQUEEZE RISK!

**Ideal Short Candidate:**
- Score ≥ 50
- In SELL zone (PSAR < -2%)
- Low short interest (<15%)
- Below 50-day MA
- Low momentum (trend still weakening)

**OTC Stock Short Interest:**

For OTC stocks (like MTPLF, TSWCF), yfinance often doesn't have short interest data. The scanner uses multiple fallback sources:

1. **short_interest.csv** (manual override - most reliable)
2. **FINRA API** (automatic fallback for OTC stocks)
3. **yfinance** (works for most exchange-listed stocks)

**Manual Override (Recommended for OTC):**

Create a `short_interest.csv` file with your own data:

```csv
Symbol,ShortPercent,DaysToCover
MTPLF,5.2,3.21
TSWCF,2.5,1.8
```

Get short interest data from:
- [Benzinga](https://www.benzinga.com/quote/MTPLF/short-interest)
- [Fintel](https://fintel.io/ss/us/mtplf)
- [OTC Markets](https://www.otcmarkets.com/stock/MTPLF/security)

Note: Short interest is published twice monthly, so data may be up to 2 weeks old.

---

## File Formats

### Ticker Lists (custom_watchlist.txt, mystocks.txt, friends.txt, shorts.txt)

Simple text file, one ticker per line:
```
# Comments start with #
AAPL
MSFT
GOOGL
NVDA
# Bitcoin plays
MSTR
FBTC
```

### mypositions.csv

CSV with Symbol and Value columns:
```csv
Symbol,Value
FBTC,1785541.39
META,66720.92
NVDA,58598.20
MSFT,22115.83
```

Used to show position sizes in portfolio reports and identify concentrated positions (>$10K).

### short_interest.csv

Manual override for short interest data (useful for OTC stocks):
```csv
Symbol,ShortPercent,DaysToCover
MTPLF,5.2,3.21
TSWCF,2.5,1.8
BYND,25.3,4.5
```

Fields:
- **Symbol**: Ticker symbol
- **ShortPercent**: Short interest as % of float (e.g., 5.2 = 5.2%)
- **DaysToCover**: Days to cover (short ratio)

This file takes priority over yfinance and FINRA data.

### sp500_tickers.csv

Single column with header:
```csv
Symbol
AAPL
MSFT
GOOGL
...
```

### ibd_stats.csv

IBD ratings export:
```csv
Symbol,Composite,EPS,RS,SMR
NVDA,99,99,98,A
AAPL,85,92,78,B
...
```

**How to update IBD list:**
1. Export from IBD MarketSmith or IBD website
2. Ensure columns: Symbol, Composite, EPS, RS, SMR
3. Save as `ibd_stats.csv`

---

## GitHub Actions Setup

### Basic Workflow (.github/workflows/scanner.yml)

```yaml
name: PSAR Market Scanner

on:
  schedule:
    # Run at 9:30 AM and 4:30 PM ET (market open/close)
    - cron: '30 13 * * 1-5'  # 9:30 AM ET
    - cron: '30 20 * * 1-5'  # 4:30 PM ET
  workflow_dispatch:  # Manual trigger

jobs:
  scan:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install yfinance pandas ta
    
    - name: Run Scanner
      env:
        GMAIL_EMAIL: ${{ secrets.GMAIL_EMAIL }}
        GMAIL_PASSWORD: ${{ secrets.GMAIL_PASSWORD }}
        RECIPIENT_EMAIL: ${{ secrets.RECIPIENT_EMAIL }}
      run: |
        python market_scanner.py
    
    - name: Save exit history
      uses: actions/upload-artifact@v3
      with:
        name: exit-history
        path: exit_history.json
```

### Advanced Workflow with Manual Flag Selection

This version lets you choose scan options when triggering manually:

```yaml
name: PSAR Market Scanner (Advanced)

on:
  schedule:
    - cron: '30 13 * * 1-5'  # 9:30 AM ET
    - cron: '30 20 * * 1-5'  # 4:30 PM ET
  workflow_dispatch:
    inputs:
      scan_type:
        description: 'Scan type'
        required: true
        default: 'market'
        type: choice
        options:
          - market
          - mystocks
          - friends
      market_cap:
        description: 'Min market cap in billions (e.g., 1, 5, 10)'
        required: false
        default: '10'
      include_adr:
        description: 'Include international ADRs'
        required: false
        default: false
        type: boolean
      eps_growth:
        description: 'Min EPS growth % (leave empty to skip)'
        required: false
        default: ''
      rev_growth:
        description: 'Min revenue growth % (leave empty to skip)'
        required: false
        default: ''
      extra_email:
        description: 'Additional email recipient'
        required: false
        default: ''
      report_title:
        description: 'Custom report title (for friends mode)'
        required: false
        default: ''

jobs:
  scan:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install yfinance pandas ta
    
    - name: Build command
      id: build_cmd
      run: |
        CMD="python market_scanner.py"
        
        # Scan type
        if [ "${{ github.event.inputs.scan_type }}" == "mystocks" ]; then
          CMD="$CMD -mystocks"
        elif [ "${{ github.event.inputs.scan_type }}" == "friends" ]; then
          CMD="$CMD -friends"
        fi
        
        # Market cap (only for market scan)
        if [ "${{ github.event.inputs.scan_type }}" == "market" ] && [ -n "${{ github.event.inputs.market_cap }}" ]; then
          CMD="$CMD -mc ${{ github.event.inputs.market_cap }}"
        fi
        
        # ADR flag
        if [ "${{ github.event.inputs.include_adr }}" == "true" ]; then
          CMD="$CMD -adr"
        fi
        
        # Growth filters
        if [ -n "${{ github.event.inputs.eps_growth }}" ]; then
          CMD="$CMD -eps ${{ github.event.inputs.eps_growth }}"
        fi
        if [ -n "${{ github.event.inputs.rev_growth }}" ]; then
          CMD="$CMD -rev ${{ github.event.inputs.rev_growth }}"
        fi
        
        # Extra email
        if [ -n "${{ github.event.inputs.extra_email }}" ]; then
          CMD="$CMD -e '${{ github.event.inputs.extra_email }}'"
        fi
        
        # Report title (friends mode)
        if [ -n "${{ github.event.inputs.report_title }}" ]; then
          CMD="$CMD -t '${{ github.event.inputs.report_title }}'"
        fi
        
        echo "command=$CMD" >> $GITHUB_OUTPUT
        echo "Running: $CMD"
    
    - name: Run Scanner
      env:
        GMAIL_EMAIL: ${{ secrets.GMAIL_EMAIL }}
        GMAIL_PASSWORD: ${{ secrets.GMAIL_PASSWORD }}
        RECIPIENT_EMAIL: ${{ secrets.RECIPIENT_EMAIL }}
      run: |
        ${{ steps.build_cmd.outputs.command }}
    
    - name: Save exit history
      uses: actions/upload-artifact@v3
      with:
        name: exit-history
        path: exit_history.json
        if-no-files-found: ignore
```

### Using the Advanced Workflow

1. Go to **Actions** tab in your GitHub repo
2. Click **PSAR Market Scanner (Advanced)**
3. Click **Run workflow**
4. Fill in the options:
   - **Scan type**: market, mystocks, or friends
   - **Min market cap**: 1, 5, 10, etc.
   - **Include ADRs**: Check to include international stocks
   - **EPS growth**: Leave empty or enter minimum % (e.g., 15)
   - **Revenue growth**: Leave empty or enter minimum %
5. Click **Run workflow**

### Multiple Scheduled Scans with Different Options

You can create multiple workflow files for different scan configurations:

**File: .github/workflows/scan-market.yml** (Default market scan)
```yaml
name: Market Scan (Default)
on:
  schedule:
    - cron: '30 13 * * 1-5'
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - run: pip install yfinance pandas ta
    - env:
        GMAIL_EMAIL: ${{ secrets.GMAIL_EMAIL }}
        GMAIL_PASSWORD: ${{ secrets.GMAIL_PASSWORD }}
        RECIPIENT_EMAIL: ${{ secrets.RECIPIENT_EMAIL }}
      run: python market_scanner.py -mc 10
```

**File: .github/workflows/scan-smallcap-adr.yml** (Small cap + ADRs)
```yaml
name: Small Cap + ADR Scan
on:
  schedule:
    - cron: '0 14 * * 1-5'  # 10:00 AM ET
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - run: pip install yfinance pandas ta
    - env:
        GMAIL_EMAIL: ${{ secrets.GMAIL_EMAIL }}
        GMAIL_PASSWORD: ${{ secrets.GMAIL_PASSWORD }}
        RECIPIENT_EMAIL: ${{ secrets.RECIPIENT_EMAIL }}
      run: python market_scanner.py -mc 1 -adr
```

**File: .github/workflows/scan-mystocks.yml** (Portfolio only)
```yaml
name: My Portfolio Scan
on:
  schedule:
    - cron: '30 20 * * 1-5'  # 4:30 PM ET
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - run: pip install yfinance pandas ta
    - env:
        GMAIL_EMAIL: ${{ secrets.GMAIL_EMAIL }}
        GMAIL_PASSWORD: ${{ secrets.GMAIL_PASSWORD }}
        RECIPIENT_EMAIL: ${{ secrets.RECIPIENT_EMAIL }}
      run: python market_scanner.py -mystocks
```

### GitHub Secrets Required

In your repo: Settings → Secrets → Actions → New repository secret

| Secret | Value |
|--------|-------|
| `GMAIL_EMAIL` | your.email@gmail.com |
| `GMAIL_PASSWORD` | your-app-password |
| `RECIPIENT_EMAIL` | recipient@example.com |

---

## Understanding the Reports

### Market Scanner Report

**Sections:**
1. **Zone Guide** - Explains PSAR zones and momentum
2. **Summary** - Counts by zone
3. **Recent Exits** - Stocks that dropped from BUY zones (7-day window)
4. **Improving Rapidly** - SELL/WEAK stocks with Momentum ≥6 (potential flips)
5. **Watchlist** - Your custom_watchlist.txt stocks
6. **Strong Buy - Top Tier** - Best opportunities (all criteria met)
7. **Buy - Confirmed** - PSAR >+5% stocks
8. **Buy** - +2% to +5% stocks
9. **Dividend Stocks** - Yield 1.5-15%, sorted by zone

### Portfolio Report (-mystocks)

**Sections:**
1. **Summary** - Your positions by zone with dollar values
2. **Recent Exits** - Your positions that exited BUY zones
3. **Improving** - Your SELL/WEAK positions with good momentum
4. **Concentrated Positions** - >$10K positions broken down by zone
5. **Covered Call Opportunities** - For NEUTRAL/WEAK/SELL positions
6. **All Positions** - Complete list by zone

### Column Definitions

| Column | Meaning |
|--------|---------|
| **Zone** | PSAR zone classification |
| **Mom** | Momentum score (1-10) |
| **PSAR %** | Distance from PSAR (+ = bullish) |
| **IR** | Indicator Rating (0-100) |
| **RSI** | Relative Strength Index |
| **50MA** | ↑ = Above 50-day MA, ↓ = Below |
| **⭐** | IBD stock |

---

## Troubleshooting

### Common Issues

**"No data" for a ticker:**
- Ticker may be delisted or have insufficient history
- Some OTC/foreign stocks not supported by yfinance

**First ticker in watchlist missing:**
- File may have BOM (Byte Order Mark)
- Scanner now handles this with `utf-8-sig` encoding

**Momentum scores all showing 5:**
- PSAR signal is very new (not enough history)
- Check `days_since_signal` column

**Email not sending:**
- Verify Gmail app password (not regular password)
- Check 2FA is enabled on Gmail account
- Verify environment variables are set

### Debug Mode

Add print statements in `scan_ticker_full()` to debug specific tickers:
```python
if ticker_symbol == 'DEBUG_TICKER':
    print(f"Price: {current_price}, PSAR: {psar_value}, Distance: {psar_distance}")
```

---

## License

MIT License - Feel free to modify and distribute.

---

## Credits

- **yfinance** - Yahoo Finance data
- **ta** - Technical analysis library
- **IBD** - Investor's Business Daily for growth stock methodology

# Market-Wide PSAR Multi-Indicator Scanner

Automated broad market scanner covering S&P 500, NASDAQ 100, Russell 1000, IBD lists, crypto, and major indices.

## 🎯 Features

- **Comprehensive Coverage**: 500-1000+ stocks automatically
- **8 Technical Indicators**: PSAR, MACD, RSI, Stochastic, Williams %R, Bollinger Bands, Coppock Curve, Ultimate Oscillator
- **Email Alerts**: Same format as portfolio scanner
- **Warning System**: Alerts when stocks exit PSAR buy
- **Twice Daily Scans**: 7 AM and 6 PM PST
- **History Tracking**: Tracks changes across runs

## 📊 Coverage

- **S&P 500** - Automatically fetched
- **NASDAQ 100** - Automatically fetched
- **Russell 1000** - Major mid-caps
- **IBD Lists** - Load from CSV files (optional)
- **Crypto** - BTC, ETH, SOL, AVAX
- **Indices** - SPY, QQQ, DIA, IWM, MDY, VTI

## 🚀 Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/YOUR_USERNAME/market-psar-scanner.git
cd market-psar-scanner
```

### 2. Set GitHub Secrets
Go to Settings → Secrets → Actions and add:
- `GMAIL_EMAIL`
- `GMAIL_PASSWORD` (Gmail App Password)
- `RECIPIENT_EMAIL`

### 3. Enable Workflow Permissions
Settings → Actions → General → Workflow permissions → "Read and write permissions"

### 4. Run It!
Actions tab → Market PSAR Scanner Automation → Run workflow

## 📧 Email Format

### Warning Section
- Shows stocks that recently exited PSAR buy
- Red highlighted section at top

### Indicator Guide
- Educational table comparing all indicators
- Timing, accuracy, best use cases

### New Changes
- Stocks that just entered PSAR buy
- Full indicator breakdown

### Current Signals
- Top 50 PSAR buy signals (by distance)
- Top 30 early buy signals (by signal count)
- Full indicator checkmarks

## 📁 Optional: IBD Lists

Place CSV files in root directory:
- `ibd_50.csv`
- `ibd_bigcap20.csv`
- `ibd_ipo.csv`
- `ibd_spotlight.csv`
- `ibd_sector.csv`

Format: First column should be tickers or have column named "Symbol" or "Ticker"

## 🔧 Configuration

Edit `config.py` to customize:
- Indicator thresholds
- PSAR parameters
- Email preferences
- Alert settings

## 📅 Schedule

- **7 AM PST** (3 PM UTC) - Pre-market analysis
- **6 PM PST** (2 AM UTC) - After-hours analysis

Adjust in `.github/workflows/market_scanner.yml` if needed.

## 💰 Cost

**Free!** GitHub Actions provides 2,000 minutes/month for private repos.
Each scan takes ~5-10 minutes.
Monthly usage: ~300-600 minutes (well within limit)

## 🔒 Security

- Repository should be **private**
- Never commit credentials
- Use GitHub Secrets for email
- History tracked in GitHub

## 📊 Output

- **No Excel attachment** (too large)
- **No sell signals table** (too many)
- **Focus on actionable signals**: New entries, top buys, early signals
- **Warning section**: Recent exits for risk management

## 🎓 Differences from Portfolio Scanner

| Feature | Portfolio Scanner | Market Scanner |
|---------|------------------|----------------|
| Coverage | 45 tickers | 500-1000+ tickers |
| Excel Attachment | ✅ Yes | ❌ No (too large) |
| Sell Signals | ✅ Shows all | ❌ Only exits |
| Runtime | ~2 min | ~5-10 min |
| Email Size | Medium | Large |
| Focus | All positions | Actionable signals |

## 🚨 Alert Logic

1. **First run**: Creates baseline, sends summary
2. **Second run**: Detects changes, shows warnings
3. **Ongoing**: Tracks last 14 scans (7 days)

## 🛠️ Troubleshooting

**Scan timeout?**
- Markets lists fetch from Wikipedia
- May need to retry if Wikipedia is slow

**Too many stocks?**
- Scanner automatically fetches S&P 500 and NASDAQ 100
- Combined with Russell additions = 500-800 stocks
- Add IBD CSV files for 1000+ stocks

**Email too large?**
- Only top 50 buy signals shown
- Only top 30 early signals shown
- Full data in scan_status.json (GitHub artifacts)

## 📞 Support

Check GitHub Actions logs for errors:
- Actions tab → Click failed run → Expand steps

Common issues same as portfolio scanner - see main docs.

---

**Happy Trading! 📈**

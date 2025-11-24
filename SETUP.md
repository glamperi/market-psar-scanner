# Market Scanner Setup Guide

## 🚀 Complete Setup in 10 Minutes

### Step 1: Create New Private Repository

1. Go to https://github.com/new
2. Repository name: `market-psar-scanner`
3. Description: "Market-wide PSAR scanner covering S&P 500, NASDAQ 100, Russell 1000"
4. **Select "Private"** ✅
5. Click "Create repository"

---

### Step 2: Initialize Local Repository

```bash
# Create directory
cd ~/Dev/Python/Investing
mkdir market-psar-scanner
cd market-psar-scanner

# Copy all files from outputs folder here
# (config.py, market_scanner.py, .github/workflows/, README.md, .gitignore)

# Initialize git
git init
git add .
git commit -m "Initial commit - Market PSAR Scanner"

# Connect to GitHub (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/market-psar-scanner.git
git branch -M main
git push -u origin main
```

---

### Step 3: Add GitHub Secrets

1. Go to your repo: `https://github.com/YOUR_USERNAME/market-psar-scanner`
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **"New repository secret"**

Add these 3 secrets:

**Secret 1:**
- Name: `GMAIL_EMAIL`
- Value: `glamp2013@gmail.com`

**Secret 2:**
- Name: `GMAIL_PASSWORD`
- Value: Your Gmail App Password (get new one if needed)

**Secret 3:**
- Name: `RECIPIENT_EMAIL`  
- Value: `glamp2013@gmail.com`

---

### Step 4: Enable Workflow Permissions

1. Settings → Actions → General
2. Scroll to "Workflow permissions"
3. Select **"Read and write permissions"** ✅
4. Click Save

---

### Step 5: Test It!

1. Go to **Actions** tab
2. Click **"Market PSAR Scanner Automation"**
3. Click **"Run workflow"** button (right side)
4. Click green **"Run workflow"** button
5. Wait 5-10 minutes
6. Check your email! 📧

---

## 📧 What to Expect

### First Email:
- ⚠️ No warning section (no history yet)
- 📊 Indicator comparison table
- 📈 Summary stats (how many buy signals)
- 🟢 Top 50 PSAR buy signals
- 🟡 Top 30 early buy signals

### Second Email (12 hours later):
- ⚠️ **Warning section appears!** (if any exits)
- 🚨 New entries since last scan
- 📊 Same tables as before
- 🟢 Updated top signals

---

## 🎯 Key Differences from Portfolio Scanner

### Portfolio Scanner:
- 45 specific stocks
- Full Excel attachment
- All buy and sell signals shown
- Detailed per-position analysis

### Market Scanner:
- 500-1000+ stocks
- No Excel (too large)
- Only top 50 buy signals + top 30 early
- Focus on actionable opportunities
- **Same email format otherwise!**

---

## 📊 Optional: Add IBD Lists

If you have IBD CSV files:

```bash
# Place CSV files in repository root
cp ~/Downloads/ibd_50.csv market-psar-scanner/
cp ~/Downloads/ibd_bigcap20.csv market-psar-scanner/
# ... etc

# Commit them
git add ibd_*.csv
git commit -m "Add IBD lists"
git push
```

The scanner will automatically detect and include them!

---

## 🔍 Monitoring

### Check Run Status:
Actions tab → See all runs with timestamps

### View Logs:
Click any run → Click "scan" job → Expand steps

### Download Data:
Click run → Scroll to "Artifacts" → Download scan_status.json

---

## 🐛 Troubleshooting

### "Timeout" or "Slow" Issues:
- S&P 500/NASDAQ lists fetched from Wikipedia
- Sometimes slow, just retry
- Or run at different time

### "Too Many Requests" Errors:
- Yahoo Finance rate limiting
- Scanner includes automatic retries
- Usually resolves on next run

### Email Not Received:
- Check spam folder
- Verify GitHub Secrets are correct
- Check workflow run logs for errors

### Wrong Stocks Scanned:
- S&P 500 and NASDAQ 100 auto-fetched
- Russell 1000 subset is hardcoded
- Add IBD CSV files for more coverage

---

## 📅 Automatic Schedule

Once working, it runs automatically:
- **7 AM PST** - Morning pre-market scan
- **6 PM PST** - Evening after-hours scan

Just check email twice daily! No maintenance needed.

---

## 💡 Pro Tips

1. **First week**: Run manually daily to build history
2. **After week**: Full automation, just check emails
3. **IBD lists**: Optional but recommended for growth stocks
4. **Compare scanners**: Run both portfolio and market for complete view

---

## 🎉 You're Done!

After setup:
- ✅ Market scanner runs twice daily automatically
- ✅ Emails you actionable signals
- ✅ Tracks history for warnings
- ✅ No maintenance required

Check your email at 7 AM and 6 PM PST for market opportunities! 📊

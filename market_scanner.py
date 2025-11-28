import warnings
# Suppress the FutureWarning from ta library
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import requests
from ta.trend import MACD, PSARIndicator
from ta.volatility import BollingerBands
from ta.momentum import WilliamsRIndicator, UltimateOscillator, RSIIndicator
from ta.trend import CCIIndicator

# Cache for FINRA short interest data (to avoid repeated API calls)
_finra_short_cache = {}

def get_finra_short_interest(ticker):
    """
    Fetch short interest data from FINRA for OTC stocks.
    Returns (short_shares, avg_daily_volume, days_to_cover) or (None, None, None) if not found.
    
    Note: FINRA publishes short interest twice monthly, so data may be up to 2 weeks old.
    """
    global _finra_short_cache
    
    # Check cache first
    if ticker in _finra_short_cache:
        return _finra_short_cache[ticker]
    
    try:
        url = "https://api.finra.org/data/group/otcMarket/name/EquityShortInterest"
        
        payload = {
            "compareFilters": [
                {
                    "compareType": "EQUAL",
                    "fieldName": "issueSymbolIdentifier", 
                    "fieldValue": ticker
                }
            ],
            "limit": 1,
            "sortFields": ["-settlementDate"]  # Get most recent
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                record = data[0]
                short_shares = record.get('currentShortPositionQuantity', 0)
                avg_volume = record.get('averageDailyVolumeQuantity', 0)
                days_to_cover = record.get('daysToCoverQuantity', 0)
                
                result = (short_shares, avg_volume, days_to_cover)
                _finra_short_cache[ticker] = result
                return result
        
        # Not found or error
        _finra_short_cache[ticker] = (None, None, None)
        return (None, None, None)
        
    except Exception as e:
        _finra_short_cache[ticker] = (None, None, None)
        return (None, None, None)


class MarketScanner:
    def __init__(self, min_market_cap_billions=10):
        self.results = []
        self.ticker_issues = []
        self.ibd_stats = {}
        self.min_market_cap = min_market_cap_billions * 1_000_000_000  # Convert to dollars
        self.min_market_cap_billions = min_market_cap_billions
        self.filter_reasons = {}  # Track why stocks are filtered
        self.short_interest_overrides = self.load_short_interest_csv()
    
    def load_short_interest_csv(self):
        """Load manual short interest overrides from short_interest.csv
        
        CSV format:
        Symbol,ShortPercent,DaysToCover
        MTPLF,5.2,3.21
        TSWCF,2.1,1.5
        """
        overrides = {}
        csv_file = 'short_interest.csv'
        
        if os.path.exists(csv_file):
            try:
                import csv
                with open(csv_file, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        symbol = row.get('Symbol', '').strip().upper()
                        if symbol:
                            try:
                                short_pct = float(row.get('ShortPercent', 0)) if row.get('ShortPercent') else None
                                days = float(row.get('DaysToCover', 0)) if row.get('DaysToCover') else None
                                overrides[symbol] = {
                                    'short_percent': short_pct,
                                    'days_to_cover': days
                                }
                            except ValueError:
                                pass
                if overrides:
                    print(f"✓ Loaded {len(overrides)} short interest overrides from {csv_file}")
            except Exception as e:
                print(f"⚠️ Error loading {csv_file}: {e}")
        
        return overrides
        
    def load_custom_watchlist(self):
        """Load priority watchlist from custom_watchlist.txt"""
        watchlist_file = 'custom_watchlist.txt'
        watchlist = []
        seen = set()
        
        if os.path.exists(watchlist_file):
            try:
                # Use utf-8-sig to handle BOM (Byte Order Mark) that some editors add
                with open(watchlist_file, 'r', encoding='utf-8-sig') as f:
                    for line in f:
                        # Strip whitespace first
                        line = line.strip()
                        
                        # Skip empty lines and comments BEFORE processing
                        if not line or line.startswith('#'):
                            continue
                        
                        # Now process the ticker - uppercase and remove hidden chars
                        ticker = line.upper()
                        ticker = ''.join(c for c in ticker if c.isalnum() or c in '-.')
                        
                        # Skip empty result or duplicates
                        if ticker and ticker not in seen:
                            watchlist.append(ticker)
                            seen.add(ticker)
                        elif ticker and ticker in seen:
                            print(f"  ⚠️ Skipping duplicate: {ticker}")
                
                print(f"\n✓ Loaded {len(watchlist)} unique tickers from custom watchlist")
                for ticker in watchlist:
                    print(f"  - {ticker}")
            except Exception as e:
                print(f"✗ Error loading custom watchlist: {e}")
        else:
            print(f"\nℹ️  No custom watchlist found at {watchlist_file}")
        
        return watchlist
    
    def load_ibd_stats(self):
        """Load IBD stats from all IBD CSV files"""
        ibd_files = [
            'ibd_50.csv',
            'ibd_bigcap20.csv', 
            'ibd_sector.csv',
            'ibd_ipo.csv',
            'ibd_spotlight.csv'
        ]
        
        all_ibd_tickers = []
        
        for filename in ibd_files:
            if os.path.exists(filename):
                try:
                    df = pd.read_csv(filename)
                    
                    # Check if this file has stats or just symbols
                    if 'Composite' in df.columns:
                        # Full stats file
                        for _, row in df.iterrows():
                            symbol = str(row['Symbol']).strip().upper()
                            all_ibd_tickers.append(symbol)
                            
                            self.ibd_stats[symbol] = {
                                'composite': row.get('Composite', 'N/A'),
                                'eps': row.get('EPS', 'N/A'),
                                'rs': row.get('RS', 'N/A'),
                                'smr': row.get('SMR', 'N/A'),
                                'source': filename.replace('.csv', '').replace('_', ' ').upper()
                            }
                    else:
                        # Just symbols (like ibd_spotlight.csv)
                        for symbol in df['Symbol'].tolist():
                            symbol = str(symbol).strip().upper()
                            all_ibd_tickers.append(symbol)
                            if symbol not in self.ibd_stats:
                                self.ibd_stats[symbol] = {
                                    'composite': 'N/A',
                                    'eps': 'N/A',
                                    'rs': 'N/A',
                                    'smr': 'N/A',
                                    'source': filename.replace('.csv', '').replace('_', ' ').upper()
                                }
                    
                    print(f"✓ Loaded {len(df)} tickers from {filename}")
                except Exception as e:
                    print(f"✗ Error loading {filename}: {e}")
        
        return list(set(all_ibd_tickers))
    
    def load_sp500_tickers(self):
        """Load S&P 500 from CSV"""
        csv_file = 'sp500_tickers.csv'
        if os.path.exists(csv_file):
            try:
                df = pd.read_csv(csv_file)
                tickers = df['Symbol'].tolist()
                print(f"✓ Loaded {len(tickers)} S&P 500 tickers from CSV")
                return tickers
            except Exception as e:
                print(f"✗ Error loading {csv_file}: {e}")
        else:
            print(f"⚠️ {csv_file} NOT FOUND in {os.getcwd()}")
        return []
    
    def load_nasdaq100_tickers(self):
        """Load NASDAQ 100 from CSV"""
        csv_file = 'nasdaq100_tickers.csv'
        if os.path.exists(csv_file):
            try:
                df = pd.read_csv(csv_file)
                tickers = df['Symbol'].tolist()
                print(f"✓ Loaded {len(tickers)} NASDAQ 100 tickers from CSV")
                return tickers
            except Exception as e:
                print(f"✗ Error loading {csv_file}: {e}")
        else:
            print(f"⚠️ {csv_file} NOT FOUND")
        return []
    
    def load_russell2000_tickers(self):
        """Load Russell 2000 from CSV"""
        csv_file = 'russell2000_tickers.csv'
        if os.path.exists(csv_file):
            try:
                df = pd.read_csv(csv_file)
                tickers = df['Symbol'].tolist()
                print(f"✓ Loaded {len(tickers)} Russell 2000 tickers from CSV")
                return tickers
            except Exception as e:
                print(f"✗ Error loading {csv_file}: {e}")
        else:
            print(f"⚠️ {csv_file} NOT FOUND")
        return []
    
    def load_adr_tickers(self):
        """Load ADR tickers - major international companies trading on US exchanges"""
        # First try to load from file
        csv_file = 'adr_tickers.csv'
        if os.path.exists(csv_file):
            try:
                df = pd.read_csv(csv_file)
                tickers = df['Symbol'].tolist()
                print(f"✓ Loaded {len(tickers)} ADR tickers from CSV")
                return tickers
            except Exception as e:
                print(f"✗ Error loading {csv_file}: {e}")
        
        # Fallback to built-in list of major ADRs
        major_adrs = [
            # China
            'BABA', 'JD', 'PDD', 'BIDU', 'NIO', 'XPEV', 'LI', 'BILI', 'TME', 'IQ',
            'TAL', 'EDU', 'VNET', 'WB', 'ZTO', 'YUMC', 'HTHT', 'ATHM', 'QFIN', 'FUTU',
            'TIGR', 'KC', 'GOTU', 'MNSO', 'YMM', 'DADA', 'BZ', 'LEGN', 'ZLAB',
            # Taiwan
            'TSM', 'UMC', 'ASX', 'IMOS',
            # Japan
            'TM', 'SONY', 'HMC', 'MUFG', 'SMFG', 'MFG', 'NMR', 'NTDOY', 'IX',
            # South Korea
            'KB', 'SHG', 'WF', 'LPL',
            # India
            'INFY', 'WIT', 'IBN', 'HDB', 'SIFY', 'RDY', 'TTM', 'VEDL', 'WNS',
            # Brazil
            'VALE', 'PBR', 'ITUB', 'BBD', 'ABEV', 'SBS', 'GGB', 'SID', 'BRFS', 'PAGS',
            'STNE', 'NU', 'XP', 'VTEX',
            # Argentina
            'MELI', 'YPF', 'GGAL', 'BMA', 'SUPV', 'GLOB',
            # Chile
            'SQM', 'BSAC', 'LTM',
            # Mexico
            'AMX', 'TV', 'KOF', 'BSMX',
            # UK
            'BP', 'SHEL', 'GSK', 'AZN', 'HSBC', 'RIO', 'BCS', 'LYG', 'NWG', 'BTI', 'DEO',
            'VOD', 'NGG', 'RELX', 'LSXMK', 'ARMHY', 'JRI',
            # Europe
            'ASML', 'NVO', 'SAP', 'TTE', 'UL', 'SNY', 'ENB', 'SU', 'TD', 'BNS',
            'BMO', 'CM', 'RY', 'SHOP', 'NVS', 'RHHBY', 'UBS', 'CS', 'DB', 'ING', 'ERIC',
            'NOK', 'PHG', 'SPOT', 'MT', 'STLA',
            # Australia
            'BHP', 'RIO', 'WBK',
            # South Africa
            'GOLD', 'AU', 'HMY', 'DRD',
            # Israel
            'TEVA', 'NICE', 'CYBR', 'MNDY', 'WIX', 'FVRR', 'CHKP',
            # Southeast Asia
            'SE', 'GRAB',
        ]
        print(f"✓ Using built-in list of {len(major_adrs)} major ADRs")
        return major_adrs
    
    def get_dividend_yield(self, ticker_obj):
        """Get dividend yield for a ticker - FIXED VERSION with validation"""
        try:
            info = ticker_obj.info
            
            # Method 1: Direct dividendYield (yfinance returns as decimal, e.g., 0.02 = 2%)
            div_yield = info.get('dividendYield', None)
            if div_yield and div_yield > 0:
                # Check if it's already a percentage (>1) or decimal (<1)
                if div_yield > 1:
                    # Already a percentage, don't multiply
                    result = round(div_yield, 2)
                else:
                    # Decimal form, convert to percentage
                    result = round(div_yield * 100, 2)
                
                # Sanity check - cap at 25% (anything higher is likely an error)
                if result > 25:
                    return 0.0
                return result
            
            # Method 2: Calculate from dividendRate and price
            div_rate = info.get('dividendRate', None)
            price = info.get('currentPrice', info.get('regularMarketPrice', None))
            
            if div_rate and price and div_rate > 0 and price > 0:
                result = round((div_rate / price) * 100, 2)
                # Sanity check
                if result > 25:
                    return 0.0
                return result
            
            return 0.0
        except Exception as e:
            return 0.0
    
    def load_all_tickers_with_sources(self, include_adr=False):
        """Load all tickers and track their sources"""
        ticker_sources = {}
        
        print("\n" + "="*60)
        print("LOADING TICKER LISTS")
        print("="*60)
        
        # Load S&P 500
        sp500 = self.load_sp500_tickers()
        for ticker in sp500:
            ticker_sources[ticker] = 'S&P 500'
        
        # Load NASDAQ 100
        nasdaq100 = self.load_nasdaq100_tickers()
        for ticker in nasdaq100:
            if ticker in ticker_sources:
                ticker_sources[ticker] += ', NASDAQ 100'
            else:
                ticker_sources[ticker] = 'NASDAQ 100'
        
        # Load Russell 2000
        russell2000 = self.load_russell2000_tickers()
        for ticker in russell2000:
            if ticker not in ticker_sources:
                ticker_sources[ticker] = 'Russell 2000'
        
        # Load IBD
        ibd_tickers = self.load_ibd_stats()
        for ticker in ibd_tickers:
            if ticker in ticker_sources:
                ticker_sources[ticker] += ', IBD'
            else:
                ticker_sources[ticker] = 'IBD'
        
        # Load ADRs if requested
        if include_adr:
            adr_tickers = self.load_adr_tickers()
            for ticker in adr_tickers:
                if ticker in ticker_sources:
                    ticker_sources[ticker] += ', ADR'
                else:
                    ticker_sources[ticker] = 'ADR'
        
        print(f"\n{'='*60}")
        print(f"TICKER LIST SUMMARY")
        print(f"{'='*60}")
        print(f"Total unique tickers: {len(ticker_sources)}")
        print(f"  - S&P 500: {len([t for t, s in ticker_sources.items() if 'S&P 500' in s])}")
        print(f"  - NASDAQ 100: {len([t for t, s in ticker_sources.items() if 'NASDAQ 100' in s])}")
        print(f"  - Russell 2000 only: {len([t for t, s in ticker_sources.items() if s == 'Russell 2000'])}")
        print(f"  - IBD: {len([t for t, s in ticker_sources.items() if 'IBD' in s])}")
        if include_adr:
            print(f"  - ADR: {len([t for t, s in ticker_sources.items() if 'ADR' in s])}")
        print(f"{'='*60}\n")
        
        return ticker_sources
    
    def calculate_indicators(self, hist):
        """Calculate all technical indicators"""
        try:
            # PSAR
            psar_indicator = PSARIndicator(high=hist['High'], low=hist['Low'], close=hist['Close'])
            psar = psar_indicator.psar()
            psar_up = psar_indicator.psar_up()
            psar_down = psar_indicator.psar_down()
            
            current_price = hist['Close'].iloc[-1]
            psar_value = psar.iloc[-1]
            is_bullish = pd.notna(psar_up.iloc[-1])
            
            # Calculate PSAR distance safely - NEGATIVE for sells, POSITIVE for buys
            if pd.notna(psar_value) and psar_value > 0 and pd.notna(current_price) and current_price > 0:
                raw_distance = abs((current_price - psar_value) / current_price) * 100
                # Make it negative if PSAR is above price (sell signal)
                if not is_bullish:
                    psar_distance = -raw_distance
                else:
                    psar_distance = raw_distance
            else:
                psar_distance = 0.0
            
            # Validate - skip if NaN
            if pd.isna(psar_distance) or pd.isna(current_price) or pd.isna(psar_value):
                return None
            
            # ==========================================
            # PSAR MOMENTUM SCORE (1-10)
            # Combines: direction, trajectory since signal start, current distance
            # ==========================================
            
            # Find when the current signal started and get distance at that point
            days_since_signal = 0
            signal_start_distance = abs(psar_distance)  # Default to current
            
            if is_bullish:
                # Count backwards to find when PSAR flipped to buy
                for i in range(len(psar_up) - 1, -1, -1):
                    if pd.notna(psar_up.iloc[i]):
                        days_since_signal += 1
                    else:
                        break
                # Get distance at signal start
                if days_since_signal > 0 and days_since_signal < len(hist):
                    start_idx = -days_since_signal
                    start_price = hist['Close'].iloc[start_idx]
                    start_psar = psar.iloc[start_idx]
                    if pd.notna(start_psar) and start_psar > 0:
                        signal_start_distance = abs((start_price - start_psar) / start_price) * 100
            else:
                # Count backwards to find when PSAR flipped to sell
                for i in range(len(psar_down) - 1, -1, -1):
                    if pd.notna(psar_down.iloc[i]):
                        days_since_signal += 1
                    else:
                        break
                # Get distance at signal start
                if days_since_signal > 0 and days_since_signal < len(hist):
                    start_idx = -days_since_signal
                    start_price = hist['Close'].iloc[start_idx]
                    start_psar = psar.iloc[start_idx]
                    if pd.notna(start_psar) and start_psar > 0:
                        signal_start_distance = abs((start_price - start_psar) / start_price) * 100
            
            # Calculate PSAR Delta (ratio of start distance to current distance)
            current_abs_distance = abs(psar_distance)
            if current_abs_distance > 0.1:  # Avoid division issues
                psar_delta_ratio = signal_start_distance / current_abs_distance
            else:
                psar_delta_ratio = 1.0
            
            # Calculate PSAR Momentum Score (1-10)
            # For BUY signals (positive distance): Higher distance = better, widening = better
            # For SELL signals (negative distance): Lower abs distance = better (closer to flip), narrowing = better
            
            if is_bullish:
                # Bullish: Score based on distance strength and whether it's growing
                # Base score from distance: 0-5% = 5, 5-10% = 7, 10%+ = 9
                if psar_distance >= 10:
                    base_score = 9
                elif psar_distance >= 5:
                    base_score = 7
                elif psar_distance >= 2:
                    base_score = 6
                else:
                    base_score = 5
                
                # Adjust based on trajectory (is it strengthening or weakening?)
                # Delta ratio > 1 means distance was bigger at start (weakening) = bad
                # Delta ratio < 1 means distance is bigger now (strengthening) = good
                if psar_delta_ratio < 0.7:  # Strengthening significantly
                    trajectory_adj = 1
                elif psar_delta_ratio > 1.5:  # Weakening significantly
                    trajectory_adj = -2
                elif psar_delta_ratio > 1.2:  # Weakening somewhat
                    trajectory_adj = -1
                else:
                    trajectory_adj = 0
                
                psar_momentum = max(1, min(10, base_score + trajectory_adj))
            else:
                # Bearish: Score based on how close to flip and whether improving
                # Closer to 0 = better, narrowing from start = better
                if current_abs_distance <= 2:
                    base_score = 6  # Close to flip
                elif current_abs_distance <= 5:
                    base_score = 4  # Weak zone
                elif current_abs_distance <= 10:
                    base_score = 2  # Sell zone
                else:
                    base_score = 1  # Deep sell
                
                # Adjust based on trajectory
                # Delta ratio > 1 means started worse, now better (improving) = good
                # Delta ratio < 1 means started better, now worse (deteriorating) = bad
                if psar_delta_ratio >= 2.5:  # Major improvement (like OKLO example)
                    trajectory_adj = 3
                elif psar_delta_ratio >= 1.5:  # Good improvement
                    trajectory_adj = 2
                elif psar_delta_ratio >= 1.2:  # Some improvement
                    trajectory_adj = 1
                elif psar_delta_ratio < 0.8:  # Getting worse
                    trajectory_adj = -1
                else:
                    trajectory_adj = 0
                
                psar_momentum = max(1, min(10, base_score + trajectory_adj))
            
            # PSAR Zone Classification (now influenced by momentum)
            # Upgrade zone if momentum is strong (>=7 for sells means improving rapidly)
            effective_distance = psar_distance
            if not is_bullish and psar_momentum >= 7:
                effective_distance = psar_distance + 2  # Boost by 2% for zone calc
            elif is_bullish and psar_momentum <= 3:
                effective_distance = psar_distance - 1  # Penalize weakening buys
            
            if effective_distance > 5:
                psar_zone = 'STRONG_BUY'
            elif effective_distance >= 2:
                psar_zone = 'BUY'
            elif effective_distance >= -2:
                psar_zone = 'NEUTRAL'
            elif effective_distance >= -5:
                psar_zone = 'WEAK'
            else:
                psar_zone = 'SELL'
            
            # 52-week high and % off high
            high_52w = hist['High'].tail(252).max() if len(hist) >= 252 else hist['High'].max()
            pct_off_high = ((high_52w - current_price) / high_52w) * 100 if high_52w > 0 else 0
            
            # 50-day moving average
            ma_50 = hist['Close'].tail(50).mean() if len(hist) >= 50 else hist['Close'].mean()
            above_ma50 = current_price > ma_50
            
            # Volume confirmation (today's volume vs 20-day average)
            vol_20_avg = hist['Volume'].tail(20).mean() if len(hist) >= 20 else hist['Volume'].mean()
            current_volume = hist['Volume'].iloc[-1] if 'Volume' in hist.columns else 0
            volume_ratio = (current_volume / vol_20_avg) if vol_20_avg > 0 else 1.0
            
            # MACD
            macd = MACD(close=hist['Close'])
            macd_line = macd.macd()
            signal_line = macd.macd_signal()
            has_macd = macd_line.iloc[-1] > signal_line.iloc[-1]
            
            # Bollinger Bands
            bb = BollingerBands(close=hist['Close'])
            bb_lower = bb.bollinger_lband()
            has_bb = current_price <= bb_lower.iloc[-1]
            
            # Williams %R
            willr = WilliamsRIndicator(high=hist['High'], low=hist['Low'], close=hist['Close'])
            willr_value = willr.williams_r()
            has_willr = willr_value.iloc[-1] < -80
            
            # Coppock Curve
            roc1 = hist['Close'].pct_change(periods=14) * 100
            roc2 = hist['Close'].pct_change(periods=11) * 100
            coppock = (roc1 + roc2).rolling(window=10).mean()
            has_coppock = coppock.iloc[-1] > 0 and coppock.iloc[-2] <= 0
            
            # Ultimate Oscillator
            ult = UltimateOscillator(high=hist['High'], low=hist['Low'], close=hist['Close'])
            ult_value = ult.ultimate_oscillator()
            has_ultimate = ult_value.iloc[-1] < 30
            
            # OBV (On-Balance Volume) - for buy confirmation
            # Calculate OBV: cumulative sum of volume * sign of price change
            import numpy as np
            price_change = hist['Close'].diff()
            obv = (hist['Volume'] * np.sign(price_change)).cumsum()
            
            # OBV trend: compare 20-day slope of OBV vs price
            if len(obv) >= 20:
                obv_now = obv.iloc[-1]
                obv_20ago = obv.iloc[-20]
                obv_slope = obv_now - obv_20ago
                
                price_now = hist['Close'].iloc[-1]
                price_20ago = hist['Close'].iloc[-20]
                price_slope = price_now - price_20ago
                
                # Determine OBV status
                if price_slope > 0:  # Price is rising
                    if obv_slope > 0:
                        obv_status = 'CONFIRM'  # Both rising - bullish
                    else:
                        obv_status = 'DIVERGE'  # Price up, OBV down - warning
                elif price_slope < 0:  # Price is falling
                    if obv_slope < 0:
                        obv_status = 'CONFIRM'  # Both falling - confirms downtrend
                    else:
                        obv_status = 'DIVERGE'  # Price down, OBV up - could reverse
                else:
                    obv_status = 'NEUTRAL'
            else:
                obv_status = 'NEUTRAL'
            
            # RSI
            rsi = RSIIndicator(close=hist['Close'])
            rsi_value = rsi.rsi().iloc[-1]
            
            # Signal Weight
            signal_weight = 0
            if has_macd: signal_weight += 30
            if has_bb: signal_weight += 10
            if has_willr: signal_weight += 20
            if has_coppock: signal_weight += 10
            if has_ultimate: signal_weight += 30
            
            # Entry Quality Score (A/B/C) - Loosened criteria
            entry_grade = 'C'
            if is_bullish:
                # Grade A: Fresh signal with either good weight OR oversold RSI
                if days_since_signal <= 7 and (signal_weight >= 50 or rsi_value < 40):
                    entry_grade = 'A'
                # Grade B: Reasonably fresh with some weight
                elif days_since_signal <= 20 and signal_weight >= 20:
                    entry_grade = 'B'
            
            # Day change
            day_change = ((current_price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2] * 100) if len(hist) > 1 else 0
            
            return {
                'price': float(current_price),
                'psar_value': float(psar_value),
                'psar_bullish': bool(is_bullish),
                'psar_distance': float(psar_distance),
                'psar_zone': psar_zone,
                'psar_momentum': int(psar_momentum),
                'psar_start_distance': float(signal_start_distance),
                'days_since_signal': int(days_since_signal),
                'pct_off_high': float(pct_off_high),
                'above_ma50': bool(above_ma50),
                'volume_ratio': float(volume_ratio),
                'obv_status': obv_status,
                'entry_grade': entry_grade,
                'has_macd': bool(has_macd),
                'has_bb': bool(has_bb),
                'has_willr': bool(has_willr),
                'has_coppock': bool(has_coppock),
                'has_ultimate': bool(has_ultimate),
                'rsi': float(rsi_value) if pd.notna(rsi_value) else 50.0,
                'signal_weight': int(signal_weight),
                'day_change': float(day_change)
            }
        except Exception as e:
            return None
    
    def scan_ticker_full(self, ticker_symbol, source="Unknown", skip_market_cap_filter=False):
        """Scan a single ticker with full data"""
        import time
        
        # Normalize ticker format for Yahoo Finance
        # BRK.B -> BRK-B, BF.B -> BF-B, etc.
        original_ticker = ticker_symbol
        if '.' in ticker_symbol and not ticker_symbol.endswith('.L'):  # Don't change London stocks
            ticker_symbol = ticker_symbol.replace('.', '-')
        
        # Add small delay to avoid rate limiting (0.1 seconds between requests)
        time.sleep(0.1)
        
        try:
            ticker_obj = yf.Ticker(ticker_symbol)
            
            # Try to get history with retry on rate limit
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    hist = ticker_obj.history(period="6mo")
                    break
                except Exception as e:
                    if 'rate' in str(e).lower() or '429' in str(e):
                        if attempt < max_retries - 1:
                            time.sleep(5)  # Wait 5 seconds on rate limit
                            continue
                    raise e
            
            if hist.empty:
                self.filter_reasons['empty_history'] = self.filter_reasons.get('empty_history', 0) + 1
                return None
            
            if len(hist) < 50:
                self.filter_reasons['short_history'] = self.filter_reasons.get('short_history', 0) + 1
                return None
            
            # Get company info
            try:
                info = ticker_obj.info
                company_name = info.get('longName', ticker_symbol)
                market_cap = info.get('marketCap', 0) or 0
                sector = info.get('sector', '') or ''
                quote_type = info.get('quoteType', '') or ''
                
                # Growth estimates from yfinance
                # Try multiple sources for growth data
                
                # EPS Growth: Calculate from forward vs trailing EPS if available
                forward_eps = info.get('forwardEps')
                trailing_eps = info.get('trailingEps')
                earnings_growth_raw = info.get('earningsGrowth')  # This is often trailing YoY
                
                if forward_eps and trailing_eps and trailing_eps > 0:
                    # Calculate implied forward growth
                    eps_growth_pct = ((forward_eps - trailing_eps) / abs(trailing_eps)) * 100
                elif earnings_growth_raw is not None:
                    # Fallback to earningsGrowth (trailing)
                    eps_growth_pct = earnings_growth_raw * 100
                else:
                    eps_growth_pct = None
                
                # Revenue Growth: Use revenueGrowth if available
                rev_growth_raw = info.get('revenueGrowth')
                if rev_growth_raw is not None:
                    rev_growth_pct = rev_growth_raw * 100
                else:
                    rev_growth_pct = None
                
                # Short interest data for short candidates
                # Priority: 1) CSV override, 2) yfinance, 3) FINRA (for OTC)
                
                # Check CSV override first
                if original_ticker in self.short_interest_overrides:
                    override = self.short_interest_overrides[original_ticker]
                    short_percent = override.get('short_percent')
                    short_ratio = override.get('days_to_cover')
                else:
                    # Try yfinance
                    short_percent = info.get('shortPercentOfFloat')  # As decimal, e.g., 0.15 = 15%
                    if short_percent is not None:
                        short_percent = short_percent * 100  # Convert to percentage
                    short_ratio = info.get('shortRatio')  # Days to cover
                    
                    # Fallback to FINRA for OTC stocks if yfinance doesn't have short data
                    # OTC stocks typically end in F or are 5 letters
                    is_likely_otc = (
                        len(original_ticker) == 5 or 
                        original_ticker.endswith('F') or
                        'OTC' in (info.get('exchange', '') or '').upper() or
                        info.get('quoteType') == 'EQUITY' and info.get('exchange') in ['PNK', 'OTC', 'NCM']
                    )
                    
                    if short_percent is None and is_likely_otc:
                        # Try FINRA API for OTC short interest
                        finra_shorts, finra_volume, finra_days = get_finra_short_interest(original_ticker)
                        if finra_shorts is not None and finra_shorts > 0:
                            # Try to calculate short % using shares outstanding from yfinance
                            shares_outstanding = info.get('sharesOutstanding')
                            float_shares = info.get('floatShares')
                            
                            if float_shares and float_shares > 0:
                                short_percent = (finra_shorts / float_shares) * 100
                            elif shares_outstanding and shares_outstanding > 0:
                                # Use shares outstanding as approximation
                                short_percent = (finra_shorts / shares_outstanding) * 100
                            
                            # Use FINRA's days to cover if available
                            if finra_days and finra_days > 0:
                                short_ratio = finra_days
                
            except Exception as e:
                self.filter_reasons['info_error'] = self.filter_reasons.get('info_error', 0) + 1
                company_name = ticker_symbol
                market_cap = 0
                sector = ''
                quote_type = ''
                eps_growth_pct = None
                rev_growth_pct = None
                short_percent = None
                short_ratio = None
            
            # Market cap filter: uses self.min_market_cap (default $10B)
            if not skip_market_cap_filter:
                if market_cap < self.min_market_cap:
                    self.filter_reasons['market_cap'] = self.filter_reasons.get('market_cap', 0) + 1
                    return None
            
            # Detect REIT or Limited Partnership
            is_reit = (
                'REIT' in sector.upper() or 
                'REIT' in (company_name or '').upper() or
                'REAL ESTATE' in sector.upper()
            )
            is_lp = (
                quote_type == 'MUTUALFUND' or
                ' LP' in (company_name or '').upper() or
                ' L.P.' in (company_name or '').upper() or
                'LIMITED PARTNER' in (company_name or '').upper() or
                ticker_symbol.endswith('LP')
            )
            
            # Calculate indicators
            indicators = self.calculate_indicators(hist)
            if not indicators:
                self.filter_reasons['indicators_failed'] = self.filter_reasons.get('indicators_failed', 0) + 1
                return None
            
            # Get dividend yield - FIXED
            dividend_yield = self.get_dividend_yield(ticker_obj)
            
            # Get IBD stats if available
            ibd_data = self.ibd_stats.get(ticker_symbol, {})
            
            result = {
                'ticker': original_ticker,  # Use original ticker format for display
                'company': company_name if company_name else ticker_symbol,
                'source': source,
                'dividend_yield': dividend_yield,
                'market_cap': market_cap,
                'is_reit': is_reit,
                'is_lp': is_lp,
                'eps_growth': eps_growth_pct,
                'rev_growth': rev_growth_pct,
                'short_percent': short_percent,  # Short interest as % of float
                'short_ratio': short_ratio,      # Days to cover
                'composite': ibd_data.get('composite', 'N/A'),
                'eps': ibd_data.get('eps', 'N/A'),
                'rs': ibd_data.get('rs', 'N/A'),
                'smr': ibd_data.get('smr', 'N/A'),
                **indicators
            }
            
            return result
            
        except Exception as e:
            self.filter_reasons['exception'] = self.filter_reasons.get('exception', 0) + 1
            # Capture first few error messages for debugging
            if 'first_exceptions' not in self.filter_reasons:
                self.filter_reasons['first_exceptions'] = []
            if len(self.filter_reasons['first_exceptions']) < 3:
                self.filter_reasons['first_exceptions'].append(f"{ticker_symbol}: {type(e).__name__}: {str(e)[:100]}")
            return None
    
    def scan_with_priority(self, include_adr=False):
        """Scan watchlist first, then broad market"""
        
        print("\n" + "="*70)
        print(" "*20 + "MARKET-WIDE PSAR SCANNER")
        print("="*70)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # PHASE 1: SCAN PRIORITY WATCHLIST
        print("\n" + "="*60)
        print("PHASE 1: SCANNING PRIORITY WATCHLIST")
        print("="*60)
        
        watchlist = self.load_custom_watchlist()
        watchlist_results = []
        
        for ticker in watchlist:
            print(f"\n📍 Scanning priority ticker: {ticker}")
            
            try:
                result = self.scan_ticker_full(ticker, source="Watchlist", skip_market_cap_filter=True)
                if result:
                    result['is_watchlist'] = True
                    watchlist_results.append(result)
                    
                    if result['psar_bullish']:
                        print(f"  ✓ PSAR BUY")
                        print(f"    Distance: {result['psar_distance']:.2f}%")
                        print(f"    Weight: {result['signal_weight']}")
                        print(f"    Price: ${result['price']:.2f}")
                        if result['dividend_yield'] > 0:
                            print(f"    Dividend: {result['dividend_yield']:.2f}%")
                    else:
                        print(f"  ○ PSAR SELL")
                else:
                    print(f"  ✗ No data available")
            except Exception as e:
                print(f"  ✗ ERROR: {str(e)}")
        
        print(f"\n✓ Watchlist scan complete: {len(watchlist_results)}/{len(watchlist)} successful")
        
        # PHASE 2: SCAN BROAD MARKET
        print("\n" + "="*60)
        print("PHASE 2: SCANNING BROAD MARKET")
        print("="*60)
        
        all_tickers = self.load_all_tickers_with_sources(include_adr=include_adr)
        
        # Remove watchlist tickers
        for ticker in watchlist:
            if ticker in all_tickers:
                del all_tickers[ticker]
        
        print(f"Scanning {len(all_tickers)} stocks from broad market...")
        print(f"This will take 20-30 minutes...\n")
        
        broad_market_results = []
        progress_count = 0
        error_count = 0
        no_data_count = 0
        market_cap_filtered = 0
        first_error = None
        
        for ticker, source in all_tickers.items():
            try:
                # Skip market cap filter for IBD stocks
                skip_cap = 'IBD' in source
                result = self.scan_ticker_full(ticker, source=source, skip_market_cap_filter=skip_cap)
                if result:
                    result['is_watchlist'] = False
                    broad_market_results.append(result)
                else:
                    no_data_count += 1
                
                progress_count += 1
                if progress_count % 50 == 0:
                    elapsed_pct = progress_count / len(all_tickers) * 100
                    print(f"Progress: {progress_count}/{len(all_tickers)} ({elapsed_pct:.1f}%) - Found: {len(broad_market_results)}, No data: {no_data_count}, Errors: {error_count}")
            except Exception as e:
                error_count += 1
                if first_error is None:
                    first_error = f"{ticker}: {str(e)}"
                continue
        
        print(f"\n✓ Broad market scan complete: {len(broad_market_results)} signals found")
        print(f"   No data/filtered: {no_data_count}, Errors: {error_count}")
        if first_error:
            print(f"   First error was: {first_error}")
        if self.filter_reasons:
            print(f"   Filter breakdown: {self.filter_reasons}")
        
        # Combine results
        all_results = watchlist_results + broad_market_results
        
        return {
            'watchlist_results': watchlist_results,
            'broad_market_results': broad_market_results,
            'all_results': all_results,
            'ticker_issues': self.ticker_issues
        }
    
    def scan_mystocks_only(self):
        """Scan only stocks from mystocks.txt - no broad market scan"""
        
        print("\n" + "="*70)
        print(" "*15 + "MY STOCKS PORTFOLIO SCANNER")
        print("="*70)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        mystocks_file = 'mystocks.txt'
        mystocks = []
        seen = set()
        
        if os.path.exists(mystocks_file):
            try:
                with open(mystocks_file, 'r', encoding='utf-8-sig') as f:
                    for line in f:
                        line = line.strip()
                        # Skip empty lines and comments BEFORE processing
                        if not line or line.startswith('#'):
                            continue
                        ticker = line.upper()
                        ticker = ''.join(c for c in ticker if c.isalnum() or c in '-.')
                        if ticker and ticker not in seen:
                            mystocks.append(ticker)
                            seen.add(ticker)
                
                print(f"\n✓ Loaded {len(mystocks)} tickers from mystocks.txt")
            except Exception as e:
                print(f"✗ Error loading mystocks.txt: {e}")
                return {'watchlist_results': [], 'broad_market_results': [], 'all_results': [], 'ticker_issues': []}
        else:
            print(f"✗ mystocks.txt not found!")
            return {'watchlist_results': [], 'broad_market_results': [], 'all_results': [], 'ticker_issues': []}
        
        # Load IBD stats for any overlapping tickers
        self.load_ibd_stats()
        
        print(f"\nScanning {len(mystocks)} portfolio stocks...")
        print("This will take a few minutes...\n")
        
        all_results = []
        progress_count = 0
        
        for ticker in mystocks:
            try:
                result = self.scan_ticker_full(ticker, source="Portfolio", skip_market_cap_filter=True)
                if result:
                    result['is_watchlist'] = True  # Treat all as watchlist for display
                    all_results.append(result)
                    
                    status = "BUY" if result['psar_bullish'] else "SELL"
                    print(f"  {ticker}: {status} (Dist: {result['psar_distance']:+.2f}%, Wt: {result['signal_weight']})")
                else:
                    print(f"  {ticker}: No data")
                
                progress_count += 1
                if progress_count % 25 == 0:
                    print(f"Progress: {progress_count}/{len(mystocks)}")
            except Exception as e:
                print(f"  {ticker}: ERROR - {str(e)}")
                continue
        
        print(f"\n✓ Portfolio scan complete: {len(all_results)}/{len(mystocks)} successful")
        
        # Count buys vs sells
        buys = len([r for r in all_results if r['psar_bullish']])
        sells = len([r for r in all_results if not r['psar_bullish']])
        print(f"  🟢 PSAR Buys: {buys}")
        print(f"  🔴 PSAR Sells: {sells}")
        
        return {
            'watchlist_results': all_results,  # Put everything in watchlist for email display
            'broad_market_results': [],
            'all_results': all_results,
            'ticker_issues': self.ticker_issues
        }
    
    def run(self, mystocks_only=False, include_adr=False):
        """Main scanner execution"""
        if mystocks_only:
            results = self.scan_mystocks_only()
        else:
            results = self.scan_with_priority(include_adr=include_adr)
        self.results = results
        
        print("\n" + "="*60)
        print("✓ SCAN COMPLETE!")
        print("="*60)
        
        return results
    
    def scan_friends_only(self):
        """Scan only stocks from friends.txt - no broad market scan"""
        
        print("\n" + "="*70)
        print(" "*15 + "FRIENDS PORTFOLIO SCANNER")
        print("="*70)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        friends_file = 'friends.txt'
        friends_stocks = []
        seen = set()
        
        if os.path.exists(friends_file):
            try:
                with open(friends_file, 'r', encoding='utf-8-sig') as f:
                    for line in f:
                        line = line.strip()
                        # Skip empty lines and comments BEFORE processing
                        if not line or line.startswith('#'):
                            continue
                        ticker = line.upper()
                        ticker = ''.join(c for c in ticker if c.isalnum() or c in '-.')
                        if ticker and ticker not in seen:
                            friends_stocks.append(ticker)
                            seen.add(ticker)
                
                print(f"\n✓ Loaded {len(friends_stocks)} tickers from friends.txt")
            except Exception as e:
                print(f"✗ Error loading friends.txt: {e}")
                return {'watchlist_results': [], 'broad_market_results': [], 'all_results': [], 'ticker_issues': []}
        else:
            print(f"✗ friends.txt not found!")
            return {'watchlist_results': [], 'broad_market_results': [], 'all_results': [], 'ticker_issues': []}
        
        # Load IBD stats for any overlapping tickers
        self.load_ibd_stats()
        
        print(f"\nScanning {len(friends_stocks)} friend's stocks...")
        
        all_results = []
        
        for ticker in friends_stocks:
            try:
                result = self.scan_ticker_full(ticker, source="Friends", skip_market_cap_filter=True)
                if result:
                    result['is_watchlist'] = True
                    all_results.append(result)
                    
                    status = "BUY" if result['psar_bullish'] else "SELL"
                    zone = result.get('psar_zone', 'UNKNOWN')
                    print(f"  {ticker}: {zone} (PSAR: {result['psar_distance']:+.2f}%, Mom: {result['psar_momentum']})")
                else:
                    print(f"  {ticker}: No data")
            except Exception as e:
                print(f"  {ticker}: ERROR - {str(e)}")
                continue
        
        print(f"\n✓ Friends scan complete: {len(all_results)}/{len(friends_stocks)} successful")
        
        return {
            'watchlist_results': all_results,
            'broad_market_results': [],
            'all_results': all_results,
            'ticker_issues': self.ticker_issues
        }
    
    def scan_shorts_only(self):
        """Scan only stocks from shorts.txt - potential short candidates"""
        
        print("\n" + "="*70)
        print(" "*15 + "SHORT CANDIDATES SCANNER")
        print("="*70)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        shorts_file = 'shorts.txt'
        short_stocks = []
        seen = set()
        
        if os.path.exists(shorts_file):
            try:
                with open(shorts_file, 'r', encoding='utf-8-sig') as f:
                    for line in f:
                        line = line.strip()
                        # Skip empty lines and comments BEFORE processing
                        if not line or line.startswith('#'):
                            continue
                        ticker = line.upper()
                        ticker = ''.join(c for c in ticker if c.isalnum() or c in '-.')
                        if ticker and ticker not in seen:
                            short_stocks.append(ticker)
                            seen.add(ticker)
                
                print(f"\n✓ Loaded {len(short_stocks)} tickers from shorts.txt")
            except Exception as e:
                print(f"✗ Error loading shorts.txt: {e}")
                return {'watchlist_results': [], 'broad_market_results': [], 'all_results': [], 'ticker_issues': []}
        else:
            print(f"✗ shorts.txt not found!")
            return {'watchlist_results': [], 'broad_market_results': [], 'all_results': [], 'ticker_issues': []}
        
        print(f"\nScanning {len(short_stocks)} potential short candidates...")
        
        all_results = []
        
        for ticker in short_stocks:
            try:
                result = self.scan_ticker_full(ticker, source="Shorts", skip_market_cap_filter=True)
                if result:
                    result['is_watchlist'] = True
                    all_results.append(result)
                    
                    zone = result.get('psar_zone', 'UNKNOWN')
                    short_pct = result.get('short_percent')
                    short_pct_str = f"{short_pct:.1f}%" if short_pct else "N/A"
                    
                    # Flag squeeze risk
                    squeeze_warn = " ⚠️SQUEEZE RISK" if short_pct and short_pct > 20 else ""
                    
                    print(f"  {ticker}: {zone} (PSAR: {result['psar_distance']:+.2f}%, SI: {short_pct_str}){squeeze_warn}")
                else:
                    print(f"  {ticker}: No data")
            except Exception as e:
                print(f"  {ticker}: ERROR - {str(e)}")
                continue
        
        print(f"\n✓ Shorts scan complete: {len(all_results)}/{len(short_stocks)} successful")
        
        # Analyze short candidates
        sells = [r for r in all_results if not r['psar_bullish']]
        high_si = [r for r in all_results if r.get('short_percent') and r.get('short_percent') > 20]
        
        print(f"  🔴 In SELL zone: {len(sells)}")
        print(f"  ⚠️ High short interest (>20%): {len(high_si)}")
        
        return {
            'watchlist_results': all_results,
            'broad_market_results': [],
            'all_results': all_results,
            'ticker_issues': self.ticker_issues
        }

if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='PSAR Market Scanner')
    parser.add_argument('-mystocks', action='store_true', help='Scan only mystocks.txt (your portfolio)')
    parser.add_argument('-friends', action='store_true', help='Scan only friends.txt (friend portfolio)')
    parser.add_argument('-shorts', action='store_true', help='Scan only shorts.txt (short candidates)')
    parser.add_argument('-shortscan', action='store_true', help='Full market scan for short candidates (uses -mc, -adr filters)')
    parser.add_argument('-t', '--title', type=str, default=None, help='Custom report title (used with -friends)')
    parser.add_argument('-e', '--email', type=str, default=None, help='Additional email recipient')
    parser.add_argument('-eps', type=float, default=None, help='Minimum EPS growth %% (e.g., -eps 20 for 20%% growth)')
    parser.add_argument('-rev', type=float, default=None, help='Minimum revenue growth %% (e.g., -rev 15 for 15%% growth)')
    parser.add_argument('-mc', type=float, default=None, help='Minimum market cap in billions (e.g., -mc 1 for $1B+, default is 10)')
    parser.add_argument('-adr', action='store_true', help='Include international ADRs (American Depositary Receipts)')
    
    args = parser.parse_args()
    
    # Set market cap filter - default $10B, or custom value
    if args.mc is not None:
        scanner = MarketScanner(min_market_cap_billions=args.mc)
    else:
        scanner = MarketScanner()
    
    def apply_growth_filters(results, eps_min=None, rev_min=None):
        """Filter results by EPS and/or revenue growth thresholds.
        
        Logic: 
        - If a filter is specified and stock HAS data: must meet threshold
        - If a filter is specified and stock has NO data: INCLUDE (don't penalize missing data)
        - Use -eps-strict or -rev-strict to require data exists
        """
        if eps_min is None and rev_min is None:
            return results
        
        filtered = []
        eps_available = 0
        rev_available = 0
        eps_passed = 0
        rev_passed = 0
        
        for r in results['all_results']:
            eps_ok = True
            rev_ok = True
            
            # Track data availability
            has_eps = r.get('eps_growth') is not None
            has_rev = r.get('rev_growth') is not None
            
            if has_eps:
                eps_available += 1
            if has_rev:
                rev_available += 1
            
            # EPS filter: only reject if data EXISTS and is below threshold
            if eps_min is not None and has_eps:
                if r.get('eps_growth') >= eps_min:
                    eps_passed += 1
                else:
                    eps_ok = False
            
            # Revenue filter: only reject if data EXISTS and is below threshold  
            if rev_min is not None and has_rev:
                if r.get('rev_growth') >= rev_min:
                    rev_passed += 1
                else:
                    rev_ok = False
            
            if eps_ok and rev_ok:
                filtered.append(r)
        
        # Update results with filtered list
        original_count = len(results['all_results'])
        results['all_results'] = filtered
        results['watchlist_results'] = [r for r in filtered if r.get('is_watchlist', False)]
        results['broad_market_results'] = [r for r in filtered if not r.get('is_watchlist', False)]
        
        filter_desc = []
        if eps_min is not None:
            filter_desc.append(f"EPS≥{eps_min}%")
        if rev_min is not None:
            filter_desc.append(f"Rev≥{rev_min}%")
        
        print(f"\n📊 Growth data availability out of {original_count} stocks:")
        if eps_min is not None:
            print(f"   EPS data: {eps_available} stocks have data, {eps_passed} passed ≥{eps_min}%")
        if rev_min is not None:
            print(f"   Revenue data: {rev_available} stocks have data, {rev_passed} passed ≥{rev_min}%")
        print(f"✓ After filter ({', '.join(filter_desc)}): {len(filtered)} stocks remain")
        print(f"   (Stocks without growth data are included, not excluded)")
        
        return results
    
    # Determine scan mode
    if args.mystocks:
        results = scanner.scan_mystocks_only()
        scanner.results = results
        print("\n" + "="*60)
        print("✓ SCAN COMPLETE!")
        print("="*60)
        
        # Apply growth filters if specified
        if args.eps is not None or args.rev is not None:
            results = apply_growth_filters(results, args.eps, args.rev)
        
        # Load position values for portfolio report
        position_values = {}
        if os.path.exists('mypositions.csv'):
            try:
                import csv
                with open('mypositions.csv', 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        symbol = row.get('Symbol', '').strip().upper()
                        try:
                            value = float(row.get('Value', 0))
                            position_values[symbol] = value
                        except:
                            pass
                print(f"✓ Loaded {len(position_values)} position values from mypositions.csv")
            except Exception as e:
                print(f"⚠️ Could not load mypositions.csv: {e}")
        
        print("\nGenerating portfolio report...")
        from portfolio_report import PortfolioReport
        report = PortfolioReport(results, position_values)
        report.send_email(additional_email=args.email)
        
    elif args.friends:
        results = scanner.scan_friends_only()
        scanner.results = results
        print("\n" + "="*60)
        print("✓ SCAN COMPLETE!")
        print("="*60)
        
        # Apply growth filters if specified
        if args.eps is not None or args.rev is not None:
            results = apply_growth_filters(results, args.eps, args.rev)
        
        print("\nGenerating friends report...")
        from portfolio_report import PortfolioReport
        report = PortfolioReport(results, position_values={}, is_friends_mode=True)
        
        # Use custom title if provided
        custom_title = args.title if args.title else "Friends Portfolio"
        report.send_email(additional_email=args.email, custom_title=custom_title)
    
    elif args.shorts:
        results = scanner.scan_shorts_only()
        scanner.results = results
        print("\n" + "="*60)
        print("✓ SCAN COMPLETE!")
        print("="*60)
        
        print("\nGenerating shorts report...")
        from shorts_report import ShortsReport
        report = ShortsReport(results)
        report.send_email(additional_email=args.email)
    
    elif args.shortscan:
        # Full market scan for short candidates
        results = scanner.run(mystocks_only=False, include_adr=args.adr)
        
        # Apply growth filters if specified
        if args.eps is not None or args.rev is not None:
            results = apply_growth_filters(results, args.eps, args.rev)
        
        # Filter to only SELL zone stocks (potential shorts)
        sell_results = [r for r in results['all_results'] if not r.get('psar_bullish', True)]
        results['all_results'] = sell_results
        results['watchlist_results'] = []
        results['broad_market_results'] = sell_results
        
        print(f"\n📉 Found {len(sell_results)} stocks in SELL zones (potential short candidates)")
        
        print("\nGenerating market short scan report...")
        from shorts_report import ShortsReport
        mc_val = args.mc if args.mc is not None else 10
        report = ShortsReport(results, mc_filter=mc_val, include_adr=args.adr)
        report.send_email(additional_email=args.email)
        
    else:
        # Full market scan
        results = scanner.run(mystocks_only=False, include_adr=args.adr)
        
        # Apply growth filters if specified
        if args.eps is not None or args.rev is not None:
            results = apply_growth_filters(results, args.eps, args.rev)
        
        print("\nGenerating market report...")
        from email_report import EmailReport
        mc_val = args.mc if args.mc is not None else 10
        report = EmailReport(results, eps_filter=args.eps, rev_filter=args.rev, mc_filter=mc_val)
        report.send_email(additional_email=args.email)

import warnings
# Suppress the FutureWarning from ta library
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from ta.trend import MACD, PSARIndicator
from ta.volatility import BollingerBands
from ta.momentum import WilliamsRIndicator, UltimateOscillator, RSIIndicator
from ta.trend import CCIIndicator

class MarketScanner:
    def __init__(self, min_market_cap_billions=10):
        self.results = []
        self.ticker_issues = []
        self.ibd_stats = {}
        self.min_market_cap = min_market_cap_billions * 1_000_000_000  # Convert to dollars
        self.min_market_cap_billions = min_market_cap_billions
        
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
                        # Strip whitespace, BOM characters, and convert to uppercase
                        ticker = line.strip().upper()
                        # Remove any hidden characters
                        ticker = ''.join(c for c in ticker if c.isalnum() or c in '-.')
                        # Skip empty lines, comments, and duplicates
                        if ticker and not ticker.startswith('#') and ticker not in seen:
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
        if os.path.exists('sp500_tickers.csv'):
            try:
                df = pd.read_csv('sp500_tickers.csv')
                tickers = df['Symbol'].tolist()
                print(f"✓ Loaded {len(tickers)} S&P 500 tickers from CSV")
                return tickers
            except Exception as e:
                print(f"✗ Error loading sp500_tickers.csv: {e}")
        return []
    
    def load_nasdaq100_tickers(self):
        """Load NASDAQ 100 from CSV"""
        if os.path.exists('nasdaq100_tickers.csv'):
            try:
                df = pd.read_csv('nasdaq100_tickers.csv')
                tickers = df['Symbol'].tolist()
                print(f"✓ Loaded {len(tickers)} NASDAQ 100 tickers from CSV")
                return tickers
            except Exception as e:
                print(f"✗ Error loading nasdaq100_tickers.csv: {e}")
        return []
    
    def load_russell2000_tickers(self):
        """Load Russell 2000 from CSV"""
        if os.path.exists('russell2000_tickers.csv'):
            try:
                df = pd.read_csv('russell2000_tickers.csv')
                tickers = df['Symbol'].tolist()
                print(f"✓ Loaded {len(tickers)} Russell 2000 tickers from CSV")
                return tickers
            except Exception as e:
                print(f"✗ Error loading russell2000_tickers.csv: {e}")
        return []
    
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
    
    def load_all_tickers_with_sources(self):
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
        
        print(f"\n{'='*60}")
        print(f"TICKER LIST SUMMARY")
        print(f"{'='*60}")
        print(f"Total unique tickers: {len(ticker_sources)}")
        print(f"  - S&P 500: {len([t for t, s in ticker_sources.items() if 'S&P 500' in s])}")
        print(f"  - NASDAQ 100: {len([t for t, s in ticker_sources.items() if 'NASDAQ 100' in s])}")
        print(f"  - Russell 2000 only: {len([t for t, s in ticker_sources.items() if s == 'Russell 2000'])}")
        print(f"  - IBD: {len([t for t, s in ticker_sources.items() if 'IBD' in s])}")
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
        try:
            ticker_obj = yf.Ticker(ticker_symbol)
            hist = ticker_obj.history(period="6mo")
            
            if hist.empty or len(hist) < 50:
                return None
            
            # Get company info
            try:
                info = ticker_obj.info
                company_name = info.get('longName', ticker_symbol)
                market_cap = info.get('marketCap', 0) or 0
                sector = info.get('sector', '') or ''
                quote_type = info.get('quoteType', '') or ''
                
                # Growth estimates from yfinance
                # earningsGrowth = next year EPS growth estimate (as decimal, e.g., 0.25 = 25%)
                # revenueGrowth = next year revenue growth estimate
                eps_growth = info.get('earningsGrowth', None)
                rev_growth = info.get('revenueGrowth', None)
                
                # Convert to percentage if available
                eps_growth_pct = (eps_growth * 100) if eps_growth is not None else None
                rev_growth_pct = (rev_growth * 100) if rev_growth is not None else None
                
            except:
                company_name = ticker_symbol
                market_cap = 0
                sector = ''
                quote_type = ''
                eps_growth_pct = None
                rev_growth_pct = None
            
            # Market cap filter: uses self.min_market_cap (default $10B)
            if not skip_market_cap_filter:
                if market_cap < self.min_market_cap:
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
                return None
            
            # Get dividend yield - FIXED
            dividend_yield = self.get_dividend_yield(ticker_obj)
            
            # Get IBD stats if available
            ibd_data = self.ibd_stats.get(ticker_symbol, {})
            
            result = {
                'ticker': ticker_symbol,
                'company': company_name if company_name else ticker_symbol,
                'source': source,
                'dividend_yield': dividend_yield,
                'market_cap': market_cap,
                'is_reit': is_reit,
                'is_lp': is_lp,
                'eps_growth': eps_growth_pct,
                'rev_growth': rev_growth_pct,
                'composite': ibd_data.get('composite', 'N/A'),
                'eps': ibd_data.get('eps', 'N/A'),
                'rs': ibd_data.get('rs', 'N/A'),
                'smr': ibd_data.get('smr', 'N/A'),
                **indicators
            }
            
            return result
            
        except Exception as e:
            return None
    
    def scan_with_priority(self):
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
        
        all_tickers = self.load_all_tickers_with_sources()
        
        # Remove watchlist tickers
        for ticker in watchlist:
            if ticker in all_tickers:
                del all_tickers[ticker]
        
        print(f"Scanning {len(all_tickers)} stocks from broad market...")
        print(f"This will take 20-30 minutes...\n")
        
        broad_market_results = []
        progress_count = 0
        
        for ticker, source in all_tickers.items():
            try:
                # Skip market cap filter for IBD stocks
                skip_cap = 'IBD' in source
                result = self.scan_ticker_full(ticker, source=source, skip_market_cap_filter=skip_cap)
                if result:
                    result['is_watchlist'] = False
                    broad_market_results.append(result)
                
                progress_count += 1
                if progress_count % 50 == 0:
                    elapsed_pct = progress_count / len(all_tickers) * 100
                    print(f"Progress: {progress_count}/{len(all_tickers)} ({elapsed_pct:.1f}%)")
            except:
                continue
        
        print(f"\n✓ Broad market scan complete: {len(broad_market_results)} signals found")
        
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
                        ticker = line.strip().upper()
                        ticker = ''.join(c for c in ticker if c.isalnum() or c in '-.')
                        if ticker and not ticker.startswith('#') and ticker not in seen:
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
    
    def run(self, mystocks_only=False):
        """Main scanner execution"""
        if mystocks_only:
            results = self.scan_mystocks_only()
        else:
            results = self.scan_with_priority()
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
                        ticker = line.strip().upper()
                        ticker = ''.join(c for c in ticker if c.isalnum() or c in '-.')
                        if ticker and not ticker.startswith('#') and ticker not in seen:
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

if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='PSAR Market Scanner')
    parser.add_argument('-mystocks', action='store_true', help='Scan only mystocks.txt (your portfolio)')
    parser.add_argument('-friends', action='store_true', help='Scan only friends.txt (friend portfolio)')
    parser.add_argument('-t', '--title', type=str, default=None, help='Custom report title (used with -friends)')
    parser.add_argument('-e', '--email', type=str, default=None, help='Additional email recipient')
    parser.add_argument('-eps', type=float, default=None, help='Minimum EPS growth %% (e.g., -eps 20 for 20%% growth)')
    parser.add_argument('-rev', type=float, default=None, help='Minimum revenue growth %% (e.g., -rev 15 for 15%% growth)')
    parser.add_argument('-mc', type=float, default=None, help='Minimum market cap in billions (e.g., -mc 1 for $1B+, default is 10)')
    
    args = parser.parse_args()
    
    # Set market cap filter - default $10B, or custom value
    if args.mc is not None:
        scanner = MarketScanner(min_market_cap_billions=args.mc)
    else:
        scanner = MarketScanner()
    
    def apply_growth_filters(results, eps_min=None, rev_min=None):
        """Filter results by EPS and/or revenue growth thresholds"""
        if eps_min is None and rev_min is None:
            return results
        
        filtered = []
        for r in results['all_results']:
            eps_ok = True
            rev_ok = True
            
            if eps_min is not None:
                eps_growth = r.get('eps_growth')
                if eps_growth is None or eps_growth < eps_min:
                    eps_ok = False
            
            if rev_min is not None:
                rev_growth = r.get('rev_growth')
                if rev_growth is None or rev_growth < rev_min:
                    rev_ok = False
            
            if eps_ok and rev_ok:
                filtered.append(r)
        
        # Update results with filtered list
        results['all_results'] = filtered
        results['watchlist_results'] = [r for r in filtered if r.get('is_watchlist', False)]
        results['broad_market_results'] = [r for r in filtered if not r.get('is_watchlist', False)]
        
        filter_desc = []
        if eps_min is not None:
            filter_desc.append(f"EPS≥{eps_min}%")
        if rev_min is not None:
            filter_desc.append(f"Rev≥{rev_min}%")
        
        print(f"\n✓ Growth filter applied ({', '.join(filter_desc)}): {len(filtered)} stocks passed")
        
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
        
    else:
        # Full market scan
        results = scanner.run(mystocks_only=False)
        
        # Apply growth filters if specified
        if args.eps is not None or args.rev is not None:
            results = apply_growth_filters(results, args.eps, args.rev)
        
        print("\nGenerating market report...")
        from email_report import EmailReport
        mc_val = args.mc if args.mc is not None else 10
        report = EmailReport(results, eps_filter=args.eps, rev_filter=args.rev, mc_filter=mc_val)
        report.send_email(additional_email=args.email)

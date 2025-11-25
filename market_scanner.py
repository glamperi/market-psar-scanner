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
    def __init__(self):
        self.results = []
        self.ticker_issues = []
        self.ibd_stats = {}
        
    def load_custom_watchlist(self):
        """Load priority watchlist from custom_watchlist.txt"""
        watchlist_file = 'custom_watchlist.txt'
        watchlist = []
        
        if os.path.exists(watchlist_file):
            try:
                with open(watchlist_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            watchlist.append(line.upper())
                
                print(f"\n✓ Loaded {len(watchlist)} tickers from custom watchlist")
                for ticker in watchlist:
                    print(f"  - {ticker}")
            except Exception as e:
                print(f"✗ Error loading custom watchlist: {e}")
        else:
            print(f"\nℹ️  No custom watchlist found at {watchlist_file}")
            print(f"   Create one to track your priority positions!")
        
        return watchlist
    
    def load_sp500_tickers_live(self):
        """Get current S&P 500 tickers from Wikipedia"""
        try:
            print("\nFetching live S&P 500 ticker list from Wikipedia...")
            url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
            tables = pd.read_html(url)
            sp500_table = tables[0]
            tickers = sp500_table['Symbol'].tolist()
            tickers = [t.replace('.', '-') for t in tickers]
            print(f"✓ Loaded {len(tickers)} current S&P 500 tickers (live)")
            return tickers
        except Exception as e:
            print(f"⚠️  Failed to load live S&P 500: {e}")
            print("   Falling back to existing method...")
            return self.load_sp500_tickers_fallback()
    
    def load_nasdaq100_tickers_live(self):
        """Get current NASDAQ 100 tickers from Wikipedia"""
        try:
            print("\nFetching live NASDAQ 100 ticker list from Wikipedia...")
            url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
            tables = pd.read_html(url)
            nasdaq_table = tables[4]
            tickers = nasdaq_table['Ticker'].tolist()
            print(f"✓ Loaded {len(tickers)} current NASDAQ 100 tickers (live)")
            return tickers
        except Exception as e:
            print(f"⚠️  Failed to load live NASDAQ 100: {e}")
            print("   Falling back to existing method...")
            return self.load_nasdaq100_tickers_fallback()
    
    def load_russell2000_tickers_live(self):
        """Get current Russell 2000 tickers from iShares IWM"""
        try:
            print("\nFetching live Russell 2000 ticker list from iShares IWM...")
            url = 'https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/1467271812596.ajax?fileType=csv&fileName=IWM_holdings&dataType=fund'
            df = pd.read_csv(url, skiprows=10)
            tickers = df['Ticker'].dropna().tolist()
            tickers = [t.strip() for t in tickers if isinstance(t, str) and t.strip() and t.strip() != '-']
            print(f"✓ Loaded {len(tickers)} current Russell 2000 tickers (live)")
            return tickers
        except Exception as e:
            print(f"⚠️  Failed to load live Russell 2000: {e}")
            print("   Falling back to existing method...")
            return self.load_russell2000_tickers_fallback()
    
    def load_sp500_tickers_fallback(self):
        """Fallback: Load S&P 500 from yfinance"""
        try:
            sp500 = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]
            return sp500['Symbol'].str.replace('.', '-').tolist()
        except:
            return []
    
    def load_nasdaq100_tickers_fallback(self):
        """Fallback: Load NASDAQ 100 from yfinance"""
        try:
            nasdaq = pd.read_html('https://en.wikipedia.org/wiki/Nasdaq-100')[4]
            return nasdaq['Ticker'].tolist()
        except:
            return []
    
    def load_russell2000_tickers_fallback(self):
        """Fallback: Load Russell 2000 from CSV if exists"""
        try:
            if os.path.exists('russell2000_tickers.csv'):
                df = pd.read_csv('russell2000_tickers.csv')
                return df['Symbol'].tolist()
        except:
            pass
        return []
    
    def load_ibd_tickers(self):
        """Load IBD tickers with stats"""
        ibd_tickers = []
        
        if os.path.exists('ibd_stocks_with_stats.csv'):
            try:
                df = pd.read_csv('ibd_stocks_with_stats.csv')
                ibd_tickers = df['Symbol'].tolist()
                
                for _, row in df.iterrows():
                    self.ibd_stats[row['Symbol']] = {
                        'comp_rating': row.get('Comp Rating', 'N/A'),
                        'rs_rating': row.get('RS Rating', 'N/A'),
                        'acc_dis': row.get('Acc/Dis', 'N/A'),
                        'source': row.get('Source', 'IBD')
                    }
                
                print(f"✓ Loaded {len(ibd_tickers)} stocks with IBD stats")
            except Exception as e:
                print(f"⚠️  Error loading IBD stats: {e}")
        
        return ibd_tickers
    
    def get_dividend_yield(self, ticker_obj):
        """Get dividend yield for a ticker"""
        try:
            info = ticker_obj.info
            div_yield = info.get('dividendYield', None)
            if div_yield and div_yield > 0:
                return round(div_yield * 100, 2)
            
            div_rate = info.get('dividendRate', 0)
            price = info.get('currentPrice', info.get('regularMarketPrice', 0))
            if div_rate and price and div_rate > 0:
                return round((div_rate / price) * 100, 2)
            
            return 0
        except:
            return 0
    
    def validate_ticker(self, ticker_symbol):
        """Validate ticker exists and has data"""
        try:
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period="5d")
            
            if hist.empty:
                return None, "No data available"
            
            return ticker_symbol, None
        except Exception as e:
            return None, str(e)
    
    def load_all_tickers_with_sources(self):
        """Load all tickers and track their sources"""
        ticker_sources = {}
        
        print("\n" + "="*60)
        print("LOADING TICKER LISTS")
        print("="*60)
        
        # Load S&P 500
        sp500 = self.load_sp500_tickers_live()
        for ticker in sp500:
            ticker_sources[ticker] = 'S&P 500'
        
        # Load NASDAQ 100
        nasdaq100 = self.load_nasdaq100_tickers_live()
        for ticker in nasdaq100:
            if ticker in ticker_sources:
                ticker_sources[ticker] += ', NASDAQ 100'
            else:
                ticker_sources[ticker] = 'NASDAQ 100'
        
        # Load Russell 2000
        russell2000 = self.load_russell2000_tickers_live()
        for ticker in russell2000:
            if ticker not in ticker_sources:
                ticker_sources[ticker] = 'Russell 2000'
        
        # Load IBD
        ibd_tickers = self.load_ibd_tickers()
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
            
            psar_distance = ((current_price - psar_value) / current_price * 100) if is_bullish else ((psar_value - current_price) / current_price * 100)
            
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
            
            # Day change
            day_change = ((current_price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2] * 100) if len(hist) > 1 else 0
            
            return {
                'price': current_price,
                'psar_value': psar_value,
                'psar_bullish': is_bullish,
                'psar_distance': psar_distance,
                'has_macd': has_macd,
                'has_bb': has_bb,
                'has_willr': has_willr,
                'has_coppock': has_coppock,
                'has_ultimate': has_ultimate,
                'rsi': rsi_value,
                'signal_weight': signal_weight,
                'day_change': day_change
            }
        except Exception as e:
            return None
    
    def scan_ticker_full(self, ticker_symbol, source="Unknown"):
        """Scan a single ticker with full data"""
        try:
            ticker_obj = yf.Ticker(ticker_symbol)
            hist = ticker_obj.history(period="6mo")
            
            if hist.empty or len(hist) < 50:
                return None
            
            # Get company name
            try:
                company_name = ticker_obj.info.get('longName', ticker_symbol)
            except:
                company_name = ticker_symbol
            
            # Calculate indicators
            indicators = self.calculate_indicators(hist)
            if not indicators:
                return None
            
            # Get dividend yield
            dividend_yield = self.get_dividend_yield(ticker_obj)
            
            # Get IBD stats if available
            ibd_data = self.ibd_stats.get(ticker_symbol, {})
            
            result = {
                'ticker': ticker_symbol,
                'company': company_name,
                'source': source,
                'dividend_yield': dividend_yield,
                'comp_rating': ibd_data.get('comp_rating', 'N/A'),
                'rs_rating': ibd_data.get('rs_rating', 'N/A'),
                'acc_dis': ibd_data.get('acc_dis', 'N/A'),
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
            
            validated_ticker, error = self.validate_ticker(ticker)
            
            if not validated_ticker:
                print(f"  ✗ INVALID: {error}")
                self.ticker_issues.append({'ticker': ticker, 'issue': error})
                continue
            
            try:
                result = self.scan_ticker_full(validated_ticker, source="Watchlist")
                if result:
                    result['is_watchlist'] = True
                    watchlist_results.append(result)
                    
                    if result['psar_bullish']:
                        print(f"  ✓ PSAR BUY")
                        print(f"    Distance: {result['psar_distance']:.2f}%")
                        print(f"    Signal Weight: {result['signal_weight']}")
                        print(f"    Price: ${result['price']:.2f}")
                        if result['dividend_yield'] > 0:
                            print(f"    Dividend: {result['dividend_yield']:.2f}%")
                    else:
                        print(f"  ○ PSAR SELL - Not in buy mode")
                else:
                    print(f"  ✗ No data available")
                    self.ticker_issues.append({'ticker': ticker, 'issue': 'No historical data'})
            except Exception as e:
                print(f"  ✗ ERROR: {str(e)}")
                self.ticker_issues.append({'ticker': ticker, 'issue': str(e)})
        
        print(f"\n✓ Watchlist scan complete: {len(watchlist_results)}/{len(watchlist)} successful")
        
        # PHASE 2: SCAN BROAD MARKET
        print("\n" + "="*60)
        print("PHASE 2: SCANNING BROAD MARKET")
        print("="*60)
        
        all_tickers = self.load_all_tickers_with_sources()
        
        # Remove watchlist tickers to avoid duplicates
        for ticker in watchlist:
            if ticker in all_tickers:
                del all_tickers[ticker]
        
        print(f"Scanning {len(all_tickers)} stocks from broad market...")
        print(f"This will take 10-20 minutes...\n")
        
        broad_market_results = []
        progress_count = 0
        
        for ticker, source in all_tickers.items():
            try:
                result = self.scan_ticker_full(ticker, source=source)
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
    
    def run(self):
        """Main scanner execution"""
        results = self.scan_with_priority()
        
        # Save results
        self.results = results
        
        print("\n" + "="*60)
        print("✓ SCAN COMPLETE!")
        print("="*60)
        
        return results

if __name__ == "__main__":
    scanner = MarketScanner()
    results = scanner.run()
    
    # Generate and send email report
    print("\nGenerating email report...")
    from email_report import EmailReport
    report = EmailReport(results)
    report.send_email()

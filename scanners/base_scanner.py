"""
Base Scanner Module
===================
Common functionality for all scanner types.

Provides:
- Data fetching with caching
- Indicator calculation
- Signal generation
- Result formatting
- Progress tracking
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    from utils.config import (
        HISTORY_DAYS, MIN_HISTORY_DAYS,
        DEFAULT_MIN_MARKET_CAP,
        DATA_FILES_DIR, TICKER_FILES, IBD_FILES, USER_FILES
    )
    from indicators import get_all_indicators
    from signals import get_complete_signal, Zone
    from data.ibd_utils import load_ibd_data, get_ibd_url, is_ibd_stock
except ImportError:
    # Fallback for standalone testing
    HISTORY_DAYS = 200
    MIN_HISTORY_DAYS = 50
    DEFAULT_MIN_MARKET_CAP = 5000  # $5 Billion in millions
    DATA_FILES_DIR = 'data_files'
    TICKER_FILES = {}
    IBD_FILES = {}
    USER_FILES = {}


@dataclass
class ScanResult:
    """Result for a single stock scan."""
    ticker: str
    price: float
    zone: str
    zone_emoji: str
    grade: str
    grade_score: int
    entry_allowed: bool
    
    # Key indicators
    psar_gap: float
    psar_days_in_trend: int  # Days since price crossed PSAR (for sorting Strong Buys)
    prsi_bullish: bool
    prsi_emoji: str
    prsi_days_since_flip: int  # Days since PRSI changed direction
    obv_bullish: Optional[bool]
    obv_emoji: str
    momentum: int
    momentum_emoji: str
    atr_percent: float
    trend_score: int
    timing_score: int
    
    # DMI state for filtering
    dmi_state: str  # 'bullish', 'bearish', 'choppy'
    dmi_diff: float  # +DI minus -DI
    
    # Individual checkboxes for display
    dmi_bullish: bool  # +DI > -DI
    adx_strong: bool   # ADX > 25
    macd_bullish: bool # MACD > Signal
    
    # For Early Buy sorting
    williams_r: float  # Williams %R value (-100 to 0)
    
    # Additional info
    warnings: List[str] = field(default_factory=list)
    warnings_emoji: str = ""
    action: str = ""
    
    # Raw ADX value for filtering (has default since it's optional)
    adx_value: float = 0.0
    
    # Optional fields
    source: str = ""
    ibd_stock: bool = False
    ibd_url: Optional[str] = None
    market_cap: Optional[float] = None
    volume: Optional[float] = None
    dividend_yield: Optional[float] = None  # For dividend filtering
    eps_growth: Optional[float] = None  # EPS growth % for filtering
    rev_growth: Optional[float] = None  # Revenue growth % for filtering
    
    # For portfolio mode
    position_value: Optional[float] = None
    shares: Optional[float] = None
    
    # Raw data for detailed analysis
    indicators: Dict = field(default_factory=dict)
    signal_data: Dict = field(default_factory=dict)


@dataclass
class ScanSummary:
    """Summary of scan results."""
    total_scanned: int
    total_passed: int
    by_zone: Dict[str, int]
    by_grade: Dict[str, int]
    strong_buys: List[ScanResult]
    early_buys: List[ScanResult]
    warnings: List[ScanResult]
    scan_time: float
    timestamp: datetime


class BaseScanner:
    """
    Base scanner class with common functionality.
    
    Subclasses should override:
    - get_tickers(): Return list of tickers to scan
    - filter_result(): Apply mode-specific filtering
    - format_result(): Format result for output
    """
    
    def __init__(
        self,
        use_v2: bool = True,
        min_market_cap: float = None,
        include_adr: bool = False,
        eps_filter: Optional[float] = None,
        rev_filter: Optional[float] = None,
        max_workers: int = 10,
        progress_callback: Optional[Callable] = None
    ):
        """
        Initialize scanner.
        
        Args:
            use_v2: Use v2 PRSI-primary logic (default True)
            min_market_cap: Minimum market cap in millions
            include_adr: Include ADR stocks
            eps_filter: Minimum EPS growth %
            rev_filter: Minimum revenue growth %
            max_workers: Max parallel threads for data fetching
            progress_callback: Function to call with progress updates
        """
        self.use_v2 = use_v2
        self.min_market_cap = min_market_cap or DEFAULT_MIN_MARKET_CAP
        self.include_adr = include_adr
        self.eps_filter = eps_filter
        self.rev_filter = rev_filter
        self.max_workers = max_workers
        self.progress_callback = progress_callback
        
        # Cache for data
        self._price_cache: Dict[str, pd.DataFrame] = {}
        self._info_cache: Dict[str, Dict] = {}
        
        # IBD data
        self.ibd_stats = {}
        self.ibd_tickers = set()
        self._load_ibd_data()
    
    def _load_ibd_data(self):
        """Load IBD list data."""
        try:
            self.ibd_stats, ibd_list = load_ibd_data()
            self.ibd_tickers = set(ibd_list)
        except Exception as e:
            print(f"Warning: Could not load IBD data: {e}")
            self.ibd_stats = {}
            self.ibd_tickers = set()
    
    def _report_progress(self, current: int, total: int, ticker: str = "", status: str = ""):
        """Report progress if callback is set."""
        if self.progress_callback:
            self.progress_callback(current, total, ticker, status)
    
    def fetch_data(self, ticker: str, force_refresh: bool = False) -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            force_refresh: Bypass cache
        
        Returns:
            DataFrame with OHLCV data or None if failed
        """
        if not force_refresh and ticker in self._price_cache:
            return self._price_cache[ticker]
        
        if yf is None:
            print("Warning: yfinance not installed")
            return None
        
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=f"{HISTORY_DAYS}d")
            
            if len(df) >= MIN_HISTORY_DAYS:
                self._price_cache[ticker] = df
                return df
            else:
                return None
        except Exception as e:
            return None
    
    def fetch_info(self, ticker: str) -> Dict:
        """Fetch stock info (market cap, etc.)."""
        if ticker in self._info_cache:
            return self._info_cache[ticker]
        
        if yf is None:
            return {}
        
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            self._info_cache[ticker] = info
            return info
        except:
            return {}
    
    def scan_ticker(self, ticker: str, source: str = "") -> Optional[ScanResult]:
        """
        Scan a single ticker.
        
        Args:
            ticker: Stock ticker symbol
            source: Source of the ticker (e.g., "SP500", "IBD 50")
        
        Returns:
            ScanResult or None if scan failed
        """
        # Fetch data
        df = self.fetch_data(ticker)
        if df is None or len(df) < MIN_HISTORY_DAYS:
            return None
        
        try:
            # Calculate all indicators
            indicators = get_all_indicators(df, use_v2=self.use_v2)
            
            if 'error' in indicators:
                return None
            
            # Get complete signal analysis
            signal = get_complete_signal(indicators)
            
            # Check if IBD stock and get info
            is_ibd = ticker in self.ibd_tickers
            ibd_url = None
            dividend_yield = None
            info = self.fetch_info(ticker)
            
            if is_ibd:
                exchange = info.get('exchange', 'NASDAQ')
                ibd_url = get_ibd_url(ticker, self.ibd_stats, exchange)
            
            # Get dividend yield - calculate from rate/price for accuracy
            dividend_yield = None
            dividend_rate = info.get('dividendRate')  # Annual dividend per share in dollars
            current_price = indicators['price']
            
            if dividend_rate and current_price and current_price > 0:
                # Calculate yield directly - most reliable method
                dividend_yield = (dividend_rate / current_price) * 100
            else:
                # Fallback to reported dividendYield with heuristic
                reported_yield = info.get('dividendYield')
                if reported_yield:
                    # yfinance returns dividendYield inconsistently:
                    # - Some stocks: decimal (0.025 = 2.5%)
                    # - Some stocks: already percentage (2.5 = 2.5%)
                    # Heuristic: Real dividend yields rarely exceed 20%
                    if reported_yield < 0.20:
                        dividend_yield = reported_yield * 100
                    else:
                        dividend_yield = reported_yield
            
            market_cap = info.get('marketCap')  # In raw dollars
            
            # Get EPS and Revenue growth
            # yfinance returns these as decimals (0.15 = 15%)
            eps_growth = info.get('earningsGrowth')
            if eps_growth is not None:
                eps_growth = eps_growth * 100  # Convert to percentage
            
            rev_growth = info.get('revenueGrowth')
            if rev_growth is not None:
                rev_growth = rev_growth * 100  # Convert to percentage
            
            # Build result
            result = ScanResult(
                ticker=ticker,
                price=indicators['price'],
                zone=signal['zone_name'],
                zone_emoji=signal['zone_emoji'],
                grade=signal['grade'],
                grade_score=signal['grade_score'],
                entry_allowed=signal['entry_allowed'],
                
                psar_gap=indicators['psar_gap'],
                psar_days_in_trend=indicators.get('psar_days_in_trend', 0),
                prsi_bullish=indicators['prsi_bullish'],
                prsi_emoji='↗️' if indicators['prsi_bullish'] else '↘️',
                prsi_days_since_flip=indicators.get('prsi', {}).get('days_since_flip', 999),
                obv_bullish=indicators['obv_bullish'],
                obv_emoji='🟢' if indicators['obv_bullish'] else ('🔴' if indicators['obv_bullish'] is False else '⚪'),
                momentum=indicators['momentum_score'],
                momentum_emoji=indicators.get('momentum', {}).get('interpretation', {}).get('emoji', ''),
                atr_percent=indicators['atr_percent'],
                trend_score=indicators['trend_score_value'],
                timing_score=indicators['timing_score_value'],
                dmi_state=indicators.get('trend_score', {}).get('dmi_state', 'choppy'),
                dmi_diff=indicators.get('trend_score', {}).get('dmi_diff', 0),
                
                # Checkboxes
                dmi_bullish=indicators.get('dmi_bullish', False),
                adx_strong=indicators.get('adx_strong', False),
                adx_value=indicators.get('adx_value', 0),
                macd_bullish=indicators.get('macd_bullish', False),
                williams_r=indicators.get('williams_r', -50),
                
                warnings=[w.message for w in signal['warnings']],
                warnings_emoji=signal['warnings_display'],
                action=signal['action'],
                
                source=source,
                ibd_stock=is_ibd,
                ibd_url=ibd_url,
                dividend_yield=dividend_yield,
                market_cap=market_cap,
                eps_growth=eps_growth,
                rev_growth=rev_growth,
                
                indicators=indicators,
                signal_data=signal
            )
            
            return result
            
        except Exception as e:
            print(f"Error scanning {ticker}: {e}")
            return None
    
    def filter_result(self, result: ScanResult) -> bool:
        """
        Apply filters to a scan result.
        Override in subclasses for mode-specific filtering.
        
        Args:
            result: ScanResult to filter
        
        Returns:
            True if result passes filters
        """
        # Market cap filter
        if result.market_cap and result.market_cap < self.min_market_cap * 1_000_000:
            return False
        
        # EPS growth filter
        if self.eps_filter is not None:
            if result.eps_growth is None:
                return False  # No EPS data, filter out
            if result.eps_growth < self.eps_filter:
                return False
        
        # Revenue growth filter
        if self.rev_filter is not None:
            if result.rev_growth is None:
                return False  # No revenue data, filter out
            if result.rev_growth < self.rev_filter:
                return False
        
        return True
    
    def get_tickers(self) -> List[tuple]:
        """
        Get list of tickers to scan.
        Override in subclasses.
        
        Returns:
            List of (ticker, source) tuples
        """
        raise NotImplementedError("Subclasses must implement get_tickers()")
    
    def scan(self) -> ScanSummary:
        """
        Run the full scan.
        
        Returns:
            ScanSummary with results
        """
        start_time = time.time()
        
        # Get tickers to scan
        ticker_list = self.get_tickers()
        total = len(ticker_list)
        
        results: List[ScanResult] = []
        
        # Scan with progress reporting
        for i, (ticker, source) in enumerate(ticker_list):
            self._report_progress(i + 1, total, ticker, "Scanning")
            
            result = self.scan_ticker(ticker, source)
            
            if result and self.filter_result(result):
                results.append(result)
        
        # Build summary
        by_zone = {}
        by_grade = {}
        strong_buys = []
        early_buys = []
        warnings_list = []
        
        for r in results:
            by_zone[r.zone] = by_zone.get(r.zone, 0) + 1
            by_grade[r.grade] = by_grade.get(r.grade, 0) + 1
            
            if r.zone == 'STRONG_BUY':
                strong_buys.append(r)
            elif r.zone == 'EARLY_BUY':
                early_buys.append(r)
            elif r.zone == 'WARNING':
                warnings_list.append(r)
        
        scan_time = time.time() - start_time
        
        return ScanSummary(
            total_scanned=total,
            total_passed=len(results),
            by_zone=by_zone,
            by_grade=by_grade,
            strong_buys=strong_buys,
            early_buys=early_buys,
            warnings=warnings_list,
            scan_time=scan_time,
            timestamp=datetime.now()
        )
    
    def scan_parallel(self) -> ScanSummary:
        """
        Run the scan with parallel data fetching.
        
        Returns:
            ScanSummary with results
        """
        start_time = time.time()
        
        ticker_list = self.get_tickers()
        total = len(ticker_list)
        
        results: List[ScanResult] = []
        completed = 0
        
        def scan_one(item):
            ticker, source = item
            return self.scan_ticker(ticker, source)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(scan_one, item): item for item in ticker_list}
            
            for future in as_completed(futures):
                completed += 1
                ticker, source = futures[future]
                self._report_progress(completed, total, ticker, "Scanning")
                
                try:
                    result = future.result()
                    if result and self.filter_result(result):
                        results.append(result)
                except Exception as e:
                    pass
        
        # Build summary (same as sequential)
        by_zone = {}
        by_grade = {}
        strong_buys = []
        early_buys = []
        warnings_list = []
        
        for r in results:
            by_zone[r.zone] = by_zone.get(r.zone, 0) + 1
            by_grade[r.grade] = by_grade.get(r.grade, 0) + 1
            
            if r.zone == 'STRONG_BUY':
                strong_buys.append(r)
            elif r.zone == 'EARLY_BUY':
                early_buys.append(r)
            elif r.zone == 'WARNING':
                warnings_list.append(r)
        
        scan_time = time.time() - start_time
        
        return ScanSummary(
            total_scanned=total,
            total_passed=len(results),
            by_zone=by_zone,
            by_grade=by_grade,
            strong_buys=strong_buys,
            early_buys=early_buys,
            warnings=warnings_list,
            scan_time=scan_time,
            timestamp=datetime.now()
        )


def load_ticker_file(filepath: str) -> List[str]:
    """Load tickers from a file (one per line or CSV)."""
    tickers = []
    
    # Try different encodings
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    
    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Handle CSV format (take first column)
                        ticker = line.split(',')[0].strip()
                        # Clean up ticker - remove quotes, spaces
                        ticker = ticker.replace('"', '').replace("'", '').strip()
                        # Skip headers and empty
                        if ticker and ticker.upper() not in ['SYMBOL', 'TICKER', 'NAME', '']:
                            # Only add valid ticker symbols (letters, dots, hyphens)
                            if ticker.replace('.', '').replace('-', '').isalnum():
                                tickers.append(ticker.upper())
            # If we got here without error, break
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
        except FileNotFoundError:
            break
    
    return tickers


def format_scan_result_row(result: ScanResult, include_position: bool = False) -> str:
    """Format a scan result as a table row."""
    parts = [
        f"{result.zone_emoji}",
        f"{result.ticker:<6}",
        f"${result.price:>8.2f}",
        f"{result.psar_gap:>+6.1f}%",
        f"{result.prsi_emoji}",
        f"{result.obv_emoji}",
        f"M:{result.momentum}",
        f"T:{result.trend_score}",
        f"{result.grade}({result.grade_score})",
    ]
    
    if result.warnings_emoji:
        parts.append(result.warnings_emoji)
    
    if result.ibd_stock:
        parts.append("⭐")
    
    if include_position and result.position_value:
        parts.insert(3, f"${result.position_value:>10,.0f}")
    
    return " ".join(parts)


# =============================================================================
# STANDALONE TESTING
# =============================================================================
if __name__ == "__main__":
    print("Base Scanner Module Test")
    print("=" * 60)
    
    # Test with a simple scanner
    class TestScanner(BaseScanner):
        def get_tickers(self):
            return [
                ("AAPL", "Test"),
                ("NVDA", "Test"),
                ("META", "Test"),
                ("MSTR", "Test"),
            ]
    
    def progress(current, total, ticker, status):
        print(f"  [{current}/{total}] {ticker} - {status}")
    
    scanner = TestScanner(progress_callback=progress)
    
    print("\nScanning test tickers...")
    summary = scanner.scan()
    
    print(f"\n{'='*60}")
    print(f"Scan Complete: {summary.total_passed}/{summary.total_scanned} passed")
    print(f"Time: {summary.scan_time:.1f}s")
    print(f"\nBy Zone: {summary.by_zone}")
    print(f"By Grade: {summary.by_grade}")
    
    if summary.strong_buys:
        print(f"\nStrong Buys:")
        for r in summary.strong_buys:
            print(f"  {format_scan_result_row(r)}")
    
    if summary.early_buys:
        print(f"\nEarly Buys:")
        for r in summary.early_buys:
            print(f"  {format_scan_result_row(r)}")

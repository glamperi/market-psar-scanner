"""
Smart Buy Scanner
=================
Scanner for finding long entry opportunities using V2 logic.

Smart Buy Criteria:
- Price > 50-Day MA (uptrend)
- RSI between 45-65 (healthy, not overheated)
- PSAR Gap < 3% OR Price touching 20-Day MA
- PRSI is Bullish (↗️)
- OBV is Green (accumulation)

Key Improvement over V1:
- Doesn't buy exhausted momentum (9-10)
- Doesn't buy > 5% gap (too risky)
- Prioritizes EARLY_BUY signals (catching turns)
"""

import pandas as pd
from typing import List, Optional, Dict
from dataclasses import dataclass

try:
    from .base_scanner import (
        BaseScanner, ScanResult, ScanSummary,
        load_ticker_file, format_scan_result_row
    )
    from utils.config import (
        DATA_FILES_DIR, TICKER_FILES, IBD_FILES,
        RSI_SMART_BUY_MIN, RSI_SMART_BUY_MAX,
        GAP_EXCELLENT, GAP_MAX,
        MOMENTUM_IDEAL_MIN, MOMENTUM_IDEAL_MAX, MOMENTUM_EXHAUSTED_MIN,
        TREND_SCORE_MIN
    )
except ImportError:
    # For standalone testing
    from base_scanner import BaseScanner, ScanResult, ScanSummary, load_ticker_file, format_scan_result_row
    DATA_FILES_DIR = 'data_files'
    TICKER_FILES = {
        'sp500': f'{DATA_FILES_DIR}/sp500_tickers.csv',
        'nasdaq100': f'{DATA_FILES_DIR}/nasdaq100_tickers.csv',
    }
    IBD_FILES = {}
    RSI_SMART_BUY_MIN = 45
    RSI_SMART_BUY_MAX = 65
    GAP_EXCELLENT = 3.0
    GAP_MAX = 5.0
    MOMENTUM_IDEAL_MIN = 5
    MOMENTUM_IDEAL_MAX = 7
    MOMENTUM_EXHAUSTED_MIN = 9
    TREND_SCORE_MIN = 50


class SmartBuyScanner(BaseScanner):
    """
    Scanner optimized for finding smart long entries.
    
    Focuses on:
    1. EARLY_BUY signals (PRSI turned, price catching up)
    2. Strong trends with good timing
    3. Accumulation (OBV green)
    4. Avoiding exhausted momentum and large gaps
    """
    
    def __init__(
        self,
        scan_sp500: bool = True,
        scan_nasdaq100: bool = True,
        scan_ibd: bool = True,
        custom_tickers: Optional[List[str]] = None,
        **kwargs
    ):
        """
        Initialize Smart Buy scanner.
        
        Args:
            scan_sp500: Include S&P 500 stocks
            scan_nasdaq100: Include NASDAQ 100 stocks
            scan_ibd: Include IBD list stocks
            custom_tickers: Additional tickers to scan
            **kwargs: Passed to BaseScanner
        """
        super().__init__(**kwargs)
        
        self.scan_sp500 = scan_sp500
        self.scan_nasdaq100 = scan_nasdaq100
        self.scan_ibd = scan_ibd
        self.custom_tickers = custom_tickers or []
    
    def get_tickers(self) -> List[tuple]:
        """Get tickers for smart buy scan."""
        tickers = []
        seen = set()
        
        # Custom tickers first (highest priority)
        for ticker in self.custom_tickers:
            if ticker not in seen:
                tickers.append((ticker, "Custom"))
                seen.add(ticker)
        
        # IBD stocks (high priority)
        if self.scan_ibd:
            for ticker in self.ibd_tickers:
                if ticker not in seen:
                    source = self.ibd_stats.get(ticker, {}).get('source', 'IBD')
                    tickers.append((ticker, source))
                    seen.add(ticker)
        
        # S&P 500
        if self.scan_sp500:
            sp500 = load_ticker_file(TICKER_FILES.get('sp500', f'{DATA_FILES_DIR}/sp500_tickers.csv'))
            for ticker in sp500:
                if ticker not in seen:
                    tickers.append((ticker, "SP500"))
                    seen.add(ticker)
        
        # NASDAQ 100
        if self.scan_nasdaq100:
            nasdaq = load_ticker_file(TICKER_FILES.get('nasdaq100', f'{DATA_FILES_DIR}/nasdaq100_tickers.csv'))
            for ticker in nasdaq:
                if ticker not in seen:
                    tickers.append((ticker, "NASDAQ100"))
                    seen.add(ticker)
        
        return tickers
    
    def filter_result(self, result: ScanResult) -> bool:
        """
        Apply Smart Buy filters.
        
        Filters for:
        - Bullish zones (STRONG_BUY, BUY, EARLY_BUY)
        - Entry allowed (gap < 5%, momentum < 9)
        - Minimum trend score
        """
        # Must be base filtered first
        if not super().filter_result(result):
            return False
        
        # Only bullish zones
        bullish_zones = ['STRONG_BUY', 'BUY', 'EARLY_BUY', 'HOLD']
        if result.zone not in bullish_zones:
            return False
        
        # Entry must be allowed (unless HOLD)
        if result.zone != 'HOLD' and not result.entry_allowed:
            return False
        
        # Minimum trend score
        if result.trend_score < TREND_SCORE_MIN:
            return False
        
        return True
    
    def get_smart_buy_candidates(self) -> List[ScanResult]:
        """
        Get the best smart buy candidates.
        
        Returns results sorted by:
        1. EARLY_BUY signals first (catching turns)
        2. Grade A before B
        3. Lower gap is better
        """
        summary = self.scan()
        
        # Combine all bullish results
        results = []
        for r in [summary.strong_buys, summary.early_buys]:
            results.extend(r)
        
        # Sort by priority
        def sort_key(r: ScanResult):
            # Zone priority (EARLY_BUY = 1, STRONG_BUY = 2, BUY = 3)
            zone_priority = {
                'EARLY_BUY': 1,
                'STRONG_BUY': 2,
                'BUY': 3,
                'HOLD': 4
            }.get(r.zone, 5)
            
            # Grade priority (A=1, B=2, C=3)
            grade_priority = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'X': 5}.get(r.grade, 5)
            
            # Gap (lower is better)
            gap = abs(r.psar_gap)
            
            return (zone_priority, grade_priority, gap)
        
        results.sort(key=sort_key)
        
        return results
    
    def get_early_entry_signals(self) -> List[ScanResult]:
        """Get only EARLY_BUY signals (the best opportunities)."""
        summary = self.scan()
        return summary.early_buys
    
    def format_report(self, results: List[ScanResult]) -> str:
        """Format results as a text report."""
        lines = []
        lines.append("=" * 70)
        lines.append("SMART BUY SCAN RESULTS")
        lines.append("=" * 70)
        lines.append("")
        
        # Group by zone
        by_zone = {}
        for r in results:
            if r.zone not in by_zone:
                by_zone[r.zone] = []
            by_zone[r.zone].append(r)
        
        # Print each zone
        zone_order = ['EARLY_BUY', 'STRONG_BUY', 'BUY', 'HOLD']
        
        for zone in zone_order:
            if zone in by_zone:
                zone_results = by_zone[zone]
                lines.append(f"{'='*70}")
                lines.append(f"{zone} ({len(zone_results)} stocks)")
                lines.append("-" * 70)
                lines.append(f"{'Zone':<3} {'Ticker':<7} {'Price':>9} {'Gap':>7} {'PRSI':<4} {'OBV':<3} {'Mom':<4} {'Trend':<5} {'Grade':<6} {'Warn':<8}")
                lines.append("-" * 70)
                
                for r in zone_results:
                    ibd = "⭐" if r.ibd_stock else "  "
                    lines.append(
                        f"{r.zone_emoji:<3} {r.ticker:<6}{ibd} ${r.price:>7.2f} {r.psar_gap:>+6.1f}% "
                        f"{r.prsi_emoji:<4} {r.obv_emoji:<3} {r.momentum:<4} {r.trend_score:<5} "
                        f"{r.grade}({r.grade_score:<2}) {r.warnings_emoji:<8}"
                    )
                
                lines.append("")
        
        return "\n".join(lines)


class PortfolioScanner(SmartBuyScanner):
    """
    Scanner for existing portfolio positions.
    Uses mystocks.txt or mypositions.csv.
    """
    
    def __init__(
        self,
        positions_file: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize portfolio scanner.
        
        Args:
            positions_file: Path to positions file (mystocks.txt or mypositions.csv)
        """
        # Don't scan market indexes
        kwargs['scan_sp500'] = False
        kwargs['scan_nasdaq100'] = False
        kwargs['scan_ibd'] = False
        
        super().__init__(**kwargs)
        
        self.positions_file = positions_file or f'{DATA_FILES_DIR}/mystocks.txt'
        self.positions = self._load_positions()
    
    def _load_positions(self) -> Dict[str, Dict]:
        """Load position data from file."""
        positions = {}
        
        try:
            # Try CSV format first (mypositions.csv)
            csv_file = self.positions_file.replace('.txt', '.csv')
            try:
                df = pd.read_csv(csv_file)
                for _, row in df.iterrows():
                    ticker = str(row.get('ticker', row.get('Symbol', ''))).upper()
                    if ticker:
                        positions[ticker] = {
                            'shares': row.get('shares', row.get('Shares', 0)),
                            'value': row.get('value', row.get('Value', 0)),
                            'cost_basis': row.get('cost_basis', row.get('Cost', 0))
                        }
                return positions
            except:
                pass
            
            # Fall back to text format
            tickers = load_ticker_file(self.positions_file)
            for ticker in tickers:
                positions[ticker] = {'shares': 0, 'value': 0}
        
        except Exception as e:
            print(f"Warning: Could not load positions: {e}")
        
        return positions
    
    def get_tickers(self) -> List[tuple]:
        """Get portfolio tickers."""
        return [(ticker, "Portfolio") for ticker in self.positions.keys()]
    
    def filter_result(self, result: ScanResult) -> bool:
        """Portfolio mode: include all zones (don't filter out sells)."""
        # Add position data
        if result.ticker in self.positions:
            pos = self.positions[result.ticker]
            result.position_value = pos.get('value', 0)
            result.shares = pos.get('shares', 0)
        
        # Include all zones for portfolio analysis
        return True


class FriendsScanner(PortfolioScanner):
    """Scanner for friend's watchlist."""
    
    def __init__(self, friends_file: Optional[str] = None, **kwargs):
        kwargs['positions_file'] = friends_file or f'{DATA_FILES_DIR}/friends.txt'
        super().__init__(**kwargs)
    
    def get_tickers(self) -> List[tuple]:
        """Get friend's tickers."""
        tickers = load_ticker_file(self.positions_file)
        return [(ticker, "Friends") for ticker in tickers]


# =============================================================================
# STANDALONE TESTING
# =============================================================================
if __name__ == "__main__":
    print("Smart Buy Scanner Test")
    print("=" * 60)
    
    def progress(current, total, ticker, status):
        print(f"  [{current}/{total}] {ticker}")
    
    # Test with limited tickers
    scanner = SmartBuyScanner(
        scan_sp500=False,
        scan_nasdaq100=False,
        scan_ibd=False,
        custom_tickers=["AAPL", "NVDA", "META", "GOOGL", "MSTR"],
        progress_callback=progress
    )
    
    print("\nRunning Smart Buy scan...")
    candidates = scanner.get_smart_buy_candidates()
    
    print(f"\n{scanner.format_report(candidates)}")
    
    # Show early entries specifically
    early = [r for r in candidates if r.zone == 'EARLY_BUY']
    if early:
        print("\n⚡ EARLY ENTRY SIGNALS (Best Opportunities):")
        print("-" * 50)
        for r in early:
            print(f"  {r.ticker}: {r.action}")
            print(f"    PRSI: {r.prsi_emoji} | OBV: {r.obv_emoji} | Gap: {r.psar_gap:+.1f}%")

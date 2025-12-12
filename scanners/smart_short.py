"""
Smart Short Scanner V2
======================
Scanner for finding short entry opportunities using PRSI-4 as fast confirmation.

V2 SHORT LOGIC:
- Lead with Price < PSAR (breakdown confirmed)
- Confirm with PRSI-4 bearish (fast 4-day RSI momentum)

Why PRSI-4 for Shorts:
- Shorts move FAST - need faster signal than 14-day
- PRSI-14 is too slow for short entries
- PRSI-4 catches momentum shifts quickly
- Avoids shorting into oversold bounces

Categories:
- 🔴🔴 Strong Short: Price < PSAR + PRSI-4 bearish ≤4 days (fresh)
- 🔴 Short: Price < PSAR + PRSI-4 bearish >4 days (confirmed)
- ⚡ Early Short: Price > PSAR + PRSI-4 bearish ≤4 days (anticipating)

HARD FILTERS (never short):
- RSI-14 < 30 (oversold, bounce risk)
- PRSI-4 bearish > 10 days (move exhausted)
- OBV green (accumulation = buying pressure)
"""

import pandas as pd
from typing import List, Optional, Dict
from dataclasses import dataclass, field

try:
    from .base_scanner import (
        BaseScanner, ScanResult, ScanSummary,
        load_ticker_file, format_scan_result_row
    )
    from utils.config import (
        DATA_FILES_DIR,
        RSI_NO_SHORT_BELOW,
    )
except ImportError:
    from base_scanner import BaseScanner, ScanResult, ScanSummary, load_ticker_file, format_scan_result_row
    DATA_FILES_DIR = 'data_files'
    RSI_NO_SHORT_BELOW = 30


# Short-specific config
PRSI4_MAX_DAYS = 10  # Don't short if PRSI-4 bearish > 10 days (exhausted)
PRSI4_FRESH_DAYS = 4  # Fresh signal threshold


@dataclass
class ShortCandidate:
    """Enhanced result for short candidates."""
    result: ScanResult
    category: str  # 'strong_short', 'short', 'early_short', 'invalid'
    short_score: int  # 0-100 quality score
    prsi4_bearish: bool
    prsi4_days: int
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    invalid_reason: Optional[str] = None


class SmartShortScanner(BaseScanner):
    """
    Scanner for finding smart short entries using PRSI-4.
    
    V2 LOGIC:
    1. Lead with Price < PSAR (confirmed breakdown)
    2. Confirm with PRSI-4 bearish (fast momentum)
    
    NEVER short:
    - RSI-14 < 30 (oversold bounce risk)
    - PRSI-4 bearish > 10 days (exhausted)
    - OBV green (accumulation)
    """
    
    def __init__(
        self,
        shorts_file: Optional[str] = None,
        scan_market: bool = False,
        scan_sp500: bool = True,
        scan_nasdaq100: bool = True,
        scan_russell2000: bool = True,
        **kwargs
    ):
        """
        Initialize Smart Short scanner.
        
        Args:
            shorts_file: File with short candidates to scan
            scan_market: If True, scan full market (for -shortscan mode)
            scan_sp500: Include S&P 500 in market scan
            scan_nasdaq100: Include NASDAQ 100 in market scan  
            scan_russell2000: Include Russell 2000 in market scan
        """
        super().__init__(**kwargs)
        
        self.shorts_file = shorts_file or f'{DATA_FILES_DIR}/shorts.txt'
        self.scan_market = scan_market
        self.scan_sp500 = scan_sp500
        self.scan_nasdaq100 = scan_nasdaq100
        self.scan_russell2000 = scan_russell2000
    
    def get_tickers(self) -> List[tuple]:
        """Get tickers for short scan."""
        tickers = []
        seen = set()
        
        if self.scan_market:
            # Market-wide scan (-shortscan mode)
            if self.scan_sp500:
                sp500 = load_ticker_file(f'{DATA_FILES_DIR}/sp500_tickers.csv')
                for ticker in sp500:
                    if ticker not in seen:
                        tickers.append((ticker, "SP500"))
                        seen.add(ticker)
            
            if self.scan_nasdaq100:
                nasdaq = load_ticker_file(f'{DATA_FILES_DIR}/nasdaq100_tickers.csv')
                for ticker in nasdaq:
                    if ticker not in seen:
                        tickers.append((ticker, "NASDAQ100"))
                        seen.add(ticker)
            
            if self.scan_russell2000:
                russell = load_ticker_file(f'{DATA_FILES_DIR}/russell2000_tickers.csv')
                for ticker in russell:
                    if ticker not in seen:
                        tickers.append((ticker, "Russell2000"))
                        seen.add(ticker)
        else:
            # Watchlist mode (-shorts mode) - scan shorts.txt
            shorts_list = load_ticker_file(self.shorts_file)
            for ticker in shorts_list:
                if ticker not in seen:
                    tickers.append((ticker, "Shorts"))
                    seen.add(ticker)
        
        return tickers
    
    def evaluate_short(self, result: ScanResult) -> ShortCandidate:
        """
        Evaluate a stock as a short candidate using V2 PRSI-4 logic.
        
        Returns:
            ShortCandidate with category and evaluation
        """
        reasons = []
        warnings = []
        short_score = 50  # Start neutral
        
        # Get PRSI data
        prsi_data = result.indicators.get('prsi', {}).get('prsi_data', {})
        rsi_14 = prsi_data.get('rsi', 50)
        prsi4_bearish = not prsi_data.get('is_bullish_fast', True)  # Inverted: not bullish = bearish
        prsi4_days = prsi_data.get('days_since_flip_fast', 0)
        
        # Price vs PSAR
        price_below_psar = result.psar_gap < 0
        
        # =================================================================
        # HARD BLOCKS - Never short these
        # =================================================================
        
        # RULE 1: Never short RSI-14 < 30 (oversold bounce risk)
        if rsi_14 < RSI_NO_SHORT_BELOW:
            return ShortCandidate(
                result=result,
                category='invalid',
                short_score=0,
                prsi4_bearish=prsi4_bearish,
                prsi4_days=prsi4_days,
                warnings=[f"RSI-14 = {rsi_14:.0f} < 30 - OVERSOLD, bounce risk"],
                invalid_reason=f"RSI {rsi_14:.0f} oversold - never short"
            )
        
        # RULE 2: Never short if PRSI-4 bearish > 10 days (exhausted move)
        if prsi4_bearish and prsi4_days > PRSI4_MAX_DAYS:
            return ShortCandidate(
                result=result,
                category='invalid',
                short_score=0,
                prsi4_bearish=prsi4_bearish,
                prsi4_days=prsi4_days,
                warnings=[f"PRSI-4 bearish {prsi4_days}d > 10d - move exhausted"],
                invalid_reason=f"PRSI-4 bearish {prsi4_days}d - too late"
            )
        
        # RULE 3: Don't short if PRSI-4 is bullish (momentum turning up)
        if not prsi4_bearish:
            return ShortCandidate(
                result=result,
                category='invalid',
                short_score=0,
                prsi4_bearish=prsi4_bearish,
                prsi4_days=prsi4_days,
                warnings=["PRSI-4 bullish ↗️ - momentum turning up"],
                invalid_reason="PRSI-4 bullish - wrong direction"
            )
        
        # RULE 4: Warning if OBV green (accumulation = buying pressure)
        if result.obv_bullish is True:
            warnings.append("OBV green 🟢 - accumulation detected")
            short_score -= 15
        
        # =================================================================
        # CATEGORIZATION based on V2 Logic
        # =================================================================
        
        # PRSI-4 is bearish (passed filters above)
        reasons.append(f"PRSI-4 bearish ↘️ ({prsi4_days}d)")
        
        if price_below_psar:
            # Price < PSAR = confirmed breakdown
            reasons.append(f"Price < PSAR ({result.psar_gap:+.1f}%)")
            
            if prsi4_days <= PRSI4_FRESH_DAYS:
                # 🔴🔴 STRONG SHORT: Fresh breakdown + fresh PRSI-4
                category = 'strong_short'
                short_score += 25
                reasons.append("Fresh signal - optimal entry")
            else:
                # 🔴 SHORT: Confirmed but older
                category = 'short'
                short_score += 15
                reasons.append("Confirmed downtrend")
        else:
            # Price > PSAR but PRSI-4 bearish = Early Short signal
            if prsi4_days <= PRSI4_FRESH_DAYS:
                # ⚡ EARLY SHORT: PRSI-4 turned, price hasn't broken yet
                category = 'early_short'
                short_score += 20
                reasons.append("Early signal - anticipating breakdown")
                reasons.append(f"Price still above PSAR ({result.psar_gap:+.1f}%)")
            else:
                # PRSI-4 bearish for a while but price holding = weak signal
                category = 'short'
                short_score += 5
                warnings.append("PRSI-4 bearish but price holding above PSAR")
        
        # =================================================================
        # BONUS SCORING
        # =================================================================
        
        # OBV distribution (red) confirms selling
        if result.obv_bullish is False:
            reasons.append("OBV distribution 🔴")
            short_score += 10
        
        # RSI-14 in ideal short zone (40-60 = recovered bounce, good to short)
        if 40 <= rsi_14 <= 60:
            reasons.append(f"RSI-14 = {rsi_14:.0f} (ideal zone)")
            short_score += 10
        elif rsi_14 > 60:
            warnings.append(f"RSI-14 = {rsi_14:.0f} (still strong)")
            short_score -= 5
        
        # Low trend score = weak stock = good short
        if result.trend_score < 40:
            reasons.append(f"Weak trend score ({result.trend_score})")
            short_score += 10
        elif result.trend_score > 60:
            warnings.append(f"Strong trend ({result.trend_score})")
            short_score -= 10
        
        # Smaller PSAR gap = less risk
        if -5 < result.psar_gap < 0:
            reasons.append("Manageable PSAR gap")
            short_score += 5
        elif result.psar_gap < -8:
            warnings.append(f"Large PSAR gap ({result.psar_gap:.1f}%) = extended")
            short_score -= 10
        
        # Clamp score
        short_score = max(0, min(100, short_score))
        
        return ShortCandidate(
            result=result,
            category=category,
            short_score=short_score,
            prsi4_bearish=prsi4_bearish,
            prsi4_days=prsi4_days,
            reasons=reasons,
            warnings=warnings
        )
    
    def filter_result(self, result: ScanResult) -> bool:
        """Include all results for short evaluation."""
        return True
    
    def get_short_candidates(self) -> List[ShortCandidate]:
        """
        Get evaluated short candidates.
        
        Returns:
            List of ShortCandidate sorted by category then score
        """
        # Scan all tickers
        ticker_list = self.get_tickers()
        
        candidates = []
        total = len(ticker_list)
        
        for i, (ticker, source) in enumerate(ticker_list):
            if self.progress_callback:
                self.progress_callback(i + 1, total, ticker, "scanning")
            
            result = self.scan_ticker(ticker, source)
            if result:
                candidate = self.evaluate_short(result)
                candidates.append(candidate)
        
        # Sort by category priority then score
        def sort_key(c: ShortCandidate):
            cat_priority = {
                'strong_short': 1,
                'early_short': 2,
                'short': 3,
                'invalid': 4
            }.get(c.category, 5)
            return (cat_priority, -c.short_score, c.prsi4_days)
        
        candidates.sort(key=sort_key)
        
        return candidates
    
    def get_valid_shorts(self) -> List[ShortCandidate]:
        """Get only valid short candidates."""
        all_candidates = self.get_short_candidates()
        return [c for c in all_candidates if c.category != 'invalid']
    
    def get_strong_shorts(self) -> List[ShortCandidate]:
        """Get only strong short signals."""
        all_candidates = self.get_short_candidates()
        return [c for c in all_candidates if c.category == 'strong_short']
    
    def get_early_shorts(self) -> List[ShortCandidate]:
        """Get early short signals (anticipating breakdown)."""
        all_candidates = self.get_short_candidates()
        return [c for c in all_candidates if c.category == 'early_short']
    
    def format_report(self, candidates: List[ShortCandidate]) -> str:
        """Format short candidates as a text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("SMART SHORT SCANNER V2 (PRSI-4)")
        lines.append("=" * 80)
        lines.append("")
        lines.append("V2 LOGIC:")
        lines.append("  • Lead with Price < PSAR (breakdown confirmed)")
        lines.append("  • Confirm with PRSI-4 bearish (fast momentum)")
        lines.append("")
        lines.append("NEVER SHORT:")
        lines.append("  • RSI-14 < 30 (oversold bounce risk)")
        lines.append("  • PRSI-4 bearish > 10 days (exhausted)")
        lines.append("  • PRSI-4 bullish (momentum turning up)")
        lines.append("")
        
        # Group by category
        strong = [c for c in candidates if c.category == 'strong_short']
        early = [c for c in candidates if c.category == 'early_short']
        shorts = [c for c in candidates if c.category == 'short']
        invalid = [c for c in candidates if c.category == 'invalid']
        
        # Strong Shorts
        if strong:
            lines.append("=" * 80)
            lines.append(f"🔴🔴 STRONG SHORT ({len(strong)}) - Fresh breakdown + fresh PRSI-4")
            lines.append("-" * 80)
            lines.append(f"{'Ticker':<8} {'Price':>9} {'PSAR%':>8} {'PRSI4':>8} {'Days':>5} {'Score':>6} {'OBV':>4}")
            lines.append("-" * 80)
            
            for c in strong:
                r = c.result
                prsi4_emoji = "↘️" if c.prsi4_bearish else "↗️"
                lines.append(
                    f"{r.ticker:<8} ${r.price:>7.2f} {r.psar_gap:>+7.1f}% "
                    f"{prsi4_emoji:>6} {c.prsi4_days:>5}d {c.short_score:>5} {r.obv_emoji:>4}"
                )
            lines.append("")
        
        # Early Shorts
        if early:
            lines.append("=" * 80)
            lines.append(f"⚡ EARLY SHORT ({len(early)}) - PRSI-4 bearish, price hasn't broken yet")
            lines.append("-" * 80)
            lines.append(f"{'Ticker':<8} {'Price':>9} {'PSAR%':>8} {'PRSI4':>8} {'Days':>5} {'Score':>6} {'OBV':>4}")
            lines.append("-" * 80)
            
            for c in early:
                r = c.result
                prsi4_emoji = "↘️" if c.prsi4_bearish else "↗️"
                lines.append(
                    f"{r.ticker:<8} ${r.price:>7.2f} {r.psar_gap:>+7.1f}% "
                    f"{prsi4_emoji:>6} {c.prsi4_days:>5}d {c.short_score:>5} {r.obv_emoji:>4}"
                )
            lines.append("")
        
        # Regular Shorts
        if shorts:
            lines.append("=" * 80)
            lines.append(f"🔴 SHORT ({len(shorts)}) - Confirmed but not as fresh")
            lines.append("-" * 80)
            lines.append(f"{'Ticker':<8} {'Price':>9} {'PSAR%':>8} {'PRSI4':>8} {'Days':>5} {'Score':>6} {'OBV':>4}")
            lines.append("-" * 80)
            
            for c in shorts:
                r = c.result
                prsi4_emoji = "↘️" if c.prsi4_bearish else "↗️"
                lines.append(
                    f"{r.ticker:<8} ${r.price:>7.2f} {r.psar_gap:>+7.1f}% "
                    f"{prsi4_emoji:>6} {c.prsi4_days:>5}d {c.short_score:>5} {r.obv_emoji:>4}"
                )
            lines.append("")
        
        # Invalid (DO NOT SHORT)
        if invalid:
            lines.append("=" * 80)
            lines.append(f"🚫 DO NOT SHORT ({len(invalid)})")
            lines.append("-" * 80)
            
            for c in invalid[:20]:  # Limit to 20
                r = c.result
                lines.append(f"{r.ticker:<8} - {c.invalid_reason}")
            
            if len(invalid) > 20:
                lines.append(f"  ... and {len(invalid) - 20} more")
            lines.append("")
        
        # Summary
        lines.append("=" * 80)
        lines.append(f"SUMMARY: {len(strong)} Strong | {len(early)} Early | {len(shorts)} Short | {len(invalid)} Invalid")
        lines.append("=" * 80)
        
        return "\n".join(lines)


# =============================================================================
# STANDALONE TESTING
# =============================================================================
if __name__ == "__main__":
    print("Smart Short Scanner V2 Test")
    print("=" * 60)
    
    def progress(current, total, ticker, status):
        print(f"  [{current}/{total}] {ticker}")
    
    # Create a test scanner with specific tickers
    class TestShortScanner(SmartShortScanner):
        def get_tickers(self):
            return [
                ("NVDA", "Test"),
                ("MSTR", "Test"),
                ("META", "Test"),
                ("INTC", "Test"),
                ("AAPL", "Test"),
            ]
    
    scanner = TestShortScanner(progress_callback=progress)
    
    print("\nEvaluating short candidates with V2 logic...")
    candidates = scanner.get_short_candidates()
    
    print(f"\n{scanner.format_report(candidates)}")

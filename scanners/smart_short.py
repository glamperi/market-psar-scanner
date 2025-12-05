"""
Smart Short Scanner
===================
Scanner for finding short entry opportunities using V2 logic.

Smart Short Criteria (FIXED from V1):
- Price < 50-Day MA (downtrend)
- RSI between 40-60 (recovered from crash, NOT capitulating)
- Price rallying toward resistance (bounce to short)
- PRSI is Bearish (↘️) or just flipped
- HARD RULE: NEVER short if RSI < 35 (capitulation zone)

Key Fix from V1:
V1 Error: Shorting deep negative PSAR (-9%, -12%) = shorting into support
V2 Fix: Short SMALL negative PSAR that is rolling over = shorting resistance

The best short is NOT when a stock has already crashed,
but when it bounces back toward resistance and fails.
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
        DATA_FILES_DIR,
        RSI_SMART_SHORT_MIN, RSI_SMART_SHORT_MAX, RSI_NO_SHORT_BELOW,
        GAP_EXCELLENT, GAP_MAX,
        TREND_SCORE_MIN
    )
except ImportError:
    from base_scanner import BaseScanner, ScanResult, ScanSummary, load_ticker_file, format_scan_result_row
    DATA_FILES_DIR = 'data_files'
    RSI_SMART_SHORT_MIN = 40
    RSI_SMART_SHORT_MAX = 60
    RSI_NO_SHORT_BELOW = 35
    GAP_EXCELLENT = 3.0
    GAP_MAX = 5.0
    TREND_SCORE_MIN = 50


@dataclass
class ShortCandidate:
    """Enhanced result for short candidates."""
    result: ScanResult
    short_score: int  # 0-100 short quality score
    short_reasons: List[str]
    short_warnings: List[str]
    is_valid_short: bool
    invalid_reason: Optional[str] = None


class SmartShortScanner(BaseScanner):
    """
    Scanner optimized for finding smart short entries.
    
    CRITICAL RULES:
    1. NEVER short RSI < 35 (oversold/capitulation)
    2. NEVER short deep negative PSAR (already crashed)
    3. Look for bounces to resistance that fail
    4. Require PRSI bearish confirmation
    5. OBV red (distribution) is ideal
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
        Evaluate a stock as a short candidate.
        
        This is the FIXED logic that addresses V1 problems.
        
        Returns:
            ShortCandidate with evaluation
        """
        short_score = 50  # Start neutral
        reasons = []
        warnings = []
        is_valid = True
        invalid_reason = None
        
        # Get RSI from indicators
        prsi_data = result.indicators.get('prsi', {}).get('prsi_data', {})
        rsi = prsi_data.get('rsi', 50)
        
        # =================================================================
        # HARD BLOCKS - These invalidate the short
        # =================================================================
        
        # RULE 1: NEVER short if RSI < 35
        if rsi < RSI_NO_SHORT_BELOW:
            is_valid = False
            invalid_reason = f"RSI {rsi:.0f} < 35 - NEVER short oversold/capitulation"
            return ShortCandidate(
                result=result,
                short_score=0,
                short_reasons=[],
                short_warnings=[invalid_reason],
                is_valid_short=False,
                invalid_reason=invalid_reason
            )
        
        # RULE 2: NEVER short deep negative PSAR (already crashed)
        if result.psar_gap < -8:
            is_valid = False
            invalid_reason = f"PSAR gap {result.psar_gap:.1f}% too negative - already crashed"
            return ShortCandidate(
                result=result,
                short_score=0,
                short_reasons=[],
                short_warnings=[invalid_reason],
                is_valid_short=False,
                invalid_reason=invalid_reason
            )
        
        # RULE 3: Don't short if OBV is green (accumulation)
        if result.obv_bullish is True:
            warnings.append("OBV green - accumulation detected, risky short")
            short_score -= 20
        
        # =================================================================
        # SCORING - What makes a GOOD short
        # =================================================================
        
        # PRSI bearish is essential
        if not result.prsi_bullish:
            reasons.append("PRSI bearish ↘️")
            short_score += 15
        else:
            warnings.append("PRSI still bullish - wait for flip")
            short_score -= 15
        
        # OBV distribution (red) is ideal
        if result.obv_bullish is False:
            reasons.append("OBV shows distribution 🔴")
            short_score += 15
        
        # RSI in ideal short zone (40-60, recovered but not strong)
        if RSI_SMART_SHORT_MIN <= rsi <= RSI_SMART_SHORT_MAX:
            reasons.append(f"RSI {rsi:.0f} in ideal short zone")
            short_score += 10
        elif rsi > RSI_SMART_SHORT_MAX:
            warnings.append(f"RSI {rsi:.0f} still strong - may have more upside")
            short_score -= 10
        
        # Small negative PSAR is better than deep negative
        if -5 < result.psar_gap < 0:
            reasons.append(f"Small PSAR gap ({result.psar_gap:.1f}%) - good risk/reward")
            short_score += 10
        elif result.psar_gap >= 0:
            # Price still above PSAR - could be early short signal
            if not result.prsi_bullish:
                reasons.append("Price above PSAR but PRSI bearish - early short signal")
                short_score += 5
            else:
                warnings.append("Price still above PSAR and PRSI bullish - too early")
                short_score -= 10
        
        # Low trend score is good for shorts
        if result.trend_score < 40:
            reasons.append(f"Weak trend score ({result.trend_score})")
            short_score += 10
        elif result.trend_score > 60:
            warnings.append(f"Strong trend score ({result.trend_score}) - risky short")
            short_score -= 10
        
        # Momentum rolling over
        if result.momentum <= 4:
            reasons.append(f"Low momentum ({result.momentum})")
            short_score += 5
        elif result.momentum >= 7:
            warnings.append(f"High momentum ({result.momentum}) - risky short")
            short_score -= 10
        
        # ATR - slightly overbought is good for shorts (shorting the bounce)
        if result.atr_percent > 2:
            reasons.append(f"Extended above average (ATR +{result.atr_percent:.0f}%)")
            short_score += 10
        
        # Clamp score
        short_score = max(0, min(100, short_score))
        
        # Determine if valid short
        if short_score < 40:
            is_valid = False
            invalid_reason = "Short score too low"
        
        return ShortCandidate(
            result=result,
            short_score=short_score,
            short_reasons=reasons,
            short_warnings=warnings,
            is_valid_short=is_valid,
            invalid_reason=invalid_reason
        )
    
    def filter_result(self, result: ScanResult) -> bool:
        """Include all results for short evaluation."""
        return True
    
    def get_short_candidates(self) -> List[ShortCandidate]:
        """
        Get evaluated short candidates.
        
        Returns:
            List of ShortCandidate sorted by short_score
        """
        summary = self.scan()
        
        candidates = []
        
        # Evaluate each result as a potential short
        # We need to re-scan to get full results, not just summary
        ticker_list = self.get_tickers()
        
        for ticker, source in ticker_list:
            result = self.scan_ticker(ticker, source)
            if result:
                candidate = self.evaluate_short(result)
                candidates.append(candidate)
        
        # Sort by short score (highest first)
        candidates.sort(key=lambda c: c.short_score, reverse=True)
        
        return candidates
    
    def get_valid_shorts(self) -> List[ShortCandidate]:
        """Get only valid short candidates."""
        all_candidates = self.get_short_candidates()
        return [c for c in all_candidates if c.is_valid_short]
    
    def get_invalid_shorts(self) -> List[ShortCandidate]:
        """Get stocks that should NOT be shorted (with reasons)."""
        all_candidates = self.get_short_candidates()
        return [c for c in all_candidates if not c.is_valid_short]
    
    def format_report(self, candidates: List[ShortCandidate]) -> str:
        """Format short candidates as a text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("SMART SHORT SCAN RESULTS")
        lines.append("=" * 80)
        lines.append("")
        lines.append("CRITICAL RULES:")
        lines.append("  • NEVER short RSI < 35 (oversold/capitulation)")
        lines.append("  • NEVER short deep negative PSAR (already crashed)")
        lines.append("  • Look for bounces to resistance that fail")
        lines.append("")
        
        # Valid shorts
        valid = [c for c in candidates if c.is_valid_short]
        invalid = [c for c in candidates if not c.is_valid_short]
        
        if valid:
            lines.append("=" * 80)
            lines.append(f"✅ VALID SHORT CANDIDATES ({len(valid)})")
            lines.append("-" * 80)
            
            for c in valid:
                r = c.result
                lines.append(f"\n{r.ticker} - Short Score: {c.short_score}/100")
                lines.append(f"  Price: ${r.price:.2f} | PSAR: {r.psar_gap:+.1f}% | PRSI: {r.prsi_emoji} | OBV: {r.obv_emoji}")
                lines.append(f"  Reasons:")
                for reason in c.short_reasons:
                    lines.append(f"    ✓ {reason}")
                if c.short_warnings:
                    lines.append(f"  Warnings:")
                    for warn in c.short_warnings:
                        lines.append(f"    ⚠️ {warn}")
        
        if invalid:
            lines.append("")
            lines.append("=" * 80)
            lines.append(f"🚫 DO NOT SHORT ({len(invalid)})")
            lines.append("-" * 80)
            
            for c in invalid:
                r = c.result
                lines.append(f"\n{r.ticker} - {c.invalid_reason}")
                lines.append(f"  Price: ${r.price:.2f} | PSAR: {r.psar_gap:+.1f}%")
                if c.short_warnings:
                    for warn in c.short_warnings:
                        lines.append(f"    🚫 {warn}")
        
        return "\n".join(lines)


# =============================================================================
# STANDALONE TESTING
# =============================================================================
if __name__ == "__main__":
    print("Smart Short Scanner Test")
    print("=" * 60)
    
    def progress(current, total, ticker, status):
        print(f"  [{current}/{total}] {ticker}")
    
    # Create a test scanner with specific tickers
    class TestShortScanner(SmartShortScanner):
        def get_tickers(self):
            # Test with stocks from the analysis
            return [
                ("NVDA", "Test"),   # Was flagged as SELL with -6.3% PSAR
                ("MSTR", "Test"),   # Was flagged as SELL with -9.3% PSAR (should be invalid)
                ("META", "Test"),   # Was STRONG_BUY - probably not a short
                ("INTC", "Test"),   # Often weak
            ]
    
    scanner = TestShortScanner(progress_callback=progress)
    
    print("\nEvaluating short candidates...")
    candidates = scanner.get_short_candidates()
    
    print(f"\n{scanner.format_report(candidates)}")
    
    # Summary
    valid = [c for c in candidates if c.is_valid_short]
    invalid = [c for c in candidates if not c.is_valid_short]
    
    print(f"\n{'='*60}")
    print(f"Summary: {len(valid)} valid shorts, {len(invalid)} invalid")
    print(f"{'='*60}")

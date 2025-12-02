"""
Console Report
==============
Terminal output formatting for scan results.

Provides colored, formatted output for command-line usage.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    from signals import Zone, ZONE_CONFIG
except ImportError:
    ZONE_CONFIG = {}


# ANSI color codes
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'


ZONE_COLORS_CONSOLE = {
    'STRONG_BUY': Colors.GREEN + Colors.BOLD,
    'BUY': Colors.GREEN,
    'EARLY_BUY': Colors.CYAN + Colors.BOLD,
    'HOLD': Colors.YELLOW,
    'NEUTRAL': Colors.GRAY,
    'WARNING': Colors.YELLOW + Colors.BOLD,
    'WEAK': Colors.RED,
    'SELL': Colors.RED + Colors.BOLD,
    'OVERSOLD_WATCH': Colors.MAGENTA,
}


def colorize(text: str, color: str) -> str:
    """Apply ANSI color to text."""
    return f"{color}{text}{Colors.RESET}"


def format_result_line(result: Any, width: int = 100) -> str:
    """
    Format a single result as a console line.
    
    Args:
        result: ScanResult object
        width: Total line width
    """
    zone_color = ZONE_COLORS_CONSOLE.get(result.zone, Colors.RESET)
    
    # IBD indicator
    ibd = "⭐" if result.ibd_stock else "  "
    
    # Build line
    line = (
        f"{result.zone_emoji:<3} "
        f"{result.ticker:<6}{ibd} "
        f"${result.price:>8.2f} "
        f"{result.psar_gap:>+6.1f}% "
        f"{result.prsi_emoji} "
        f"{result.obv_emoji} "
        f"M:{result.momentum:<2}{result.momentum_emoji:<2} "
        f"T:{result.trend_score:<3} "
        f"{result.grade}({result.grade_score:<2}) "
        f"{result.warnings_emoji}"
    )
    
    return colorize(line, zone_color)


def format_header(width: int = 100) -> str:
    """Format table header."""
    header = (
        f"{'Zone':<4} "
        f"{'Ticker':<9} "
        f"{'Price':>9} "
        f"{'PSAR%':>7} "
        f"{'PRSI':<4} "
        f"{'OBV':<3} "
        f"{'Mom':<6} "
        f"{'Trend':<5} "
        f"{'Grade':<6} "
        f"{'Warnings'}"
    )
    return colorize(header, Colors.BOLD)


def format_separator(char: str = '-', width: int = 100) -> str:
    """Format a separator line."""
    return char * width


def print_zone_section(
    zone: str,
    results: List[Any],
    show_header: bool = True
):
    """
    Print a zone section to console.
    
    Args:
        zone: Zone name
        results: List of ScanResults
        show_header: Whether to show column header
    """
    if not results:
        return
    
    zone_color = ZONE_COLORS_CONSOLE.get(zone, Colors.RESET)
    zone_emoji = ZONE_CONFIG.get(Zone[zone], {}).get('emoji', '') if zone in Zone.__members__ else ''
    
    print()
    print(colorize(f"{'='*80}", zone_color))
    print(colorize(f"{zone_emoji} {zone} ({len(results)} stocks)", zone_color + Colors.BOLD))
    print(colorize(f"{'='*80}", zone_color))
    
    if show_header:
        print(format_header())
        print(format_separator('-', 80))
    
    for result in results:
        print(format_result_line(result))


def print_summary(summary: Any):
    """Print scan summary to console."""
    print()
    print(colorize("="*80, Colors.BOLD))
    print(colorize("SCAN SUMMARY", Colors.BOLD))
    print(colorize("="*80, Colors.BOLD))
    
    print(f"Scanned: {summary.total_scanned} | Passed: {summary.total_passed}")
    print(f"Time: {summary.scan_time:.1f}s | {summary.timestamp.strftime('%Y-%m-%d %H:%M')}")
    
    print()
    print("By Zone:")
    for zone, count in sorted(summary.by_zone.items()):
        zone_color = ZONE_COLORS_CONSOLE.get(zone, Colors.RESET)
        print(colorize(f"  {zone}: {count}", zone_color))
    
    print()
    print("By Grade:")
    for grade, count in sorted(summary.by_grade.items()):
        print(f"  {grade}: {count}")


def print_early_entries(results: List[Any]):
    """Print early entry signals prominently."""
    early = [r for r in results if r.zone == 'EARLY_BUY']
    
    if not early:
        return
    
    print()
    print(colorize("⚡" * 20, Colors.CYAN + Colors.BOLD))
    print(colorize("EARLY ENTRY SIGNALS - Best Opportunities!", Colors.CYAN + Colors.BOLD))
    print(colorize("⚡" * 20, Colors.CYAN + Colors.BOLD))
    print()
    
    for r in early:
        print(colorize(f"  {r.ticker}", Colors.CYAN + Colors.BOLD))
        print(f"    PRSI: {r.prsi_emoji} turned bullish")
        print(f"    OBV: {r.obv_emoji} | Gap: {r.psar_gap:+.1f}%")
        print(f"    Action: {r.action}")
        print()


def print_warnings_summary(results: List[Any]):
    """Print warning signals."""
    warnings = [r for r in results if r.zone == 'WARNING']
    
    if not warnings:
        return
    
    print()
    print(colorize("⚠️ WARNING SIGNALS - Consider Exit", Colors.YELLOW + Colors.BOLD))
    print(format_separator('-', 50))
    
    for r in warnings:
        print(colorize(f"  {r.ticker}: {r.action}", Colors.YELLOW))


def print_full_report(
    summary: Any,
    results: List[Any],
    title: str = "Market Scan Results"
):
    """
    Print complete report to console.
    
    Args:
        summary: ScanSummary object
        results: List of all ScanResults
        title: Report title
    """
    # Title
    print()
    print(colorize("="*80, Colors.BOLD))
    print(colorize(f"📊 {title}", Colors.BOLD))
    print(colorize(f"   {datetime.now().strftime('%Y-%m-%d %H:%M')}", Colors.GRAY))
    print(colorize("="*80, Colors.BOLD))
    
    # Summary
    print_summary(summary)
    
    # Early entries first (most important)
    print_early_entries(results)
    
    # Group by zone
    by_zone = {}
    for r in results:
        if r.zone not in by_zone:
            by_zone[r.zone] = []
        by_zone[r.zone].append(r)
    
    # Print each zone
    zone_order = ['STRONG_BUY', 'BUY', 'HOLD', 'NEUTRAL', 'WARNING', 'WEAK', 'SELL', 'OVERSOLD_WATCH']
    
    for zone in zone_order:
        if zone in by_zone and zone != 'EARLY_BUY':  # Already printed early entries
            print_zone_section(zone, by_zone[zone])
    
    # Warnings summary
    print_warnings_summary(results)
    
    # Legend
    print()
    print(colorize("Legend:", Colors.GRAY))
    print(colorize("  ⭐ = IBD Stock | PRSI: ↗️ Up ↘️ Down | OBV: 🟢 Accum 🔴 Distrib", Colors.GRAY))
    print(colorize("  Mom: 5-7 ideal, 9-10 hold only | Grade: A=Best, X=Blocked", Colors.GRAY))


# =============================================================================
# STANDALONE TESTING
# =============================================================================
if __name__ == "__main__":
    print("Console Report Module Test")
    print("=" * 50)
    
    # Test colors
    print()
    print("Zone Colors:")
    for zone, color in ZONE_COLORS_CONSOLE.items():
        print(colorize(f"  {zone}", color))
    
    print()
    print(format_header())
    print(format_separator())

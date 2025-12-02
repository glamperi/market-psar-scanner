#!/usr/bin/env python3
"""
Market PSAR Scanner V2
======================
Main entry point for the scanner.

Usage:
    python main.py                    # Full market scan
    python main.py -mystocks          # Portfolio scan
    python main.py -friends           # Friends watchlist
    python main.py -shorts            # Short candidates
    python main.py --smart-buy        # Smart buy signals
    python main.py --smart-short      # Smart short signals
    python main.py --classic          # Use V1 logic for comparison

Filters:
    --eps 20                          # Min EPS growth %
    --rev 15                          # Min revenue growth %
    --mc 1000                         # Min market cap (millions)
    --adr                             # Include ADRs

Output:
    --email                           # Send email report
    --html report.html                # Save HTML report
    --json results.json               # Save JSON results
"""

import argparse
import sys
import json
from datetime import datetime
from typing import Optional

# Module imports
try:
    from scanners import (
        create_scanner,
        SmartBuyScanner,
        SmartShortScanner,
        PortfolioScanner,
        FriendsScanner
    )
    from reports import (
        print_full_report,
        generate_full_report_html
    )
    from data.cboe import get_cboe_ratios_and_analyze
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure all modules are installed and in the correct location.")
    sys.exit(1)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Market PSAR Scanner V2 - PRSI-Primary Signal Logic",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                     # Full market scan
  python main.py -mystocks           # Your portfolio
  python main.py -mystocks --email   # Portfolio + email report
  python main.py --smart-buy         # Find buy opportunities
  python main.py --smart-short       # Find short opportunities
  python main.py --classic           # Use old V1 logic
  python main.py --compare           # Compare V1 vs V2

Key V2 Changes:
  - PRSI (PSAR on RSI) is the primary signal
  - Momentum 9-10 = HOLD (no new entries)
  - Gap > 5% = blocked (too risky)
  - OBV confirms/warns signals
  - Smart Short never shorts RSI < 35
        """
    )
    
    # Scan mode
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('-mystocks', action='store_true',
                           help='Scan your portfolio (mystocks.txt)')
    mode_group.add_argument('-friends', action='store_true',
                           help="Scan friend's watchlist (friends.txt)")
    mode_group.add_argument('-shorts', action='store_true',
                           help='Scan short candidates (shorts.txt)')
    mode_group.add_argument('--smart-buy', action='store_true',
                           help='Find smart buy opportunities')
    mode_group.add_argument('--smart-short', action='store_true',
                           help='Find smart short opportunities')
    
    # Logic version
    parser.add_argument('--classic', action='store_true',
                       help='Use V1 classic logic (Price PSAR primary)')
    parser.add_argument('--compare', action='store_true',
                       help='Compare V1 and V2 signals')
    
    # Filters
    parser.add_argument('--eps', type=float, default=None,
                       help='Minimum EPS growth %%')
    parser.add_argument('--rev', type=float, default=None,
                       help='Minimum revenue growth %%')
    parser.add_argument('--mc', type=float, default=None,
                       help='Minimum market cap in millions')
    parser.add_argument('--adr', action='store_true',
                       help='Include ADR stocks')
    
    # Output
    parser.add_argument('--email', nargs='?', const=True, default=False,
                       help='Send email report (optional: specify recipient)')
    parser.add_argument('--html', type=str, default=None,
                       help='Save HTML report to file')
    parser.add_argument('--json', type=str, default=None,
                       help='Save JSON results to file')
    parser.add_argument('--quiet', action='store_true',
                       help='Minimal console output')
    
    # Advanced
    parser.add_argument('--workers', type=int, default=10,
                       help='Parallel workers for data fetching')
    parser.add_argument('--no-ibd', action='store_true',
                       help='Skip IBD list scanning')
    parser.add_argument('--tickers', type=str, default=None,
                       help='Comma-separated list of specific tickers')
    
    return parser.parse_args()


def create_progress_callback(quiet: bool = False):
    """Create a progress callback function."""
    if quiet:
        return None
    
    def progress(current: int, total: int, ticker: str, status: str):
        pct = current / total * 100
        bar_width = 30
        filled = int(bar_width * current / total)
        bar = '█' * filled + '░' * (bar_width - filled)
        print(f"\r[{bar}] {pct:5.1f}% ({current}/{total}) {ticker:<8}", end='', flush=True)
    
    return progress


def run_scan(args) -> tuple:
    """
    Run the appropriate scan based on arguments.
    
    Returns:
        Tuple of (summary, results)
    """
    use_v2 = not args.classic
    progress = create_progress_callback(args.quiet)
    
    # Common kwargs
    kwargs = {
        'use_v2': use_v2,
        'include_adr': args.adr,
        'eps_filter': args.eps,
        'rev_filter': args.rev,
        'max_workers': args.workers,
        'progress_callback': progress
    }
    
    if args.mc:
        kwargs['min_market_cap'] = args.mc
    
    # Custom tickers
    custom_tickers = None
    if args.tickers:
        custom_tickers = [t.strip().upper() for t in args.tickers.split(',')]
    
    # Select scanner type
    if args.mystocks:
        scanner = PortfolioScanner(**kwargs)
        mode = "Portfolio"
    elif args.friends:
        scanner = FriendsScanner(**kwargs)
        mode = "Friends"
    elif args.shorts or args.smart_short:
        scanner = SmartShortScanner(**kwargs)
        mode = "Shorts"
    else:
        scanner = SmartBuyScanner(
            scan_ibd=not args.no_ibd,
            custom_tickers=custom_tickers,
            **kwargs
        )
        mode = "Market"
    
    # Print header
    if not args.quiet:
        version = "V1 Classic" if args.classic else "V2 PRSI-Primary"
        print(f"\n{'='*60}")
        print(f"📊 Market Scanner {version}")
        print(f"   Mode: {mode}")
        print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*60}\n")
    
    # Run scan
    if args.smart_short or args.shorts:
        # Short scanner returns candidates differently
        candidates = scanner.get_short_candidates()
        
        # Build results list from candidates
        results = [c.result for c in candidates]
        
        # Create a summary manually
        from scanners import ScanSummary
        summary = ScanSummary(
            total_scanned=len(candidates),
            total_passed=len([c for c in candidates if c.is_valid_short]),
            by_zone={},
            by_grade={},
            strong_buys=[],
            early_buys=[],
            warnings=[],
            scan_time=0,
            timestamp=datetime.now()
        )
        
        # Print short-specific report
        if not args.quiet:
            print("\n")  # Clear progress line
            print(scanner.format_report(candidates))
        
        return summary, results, candidates
    else:
        # Regular buy scan
        summary = scanner.scan()
        
        # Collect all results
        results = []
        for ticker, source in scanner.get_tickers():
            result = scanner.scan_ticker(ticker, source)
            if result and scanner.filter_result(result):
                results.append(result)
        
        if not args.quiet:
            print("\n")  # Clear progress line
            print_full_report(summary, results, f"{mode} Scan Results")
        
        return summary, results, None


def save_html_report(
    summary,
    results,
    filename: str,
    cboe_ratio: Optional[float] = None,
    cboe_sentiment: Optional[str] = None
):
    """Save HTML report to file."""
    # Group by zone
    by_zone = {}
    for r in results:
        if r.zone not in by_zone:
            by_zone[r.zone] = []
        by_zone[r.zone].append(r)
    
    html = generate_full_report_html(
        summary=summary,
        results_by_zone=by_zone,
        title="Market Scan Report",
        cboe_ratio=cboe_ratio,
        cboe_sentiment=cboe_sentiment
    )
    
    with open(filename, 'w') as f:
        f.write(html)
    
    print(f"HTML report saved to: {filename}")


def save_json_results(results, filename: str):
    """Save results as JSON."""
    data = []
    for r in results:
        data.append({
            'ticker': r.ticker,
            'price': r.price,
            'zone': r.zone,
            'grade': r.grade,
            'grade_score': r.grade_score,
            'psar_gap': r.psar_gap,
            'prsi_bullish': r.prsi_bullish,
            'obv_bullish': r.obv_bullish,
            'momentum': r.momentum,
            'trend_score': r.trend_score,
            'timing_score': r.timing_score,
            'entry_allowed': r.entry_allowed,
            'warnings': r.warnings,
            'ibd_stock': r.ibd_stock,
            'source': r.source
        })
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"JSON results saved to: {filename}")


def main():
    """Main entry point."""
    args = parse_args()
    
    try:
        # Get CBOE ratio if available
        cboe_ratio = None
        cboe_sentiment = None
        try:
            cboe_data = get_cboe_ratios_and_analyze()
            cboe_ratio = cboe_data.get('total_pcr')
            cboe_sentiment = cboe_data.get('sentiment')
        except:
            pass
        
        # Run scan
        result = run_scan(args)
        
        if len(result) == 3:
            summary, results, short_candidates = result
        else:
            summary, results = result
            short_candidates = None
        
        # Save outputs
        if args.html:
            save_html_report(summary, results, args.html, cboe_ratio, cboe_sentiment)
        
        if args.json:
            save_json_results(results, args.json)
        
        # Email report (placeholder - implement with existing email_report.py)
        if args.email:
            print("Email report: Use existing email_report.py for now")
            # TODO: Integrate with updated email_report.py
        
        # Exit code based on results
        if summary.total_passed == 0:
            sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n\nScan interrupted.")
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}")
        if '--debug' in sys.argv:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

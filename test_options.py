#!/usr/bin/env python3
"""Test script for options data fetching."""

import sys
sys.path.insert(0, '.')

from utils.options_data import (
    fetch_options_chain,
    _fetch_options_yfinance,
    _fetch_options_yahoo_scrape,
    _fetch_options_yahoo_selenium,
    get_options_source_status
)

def test_ticker(ticker: str):
    print(f"\n{'='*50}")
    print(f"Testing {ticker}")
    print(f"{'='*50}")
    print(f"Options source status: {get_options_source_status()}")
    
    print(f"\n1. Testing yfinance...")
    result = _fetch_options_yfinance(ticker)
    if result:
        print(f"   ✓ yfinance SUCCESS")
        print(f"   Expiration: {result['expiration']}")
        print(f"   Puts found: {len(result['puts'])}")
    else:
        print(f"   ✗ yfinance FAILED (likely rate limited)")
    
    print(f"\n2. Testing Yahoo scrape (requests)...")
    result = _fetch_options_yahoo_scrape(ticker)
    if result:
        print(f"   ✓ Yahoo scrape SUCCESS (source: {result['source']})")
        print(f"   Expiration: {result['expiration']}")
        print(f"   Puts found: {len(result['puts'])}")
        if result['puts']:
            print(f"   Sample put: strike=${result['puts'][0]['strike']}, bid=${result['puts'][0]['bid']}")
    else:
        print(f"   ✗ Yahoo scrape FAILED (may need Selenium)")
    
    print(f"\n3. Testing Yahoo Selenium (handles consent)...")
    result = _fetch_options_yahoo_selenium(ticker)
    if result:
        print(f"   ✓ Yahoo Selenium SUCCESS")
        print(f"   Expiration: {result['expiration']}")
        print(f"   Puts found: {len(result['puts'])}")
    else:
        print(f"   ✗ Yahoo Selenium FAILED")
    
    print(f"\n4. Testing full fallback chain...")
    result = fetch_options_chain(ticker, debug=True)
    if result:
        print(f"   ✓ Final result: {result['source']}")
        print(f"   Expiration: {result['expiration']}")
        print(f"   Puts: {len(result['puts'])}")
    else:
        print(f"   ✗ All sources failed")

if __name__ == "__main__":
    tickers = sys.argv[1:] if len(sys.argv) > 1 else ['MRK', 'AAPL']
    
    for ticker in tickers:
        test_ticker(ticker.upper())
    
    print("\n" + "="*50)
    print("DONE")

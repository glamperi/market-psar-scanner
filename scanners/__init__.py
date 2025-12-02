"""
Market Scanner V2 - Scanners Module
===================================

Scanner classes for different scanning modes.

Available Scanners:
- SmartBuyScanner: Long entry opportunities (V2 logic)
- SmartShortScanner: Short entry opportunities (FIXED logic)
- PortfolioScanner: Scan existing positions (-mystocks)
- FriendsScanner: Scan friend's watchlist (-friends)

V2 Key Improvements:
- PRSI-primary signals catch turns earlier
- Momentum 9-10 blocks new entries (exhausted)
- Gap > 5% blocks new entries (too risky)
- OBV confirms or warns against signals
- Smart Short never shorts RSI < 35 (no more shorting capitulation)
"""

# Base Scanner
from .base_scanner import (
    BaseScanner,
    ScanResult,
    ScanSummary,
    load_ticker_file,
    format_scan_result_row
)

# Smart Buy Scanner
from .smart_buy import (
    SmartBuyScanner,
    PortfolioScanner,
    FriendsScanner
)

# Smart Short Scanner
from .smart_short import (
    SmartShortScanner,
    ShortCandidate
)


def create_scanner(
    mode: str,
    use_v2: bool = True,
    **kwargs
) -> BaseScanner:
    """
    Factory function to create appropriate scanner.
    
    Args:
        mode: Scan mode ('market', 'mystocks', 'friends', 'shorts')
        use_v2: Use V2 logic (default True)
        **kwargs: Additional scanner arguments
    
    Returns:
        Appropriate scanner instance
    """
    kwargs['use_v2'] = use_v2
    
    if mode == 'market':
        return SmartBuyScanner(**kwargs)
    elif mode == 'mystocks':
        return PortfolioScanner(**kwargs)
    elif mode == 'friends':
        return FriendsScanner(**kwargs)
    elif mode == 'shorts':
        return SmartShortScanner(**kwargs)
    else:
        raise ValueError(f"Unknown scan mode: {mode}")


__all__ = [
    # Base
    'BaseScanner', 'ScanResult', 'ScanSummary',
    'load_ticker_file', 'format_scan_result_row',
    
    # Smart Buy
    'SmartBuyScanner', 'PortfolioScanner', 'FriendsScanner',
    
    # Smart Short
    'SmartShortScanner', 'ShortCandidate',
    
    # Factory
    'create_scanner'
]

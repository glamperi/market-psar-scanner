"""
Warnings Module
===============
Generates warning alerts for various market conditions.

Warning Types:
- 🔥 OVERBOUGHT: ATR > +3% AND (OBV Red OR Momentum 9-10)
- ❄️ OVERSOLD BOUNCE: PSAR < -5% AND OBV Green AND/OR Williams oversold
- ⚡ EARLY ENTRY: Price PSAR negative BUT PRSI bullish
- ⚠️ DIVERGENCE: PRSI disagrees with Price PSAR
- 📉 DISTRIBUTION: OBV falling while price rising
- 📈 ACCUMULATION: OBV rising while price falling
- 🚫 GAP WARNING: Gap approaching 5% limit
- ⏸️ EXHAUSTION: Momentum 9-10, no new entries
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

try:
    from utils.config import (
        GAP_MAX, GAP_ACCEPTABLE,
        ATR_OVERBOUGHT, ATR_OVERSOLD, ATR_EXTREME_OVERBOUGHT, ATR_EXTREME_OVERSOLD,
        MOMENTUM_EXHAUSTED_MIN,
        RSI_OVERSOLD, RSI_OVERBOUGHT,
        WILLIAMS_R_OVERSOLD, WILLIAMS_R_OVERBOUGHT
    )
except ImportError:
    GAP_MAX = 5.0
    GAP_ACCEPTABLE = 5.0
    ATR_OVERBOUGHT = 3.0
    ATR_OVERSOLD = -3.0
    ATR_EXTREME_OVERBOUGHT = 5.0
    ATR_EXTREME_OVERSOLD = -5.0
    MOMENTUM_EXHAUSTED_MIN = 9
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    WILLIAMS_R_OVERSOLD = -80
    WILLIAMS_R_OVERBOUGHT = -20


class WarningType(Enum):
    """Types of warnings."""
    OVERBOUGHT = "OVERBOUGHT"
    EXTREME_OVERBOUGHT = "EXTREME_OVERBOUGHT"
    OVERSOLD_BOUNCE = "OVERSOLD_BOUNCE"
    EXTREME_OVERSOLD = "EXTREME_OVERSOLD"
    EARLY_ENTRY = "EARLY_ENTRY"
    PRSI_DIVERGENCE = "PRSI_DIVERGENCE"
    OBV_DISTRIBUTION = "OBV_DISTRIBUTION"
    OBV_ACCUMULATION = "OBV_ACCUMULATION"
    GAP_WARNING = "GAP_WARNING"
    GAP_BLOCKED = "GAP_BLOCKED"
    MOMENTUM_EXHAUSTED = "MOMENTUM_EXHAUSTED"
    RSI_OVERBOUGHT = "RSI_OVERBOUGHT"
    RSI_OVERSOLD = "RSI_OVERSOLD"


WARNING_CONFIG = {
    WarningType.OVERBOUGHT: {
        'emoji': '🔥',
        'severity': 'medium',
        'color': '#e67e22',
        'message': 'Overbought - extended above average'
    },
    WarningType.EXTREME_OVERBOUGHT: {
        'emoji': '🔥🔥',
        'severity': 'high',
        'color': '#e74c3c',
        'message': 'Extremely overbought - high pullback risk'
    },
    WarningType.OVERSOLD_BOUNCE: {
        'emoji': '❄️',
        'severity': 'opportunity',
        'color': '#3498db',
        'message': 'Oversold with accumulation - watch for bounce'
    },
    WarningType.EXTREME_OVERSOLD: {
        'emoji': '❄️❄️',
        'severity': 'opportunity',
        'color': '#9b59b6',
        'message': 'Extremely oversold - capitulation zone'
    },
    WarningType.EARLY_ENTRY: {
        'emoji': '⚡',
        'severity': 'opportunity',
        'color': '#27ae60',
        'message': 'Early entry signal - PRSI turned before price'
    },
    WarningType.PRSI_DIVERGENCE: {
        'emoji': '⚠️',
        'severity': 'medium',
        'color': '#f39c12',
        'message': 'PRSI diverging from price - momentum shift'
    },
    WarningType.OBV_DISTRIBUTION: {
        'emoji': '📉',
        'severity': 'high',
        'color': '#e74c3c',
        'message': 'Distribution detected - smart money selling'
    },
    WarningType.OBV_ACCUMULATION: {
        'emoji': '📈',
        'severity': 'opportunity',
        'color': '#27ae60',
        'message': 'Accumulation detected - smart money buying'
    },
    WarningType.GAP_WARNING: {
        'emoji': '⚠️',
        'severity': 'medium',
        'color': '#f39c12',
        'message': 'Gap approaching 5% limit'
    },
    WarningType.GAP_BLOCKED: {
        'emoji': '🚫',
        'severity': 'block',
        'color': '#c0392b',
        'message': 'Gap > 5% - no new entries allowed'
    },
    WarningType.MOMENTUM_EXHAUSTED: {
        'emoji': '⏸️',
        'severity': 'block',
        'color': '#95a5a6',
        'message': 'Momentum exhausted (9-10) - hold only, no new entries'
    },
    WarningType.RSI_OVERBOUGHT: {
        'emoji': '📊',
        'severity': 'low',
        'color': '#e67e22',
        'message': 'RSI overbought (>70)'
    },
    WarningType.RSI_OVERSOLD: {
        'emoji': '📊',
        'severity': 'opportunity',
        'color': '#3498db',
        'message': 'RSI oversold (<30) - potential bounce'
    }
}


@dataclass
class Warning:
    """A single warning."""
    type: WarningType
    message: str
    detail: Optional[str] = None
    value: Optional[float] = None
    
    @property
    def emoji(self) -> str:
        return WARNING_CONFIG[self.type]['emoji']
    
    @property
    def severity(self) -> str:
        return WARNING_CONFIG[self.type]['severity']
    
    @property
    def color(self) -> str:
        return WARNING_CONFIG[self.type]['color']
    
    @property
    def is_opportunity(self) -> bool:
        return self.severity == 'opportunity'
    
    @property
    def is_block(self) -> bool:
        return self.severity == 'block'


def check_all_warnings(
    psar_gap: float,
    prsi_bullish: bool,
    price_psar_bullish: bool,
    obv_bullish: Optional[bool],
    momentum: int,
    atr_percent: float,
    rsi: float = 50,
    williams_r: float = -50
) -> List[Warning]:
    """
    Check for all warning conditions.
    
    Args:
        psar_gap: PSAR gap percentage
        prsi_bullish: Is PRSI bullish?
        price_psar_bullish: Is price above PSAR?
        obv_bullish: Is OBV bullish?
        momentum: Momentum score 1-10
        atr_percent: ATR percentage
        rsi: Current RSI
        williams_r: Current Williams %R
    
    Returns:
        List of Warning objects
    """
    warnings = []
    abs_gap = abs(psar_gap)
    
    # =================================================================
    # BLOCK WARNINGS (highest priority)
    # =================================================================
    
    # Gap blocked
    if abs_gap > GAP_MAX:
        warnings.append(Warning(
            type=WarningType.GAP_BLOCKED,
            message="Gap exceeds 5% - no new entries",
            detail=f"Gap: {psar_gap:+.1f}%",
            value=psar_gap
        ))
    elif abs_gap > GAP_ACCEPTABLE - 1:
        warnings.append(Warning(
            type=WarningType.GAP_WARNING,
            message="Gap approaching limit",
            detail=f"Gap: {psar_gap:+.1f}% (limit: 5%)",
            value=psar_gap
        ))
    
    # Momentum exhausted
    if momentum >= MOMENTUM_EXHAUSTED_MIN:
        warnings.append(Warning(
            type=WarningType.MOMENTUM_EXHAUSTED,
            message="Momentum exhausted - hold only",
            detail=f"Momentum: {momentum}/10",
            value=momentum
        ))
    
    # =================================================================
    # OVERBOUGHT/OVERSOLD WARNINGS
    # =================================================================
    
    if atr_percent >= ATR_EXTREME_OVERBOUGHT:
        warnings.append(Warning(
            type=WarningType.EXTREME_OVERBOUGHT,
            message="Extremely overbought",
            detail=f"ATR: +{atr_percent:.1f}%",
            value=atr_percent
        ))
    elif atr_percent >= ATR_OVERBOUGHT:
        warnings.append(Warning(
            type=WarningType.OVERBOUGHT,
            message="Overbought",
            detail=f"ATR: +{atr_percent:.1f}%",
            value=atr_percent
        ))
    
    if atr_percent <= ATR_EXTREME_OVERSOLD:
        warnings.append(Warning(
            type=WarningType.EXTREME_OVERSOLD,
            message="Extremely oversold - capitulation",
            detail=f"ATR: {atr_percent:.1f}%",
            value=atr_percent
        ))
    elif atr_percent <= ATR_OVERSOLD:
        # Check if there's accumulation (opportunity)
        if obv_bullish is True:
            warnings.append(Warning(
                type=WarningType.OVERSOLD_BOUNCE,
                message="Oversold with accumulation",
                detail=f"ATR: {atr_percent:.1f}%, OBV bullish",
                value=atr_percent
            ))
    
    # RSI warnings
    if rsi >= RSI_OVERBOUGHT:
        warnings.append(Warning(
            type=WarningType.RSI_OVERBOUGHT,
            message="RSI overbought",
            detail=f"RSI: {rsi:.0f}",
            value=rsi
        ))
    elif rsi <= RSI_OVERSOLD:
        warnings.append(Warning(
            type=WarningType.RSI_OVERSOLD,
            message="RSI oversold",
            detail=f"RSI: {rsi:.0f}",
            value=rsi
        ))
    
    # =================================================================
    # DIVERGENCE WARNINGS
    # =================================================================
    
    # PRSI divergence (momentum vs price)
    if prsi_bullish and not price_psar_bullish:
        warnings.append(Warning(
            type=WarningType.EARLY_ENTRY,
            message="Early entry - PRSI bullish, price catching up",
            detail="Momentum turned before price"
        ))
    elif not prsi_bullish and price_psar_bullish:
        warnings.append(Warning(
            type=WarningType.PRSI_DIVERGENCE,
            message="PRSI bearish despite bullish price",
            detail="Momentum fading - watch for reversal"
        ))
    
    # OBV divergence (volume vs price)
    if obv_bullish is True and not price_psar_bullish:
        warnings.append(Warning(
            type=WarningType.OBV_ACCUMULATION,
            message="Accumulation on dip",
            detail="OBV rising while price falling"
        ))
    elif obv_bullish is False and price_psar_bullish:
        warnings.append(Warning(
            type=WarningType.OBV_DISTRIBUTION,
            message="Distribution at top",
            detail="OBV falling while price rising"
        ))
    
    return warnings


def check_from_indicators(indicators: Dict) -> List[Warning]:
    """
    Check warnings from get_all_indicators() output.
    
    Args:
        indicators: Dict from indicators.get_all_indicators()
    
    Returns:
        List of Warning objects
    """
    # Get RSI from PRSI data
    prsi_data = indicators.get('prsi', {}).get('prsi_data', {})
    rsi = prsi_data.get('rsi', 50)
    
    # Get Williams %R from timing score
    timing_components = indicators.get('timing_score', {}).get('components', {})
    williams = timing_components.get('williams', {}).get('value', -50)
    
    return check_all_warnings(
        psar_gap=indicators.get('psar_gap', 0),
        prsi_bullish=indicators.get('prsi_bullish', False),
        price_psar_bullish=(indicators.get('psar', {}).get('trend') == 'bullish'),
        obv_bullish=indicators.get('obv_bullish'),
        momentum=indicators.get('momentum_score', 5),
        atr_percent=indicators.get('atr_percent', 0),
        rsi=rsi,
        williams_r=williams
    )


def get_blocking_warnings(warnings: List[Warning]) -> List[Warning]:
    """Get only warnings that block entry."""
    return [w for w in warnings if w.is_block]


def get_opportunity_warnings(warnings: List[Warning]) -> List[Warning]:
    """Get only opportunity warnings."""
    return [w for w in warnings if w.is_opportunity]


def format_warnings(warnings: List[Warning], include_detail: bool = True) -> str:
    """Format warnings for display."""
    if not warnings:
        return ""
    
    parts = []
    for w in warnings:
        if include_detail and w.detail:
            parts.append(f"{w.emoji} {w.message}: {w.detail}")
        else:
            parts.append(f"{w.emoji} {w.message}")
    
    return " | ".join(parts)


def format_warnings_short(warnings: List[Warning]) -> str:
    """Format warnings as emoji-only string."""
    return "".join(w.emoji for w in warnings)


def has_entry_block(warnings: List[Warning]) -> bool:
    """Check if any warning blocks entry."""
    return any(w.is_block for w in warnings)


def summarize_warnings(warnings: List[Warning]) -> Dict[str, int]:
    """Summarize warnings by severity."""
    summary = {'block': 0, 'high': 0, 'medium': 0, 'low': 0, 'opportunity': 0}
    for w in warnings:
        summary[w.severity] = summary.get(w.severity, 0) + 1
    return summary


# =============================================================================
# STANDALONE TESTING
# =============================================================================
if __name__ == "__main__":
    print("Warnings Module Test")
    print("=" * 70)
    
    test_cases = [
        {
            'name': 'META-like (Overbought + Distribution)',
            'psar_gap': 7.6,
            'prsi_bullish': True,
            'price_psar_bullish': True,
            'obv_bullish': False,
            'momentum': 8,
            'atr_percent': 4.0,
            'rsi': 72
        },
        {
            'name': 'NVDA-like (Oversold + Accumulation)',
            'psar_gap': -6.3,
            'prsi_bullish': False,
            'price_psar_bullish': False,
            'obv_bullish': True,
            'momentum': 4,
            'atr_percent': -3.5,
            'rsi': 38
        },
        {
            'name': 'MSTR-like (Deep oversold)',
            'psar_gap': -9.3,
            'prsi_bullish': False,
            'price_psar_bullish': False,
            'obv_bullish': True,
            'momentum': 2,
            'atr_percent': -5.5,
            'rsi': 28
        },
        {
            'name': 'Early Entry Signal',
            'psar_gap': -2.0,
            'prsi_bullish': True,
            'price_psar_bullish': False,
            'obv_bullish': True,
            'momentum': 5,
            'atr_percent': -1.0,
            'rsi': 48
        },
        {
            'name': 'Exhausted Momentum',
            'psar_gap': 4.0,
            'prsi_bullish': True,
            'price_psar_bullish': True,
            'obv_bullish': True,
            'momentum': 10,
            'atr_percent': 3.5,
            'rsi': 68
        }
    ]
    
    for case in test_cases:
        name = case.pop('name')
        warnings = check_all_warnings(**case)
        
        print(f"\n{name}")
        print("-" * 50)
        
        if warnings:
            print(f"  Warnings ({len(warnings)}):")
            for w in warnings:
                severity_emoji = {'block': '🚫', 'high': '🔴', 'medium': '🟡', 'low': '🟢', 'opportunity': '✨'}.get(w.severity, '❓')
                print(f"    {w.emoji} [{severity_emoji} {w.severity}] {w.message}")
                if w.detail:
                    print(f"       └─ {w.detail}")
            
            summary = summarize_warnings(warnings)
            print(f"  Summary: {summary}")
            print(f"  Entry Blocked: {'Yes' if has_entry_block(warnings) else 'No'}")
            print(f"  Short format: {format_warnings_short(warnings)}")
        else:
            print("  No warnings")

"""
Zone Classifier
===============
Classifies stocks into zones based on V2 PRSI-primary logic.

V2 Zone Hierarchy (New):
1. PRSI direction is PRIMARY
2. OBV confirms or warns
3. Price PSAR is risk filter
4. Momentum modifies zone
5. ATR adds warnings

New Zones in V2:
- EARLY_BUY: PRSI bullish but price still below PSAR (catching the turn)
- HOLD: Good trend but gap > 5% (wait for pullback)
- WARNING: PRSI bearish but price still above PSAR (momentum fading)
- OVERSOLD_WATCH: PRSI bearish + OBV green (accumulation on dip)
"""

from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum

try:
    from utils.config import (
        GAP_MAX, GAP_EXCELLENT,
        MOMENTUM_EXHAUSTED_MIN, MOMENTUM_IDEAL_MIN,
        RSI_OVERSOLD, RSI_OVERBOUGHT
    )
except ImportError:
    GAP_MAX = 5.0
    GAP_EXCELLENT = 3.0
    MOMENTUM_EXHAUSTED_MIN = 9
    MOMENTUM_IDEAL_MIN = 5
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70


class Zone(Enum):
    """Trading zones in priority order."""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    EARLY_BUY = "EARLY_BUY"
    HOLD = "HOLD"
    NEUTRAL = "NEUTRAL"
    WARNING = "WARNING"
    WEAK = "WEAK"
    SELL = "SELL"
    OVERSOLD_WATCH = "OVERSOLD_WATCH"


ZONE_CONFIG = {
    Zone.STRONG_BUY: {
        'color': '#27ae60',
        'emoji': '🟢🟢',
        'priority': 1,
        'action': 'Enter now - all signals aligned',
        'description': 'PRSI bullish + OBV green + Gap < 5%'
    },
    Zone.BUY: {
        'color': '#2ecc71',
        'emoji': '🟢',
        'priority': 2,
        'action': 'Enter with normal position',
        'description': 'PRSI bullish + mostly confirmed'
    },
    Zone.EARLY_BUY: {
        'color': '#3498db',
        'emoji': '⚡',
        'priority': 3,
        'action': 'Early entry - catching the turn',
        'description': 'PRSI flipped bullish, price catching up'
    },
    Zone.HOLD: {
        'color': '#f39c12',
        'emoji': '⏸️',
        'priority': 4,
        'action': 'Hold existing, no new entries',
        'description': 'Good trend but overextended (gap > 5%)'
    },
    Zone.NEUTRAL: {
        'color': '#95a5a6',
        'emoji': '🟡',
        'priority': 5,
        'action': 'Wait for clarity',
        'description': 'Mixed signals'
    },
    Zone.WARNING: {
        'color': '#e67e22',
        'emoji': '⚠️',
        'priority': 6,
        'action': 'Consider exit - momentum fading',
        'description': 'PRSI bearish but price still up'
    },
    Zone.WEAK: {
        'color': '#e74c3c',
        'emoji': '🟠',
        'priority': 7,
        'action': 'Avoid - weak setup',
        'description': 'Poor trend strength'
    },
    Zone.SELL: {
        'color': '#c0392b',
        'emoji': '🔴',
        'priority': 8,
        'action': 'Exit or avoid',
        'description': 'PRSI bearish + OBV red'
    },
    Zone.OVERSOLD_WATCH: {
        'color': '#9b59b6',
        'emoji': '❄️',
        'priority': 9,
        'action': 'Watch for bounce - accumulation detected',
        'description': 'PRSI bearish but OBV green (divergence)'
    }
}


@dataclass
class ZoneResult:
    """Result of zone classification."""
    zone: Zone
    confidence: int  # 0-100
    reasons: List[str]
    warnings: List[str]
    entry_allowed: bool
    action: str
    
    @property
    def color(self) -> str:
        return ZONE_CONFIG[self.zone]['color']
    
    @property
    def emoji(self) -> str:
        return ZONE_CONFIG[self.zone]['emoji']
    
    @property
    def priority(self) -> int:
        return ZONE_CONFIG[self.zone]['priority']


def classify_zone_v1(psar_gap: float, momentum: int = 5) -> Zone:
    """
    V1 CLASSIC zone classification (Price PSAR primary).
    Kept for --classic mode comparison.
    
    Args:
        psar_gap: PSAR gap percentage
        momentum: Momentum score 1-10
    
    Returns:
        Zone enum
    """
    if psar_gap >= 5.0 and momentum >= 7:
        return Zone.STRONG_BUY
    elif psar_gap >= 0:
        return Zone.BUY
    elif psar_gap >= -2:
        return Zone.NEUTRAL
    elif psar_gap >= -5:
        return Zone.WEAK
    else:
        return Zone.SELL


def classify_zone_v2(
    prsi_bullish: bool,
    price_psar_bullish: bool,
    psar_gap: float,
    obv_bullish: Optional[bool],
    momentum: int,
    rsi: float = 50,
    atr_percent: float = 0,
    trend_score: int = 50,
    timing_score: int = 50,
    is_broken: bool = False
) -> ZoneResult:
    """
    V2 zone classification (PRSI primary).
    
    Args:
        prsi_bullish: Is PRSI trending up?
        price_psar_bullish: Is price above PSAR?
        psar_gap: PSAR gap percentage
        obv_bullish: Is OBV showing accumulation? (None if unknown)
        momentum: Momentum score 1-10
        rsi: Current RSI value
        atr_percent: ATR% (overbought/oversold)
        trend_score: Trend score 0-100
        timing_score: Timing score 0-100
        is_broken: True if stock recently broke DOWN through PSAR (was bullish, now bearish)
    
    Returns:
        ZoneResult with zone, confidence, reasons, warnings
    """
    reasons = []
    warnings = []
    confidence = 50
    entry_allowed = True
    
    abs_gap = abs(psar_gap)
    
    # =================================================================
    # RULE 1: Gap > 5% blocks new entries (becomes HOLD if bullish)
    # =================================================================
    if abs_gap > GAP_MAX:
        entry_allowed = False
        warnings.append(f"Gap {psar_gap:+.1f}% exceeds 5% max - no new entries")
    
    # =================================================================
    # RULE 2: Momentum 9-10 = no new entries (exhausted)
    # =================================================================
    if momentum >= MOMENTUM_EXHAUSTED_MIN:
        entry_allowed = False
        warnings.append(f"Momentum {momentum} exhausted - hold only")
    
    # =================================================================
    # PRIMARY CLASSIFICATION based on PRSI + Price PSAR combination
    # =================================================================
    
    # Case 1: PRSI Bullish + Price Bullish = Confirmed uptrend
    if prsi_bullish and price_psar_bullish:
        reasons.append("PRSI bullish ↗️")
        reasons.append("Price above PSAR")
        
        # Check if overextended
        if abs_gap > GAP_MAX:
            zone = Zone.HOLD
            reasons.append(f"But gap {psar_gap:+.1f}% too large")
            confidence = 60
        # Check OBV confirmation
        elif obv_bullish is True:
            if momentum >= 7 and abs_gap < GAP_EXCELLENT:
                zone = Zone.STRONG_BUY
                reasons.append("OBV confirms accumulation 🟢")
                confidence = 85
            else:
                zone = Zone.BUY
                reasons.append("OBV confirms 🟢")
                confidence = 75
        elif obv_bullish is False:
            zone = Zone.WARNING
            reasons.append("But OBV shows distribution 🔴")
            warnings.append("Price/OBV divergence - momentum may fade")
            confidence = 45
        else:
            zone = Zone.BUY
            confidence = 65
    
    # Case 2: PRSI Bullish + Price Bearish = EARLY BUY or BROKEN
    elif prsi_bullish and not price_psar_bullish:
        # Check if this is a BROKEN signal (was bullish, crashed down)
        if is_broken:
            # Stock just broke DOWN through PSAR - NOT an early buy opportunity
            zone = Zone.WARNING
            reasons.append("⚠️ BROKEN - price crashed through PSAR")
            reasons.append("PRSI bullish but lagging (may follow price down)")
            confidence = 30
            entry_allowed = False
            warnings.append("Recent breakdown - avoid, PRSI may flip bearish")
        else:
            # True Early Buy - consolidating below PSAR, PRSI flipped bullish
            zone = Zone.EARLY_BUY
            reasons.append("PRSI flipped bullish ↗️")
            reasons.append("Price still below PSAR (catching up)")
            confidence = 70
            
            if obv_bullish is True:
                reasons.append("OBV confirms accumulation 🟢")
                confidence = 80
            
            if momentum <= 4:
                reasons.append("Momentum building")
                confidence += 5
    
    # Case 3: PRSI Bearish + Price Bullish = WARNING (momentum fading)
    elif not prsi_bullish and price_psar_bullish:
        zone = Zone.WARNING
        reasons.append("PRSI turned bearish ↘️")
        reasons.append("Price still above PSAR (may follow)")
        confidence = 55
        warnings.append("Momentum fading - consider reducing position")
        
        if obv_bullish is False:
            zone = Zone.WEAK
            reasons.append("OBV confirms distribution 🔴")
            confidence = 40
    
    # Case 4: PRSI Bearish + Price Bearish = Confirmed downtrend
    else:  # not prsi_bullish and not price_psar_bullish
        reasons.append("PRSI bearish ↘️")
        reasons.append("Price below PSAR")
        
        # Check for oversold bounce potential
        if obv_bullish is True:
            zone = Zone.OVERSOLD_WATCH
            reasons.append("But OBV shows accumulation 🟢")
            reasons.append("Potential bounce setup")
            confidence = 50
            warnings.append("Watch for PRSI flip for entry")
        elif rsi <= RSI_OVERSOLD:
            zone = Zone.OVERSOLD_WATCH
            reasons.append(f"RSI oversold ({rsi:.0f})")
            confidence = 45
            warnings.append("Oversold - bounce possible")
        else:
            zone = Zone.SELL
            if obv_bullish is False:
                reasons.append("OBV confirms distribution 🔴")
            confidence = 70
    
    # =================================================================
    # MODIFIERS based on other factors
    # =================================================================
    
    # Trend score modifier
    if trend_score < 40:
        confidence -= 10
        warnings.append(f"Weak trend score ({trend_score})")
    elif trend_score >= 70:
        confidence += 5
    
    # Timing score modifier
    if timing_score < 30:
        warnings.append(f"Poor timing ({timing_score}) - oversold")
    elif timing_score > 80:
        warnings.append(f"Poor timing ({timing_score}) - overbought")
    elif 40 <= timing_score <= 70:
        confidence += 5
    
    # ATR modifier
    if atr_percent > 5:
        warnings.append(f"Extremely overbought (ATR +{atr_percent:.0f}%)")
        if zone in [Zone.STRONG_BUY, Zone.BUY]:
            zone = Zone.HOLD
    elif atr_percent < -5:
        warnings.append(f"Extremely oversold (ATR {atr_percent:.0f}%)")
    
    # Clamp confidence
    confidence = max(10, min(95, confidence))
    
    # Get action from config
    action = ZONE_CONFIG[zone]['action']
    if not entry_allowed and zone in [Zone.STRONG_BUY, Zone.BUY, Zone.EARLY_BUY]:
        action = "HOLD - no new entries (gap or momentum)"
    
    return ZoneResult(
        zone=zone,
        confidence=confidence,
        reasons=reasons,
        warnings=warnings,
        entry_allowed=entry_allowed,
        action=action
    )


def classify_from_indicators(indicators: Dict) -> ZoneResult:
    """
    Classify zone using output from get_all_indicators().
    
    Args:
        indicators: Dict from indicators.get_all_indicators()
    
    Returns:
        ZoneResult
    """
    return classify_zone_v2(
        prsi_bullish=indicators.get('prsi_bullish', False),
        price_psar_bullish=(indicators.get('psar', {}).get('trend') == 'bullish'),
        psar_gap=indicators.get('psar_gap', 0),
        obv_bullish=indicators.get('obv_bullish'),
        momentum=indicators.get('momentum_score', 5),
        rsi=indicators.get('prsi', {}).get('prsi_data', {}).get('rsi', 50),
        atr_percent=indicators.get('atr_percent', 0),
        trend_score=indicators.get('trend_score_value', 50),
        timing_score=indicators.get('timing_score_value', 50),
        is_broken=indicators.get('is_broken', False)
    )


def get_zone_display(zone_result: ZoneResult) -> str:
    """Format zone for display."""
    return f"{zone_result.emoji} {zone_result.zone.value}"


def get_zone_color(zone: Zone) -> str:
    """Get HTML color for zone."""
    return ZONE_CONFIG[zone]['color']


def compare_zones_v1_v2(
    psar_gap: float,
    prsi_bullish: bool,
    price_psar_bullish: bool,
    obv_bullish: Optional[bool],
    momentum: int
) -> Dict[str, any]:
    """
    Compare V1 and V2 zone classifications.
    Useful for --compare mode.
    
    Returns:
        Dict with both classifications and differences
    """
    v1_zone = classify_zone_v1(psar_gap, momentum)
    v2_result = classify_zone_v2(
        prsi_bullish=prsi_bullish,
        price_psar_bullish=price_psar_bullish,
        psar_gap=psar_gap,
        obv_bullish=obv_bullish,
        momentum=momentum
    )
    
    # Determine if there's a significant difference
    v1_bullish = v1_zone in [Zone.STRONG_BUY, Zone.BUY]
    v2_bullish = v2_result.zone in [Zone.STRONG_BUY, Zone.BUY, Zone.EARLY_BUY]
    
    if v1_bullish and not v2_bullish:
        difference = "V1 says BUY, V2 says WAIT/SELL"
        flag = "⚠️"
    elif not v1_bullish and v2_bullish:
        difference = "V1 says SELL/WAIT, V2 says BUY"
        flag = "⚡"
    elif v1_zone != v2_result.zone:
        difference = f"Different zones: {v1_zone.value} vs {v2_result.zone.value}"
        flag = "🔄"
    else:
        difference = "Same classification"
        flag = "✓"
    
    return {
        'v1_zone': v1_zone,
        'v2_zone': v2_result.zone,
        'v2_result': v2_result,
        'difference': difference,
        'flag': flag,
        'v1_bullish': v1_bullish,
        'v2_bullish': v2_bullish
    }


# =============================================================================
# STANDALONE TESTING
# =============================================================================
if __name__ == "__main__":
    print("Zone Classifier Module Test")
    print("=" * 70)
    
    # Test cases based on your portfolio analysis
    test_cases = [
        {
            'name': 'META (was STRONG_BUY, OBV red)',
            'prsi_bullish': True,
            'price_psar_bullish': True,
            'psar_gap': 7.6,
            'obv_bullish': False,  # Distribution!
            'momentum': 8
        },
        {
            'name': 'NVDA (was SELL, OBV green)',
            'prsi_bullish': False,
            'price_psar_bullish': False,
            'psar_gap': -6.3,
            'obv_bullish': True,  # Accumulation!
            'momentum': 4
        },
        {
            'name': 'MSTR (was SELL, OBV green, oversold)',
            'prsi_bullish': False,
            'price_psar_bullish': False,
            'psar_gap': -9.3,
            'obv_bullish': True,
            'momentum': 2
        },
        {
            'name': 'AAPL (ideal STRONG_BUY)',
            'prsi_bullish': True,
            'price_psar_bullish': True,
            'psar_gap': 3.0,
            'obv_bullish': True,
            'momentum': 7
        },
        {
            'name': 'Early entry example',
            'prsi_bullish': True,  # PRSI flipped
            'price_psar_bullish': False,  # Price not yet
            'psar_gap': -2.0,
            'obv_bullish': True,
            'momentum': 5
        }
    ]
    
    for case in test_cases:
        name = case.pop('name')
        print(f"\n{name}")
        print("-" * 50)
        
        # V1 classification
        v1 = classify_zone_v1(case['psar_gap'], case['momentum'])
        print(f"  V1 Zone: {ZONE_CONFIG[v1]['emoji']} {v1.value}")
        
        # V2 classification
        v2 = classify_zone_v2(**case)
        print(f"  V2 Zone: {v2.emoji} {v2.zone.value}")
        print(f"  Confidence: {v2.confidence}%")
        print(f"  Entry Allowed: {'✅' if v2.entry_allowed else '❌'}")
        print(f"  Action: {v2.action}")
        print(f"  Reasons:")
        for r in v2.reasons:
            print(f"    - {r}")
        if v2.warnings:
            print(f"  Warnings:")
            for w in v2.warnings:
                print(f"    ⚠️ {w}")

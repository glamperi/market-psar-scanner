"""
Entry Quality Grading
=====================
Grades entry quality as A/B/C/D/X based on signal alignment.

Grades:
- A: Excellent - all signals aligned, low risk
- B: Good - most signals aligned, moderate risk  
- C: Poor - conflicting signals or elevated risk
- D: Bad - avoid this entry
- X: Blocked - gap > 5% or other hard block

The grade combines:
- Trend Score (is this a good stock?)
- Timing Score (is now a good time?)
- PRSI/OBV confirmation
- Gap risk
- Momentum status
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

try:
    from utils.config import (
        GAP_MAX, GAP_EXCELLENT, GAP_ACCEPTABLE,
        MOMENTUM_EXHAUSTED_MIN, MOMENTUM_IDEAL_MIN, MOMENTUM_IDEAL_MAX,
        TREND_SCORE_STRONG, TREND_SCORE_MIN,
        TIMING_SCORE_IDEAL_MIN, TIMING_SCORE_IDEAL_MAX
    )
except ImportError:
    GAP_MAX = 5.0
    GAP_EXCELLENT = 3.0
    GAP_ACCEPTABLE = 5.0
    MOMENTUM_EXHAUSTED_MIN = 9
    MOMENTUM_IDEAL_MIN = 5
    MOMENTUM_IDEAL_MAX = 7
    TREND_SCORE_STRONG = 70
    TREND_SCORE_MIN = 50
    TIMING_SCORE_IDEAL_MIN = 40
    TIMING_SCORE_IDEAL_MAX = 70


class EntryGrade(Enum):
    """Entry quality grades."""
    A = "A"  # Excellent
    B = "B"  # Good
    C = "C"  # Poor
    D = "D"  # Bad
    X = "X"  # Blocked


GRADE_CONFIG = {
    EntryGrade.A: {
        'color': '#27ae60',
        'label': 'Excellent',
        'action': 'ENTER - full position',
        'description': 'All signals aligned, low risk entry'
    },
    EntryGrade.B: {
        'color': '#f1c40f',
        'label': 'Good',
        'action': 'ENTER - reduced position',
        'description': 'Most signals aligned, moderate risk'
    },
    EntryGrade.C: {
        'color': '#e67e22',
        'label': 'Poor',
        'action': 'WAIT - poor timing or risk',
        'description': 'Conflicting signals or elevated risk'
    },
    EntryGrade.D: {
        'color': '#e74c3c',
        'label': 'Bad',
        'action': 'AVOID - bad setup',
        'description': 'Poor trend and/or timing'
    },
    EntryGrade.X: {
        'color': '#c0392b',
        'label': 'Blocked',
        'action': 'NO ENTRY - hard block',
        'description': 'Gap > 5% or momentum exhausted'
    }
}


@dataclass
class EntryQualityResult:
    """Result of entry quality assessment."""
    grade: EntryGrade
    score: int  # 0-100 composite score
    factors: Dict[str, int]  # Individual factor scores
    positives: List[str]
    negatives: List[str]
    blocked_reason: Optional[str]
    
    @property
    def color(self) -> str:
        return GRADE_CONFIG[self.grade]['color']
    
    @property
    def label(self) -> str:
        return GRADE_CONFIG[self.grade]['label']
    
    @property
    def action(self) -> str:
        return GRADE_CONFIG[self.grade]['action']
    
    @property
    def is_actionable(self) -> bool:
        return self.grade in [EntryGrade.A, EntryGrade.B]


def calculate_entry_quality(
    trend_score: int,
    timing_score: int,
    psar_gap: float,
    prsi_bullish: bool,
    obv_bullish: Optional[bool],
    momentum: int,
    price_psar_bullish: bool,
    atr_percent: float = 0
) -> EntryQualityResult:
    """
    Calculate comprehensive entry quality grade.
    
    Args:
        trend_score: Trend score 0-100
        timing_score: Timing score 0-100
        psar_gap: PSAR gap percentage
        prsi_bullish: Is PRSI bullish?
        obv_bullish: Is OBV bullish? (None if unknown)
        momentum: Momentum score 1-10
        price_psar_bullish: Is price above PSAR?
        atr_percent: ATR percentage
    
    Returns:
        EntryQualityResult with grade, score, and details
    """
    positives = []
    negatives = []
    blocked_reason = None
    
    factors = {
        'trend': 0,
        'timing': 0,
        'gap': 0,
        'confirmation': 0,
        'momentum': 0
    }
    
    abs_gap = abs(psar_gap)
    
    # =================================================================
    # CHECK FOR HARD BLOCKS FIRST
    # =================================================================
    
    if abs_gap > GAP_MAX:
        blocked_reason = f"Gap {psar_gap:+.1f}% exceeds 5% maximum"
        return EntryQualityResult(
            grade=EntryGrade.X,
            score=0,
            factors=factors,
            positives=positives,
            negatives=[blocked_reason],
            blocked_reason=blocked_reason
        )
    
    if momentum >= MOMENTUM_EXHAUSTED_MIN:
        blocked_reason = f"Momentum {momentum} exhausted (9-10 = hold only)"
        return EntryQualityResult(
            grade=EntryGrade.X,
            score=0,
            factors=factors,
            positives=positives,
            negatives=[blocked_reason],
            blocked_reason=blocked_reason
        )
    
    # =================================================================
    # FACTOR 1: TREND SCORE (0-25 points)
    # =================================================================
    if trend_score >= TREND_SCORE_STRONG:
        factors['trend'] = 25
        positives.append(f"Strong trend ({trend_score})")
    elif trend_score >= TREND_SCORE_MIN:
        factors['trend'] = 15
        positives.append(f"Moderate trend ({trend_score})")
    elif trend_score >= 40:
        factors['trend'] = 10
        negatives.append(f"Weak trend ({trend_score})")
    else:
        factors['trend'] = 5
        negatives.append(f"Very weak trend ({trend_score})")
    
    # =================================================================
    # FACTOR 2: TIMING SCORE (0-25 points)
    # =================================================================
    if TIMING_SCORE_IDEAL_MIN <= timing_score <= TIMING_SCORE_IDEAL_MAX:
        factors['timing'] = 25
        positives.append(f"Ideal timing ({timing_score})")
    elif 30 <= timing_score <= 80:
        factors['timing'] = 15
        positives.append(f"Acceptable timing ({timing_score})")
    elif timing_score > 80:
        factors['timing'] = 5
        negatives.append(f"Overbought timing ({timing_score})")
    else:
        factors['timing'] = 10
        negatives.append(f"Oversold timing ({timing_score})")
    
    # =================================================================
    # FACTOR 3: GAP RISK (0-20 points)
    # =================================================================
    if abs_gap < 2:
        factors['gap'] = 20
        positives.append(f"Excellent gap ({psar_gap:+.1f}%)")
    elif abs_gap < GAP_EXCELLENT:
        factors['gap'] = 15
        positives.append(f"Good gap ({psar_gap:+.1f}%)")
    elif abs_gap < 4:
        factors['gap'] = 10
    else:
        factors['gap'] = 5
        negatives.append(f"Elevated gap risk ({psar_gap:+.1f}%)")
    
    # =================================================================
    # FACTOR 4: SIGNAL CONFIRMATION (0-20 points)
    # =================================================================
    confirmations = 0
    
    if prsi_bullish and price_psar_bullish:
        confirmations += 2
        positives.append("PRSI + Price PSAR aligned bullish")
    elif prsi_bullish:
        confirmations += 1
        positives.append("PRSI bullish (early signal)")
    elif price_psar_bullish:
        negatives.append("PRSI bearish despite price strength")
    
    if obv_bullish is True:
        confirmations += 1
        positives.append("OBV confirms accumulation")
    elif obv_bullish is False:
        negatives.append("OBV shows distribution")
    
    factors['confirmation'] = confirmations * 7  # Max 21, cap at 20
    factors['confirmation'] = min(20, factors['confirmation'])
    
    # =================================================================
    # FACTOR 5: MOMENTUM (0-10 points)
    # =================================================================
    if MOMENTUM_IDEAL_MIN <= momentum <= MOMENTUM_IDEAL_MAX:
        factors['momentum'] = 10
        positives.append(f"Ideal momentum ({momentum})")
    elif momentum >= 7:
        factors['momentum'] = 5
        negatives.append(f"High momentum ({momentum}) - late entry")
    elif momentum >= 4:
        factors['momentum'] = 7
    else:
        factors['momentum'] = 3
        negatives.append(f"Low momentum ({momentum})")
    
    # =================================================================
    # CALCULATE TOTAL SCORE AND GRADE
    # =================================================================
    total_score = sum(factors.values())
    
    # ATR penalty for extreme conditions
    if atr_percent > 5:
        total_score -= 15
        negatives.append(f"Extremely overbought (ATR +{atr_percent:.0f}%)")
    elif atr_percent < -5:
        total_score -= 5  # Less penalty for oversold
        negatives.append(f"Extremely oversold (ATR {atr_percent:.0f}%)")
    
    # Determine grade
    if total_score >= 80:
        grade = EntryGrade.A
    elif total_score >= 60:
        grade = EntryGrade.B
    elif total_score >= 40:
        grade = EntryGrade.C
    else:
        grade = EntryGrade.D
    
    return EntryQualityResult(
        grade=grade,
        score=max(0, min(100, total_score)),
        factors=factors,
        positives=positives,
        negatives=negatives,
        blocked_reason=blocked_reason
    )


def calculate_from_indicators(indicators: Dict) -> EntryQualityResult:
    """
    Calculate entry quality from get_all_indicators() output.
    
    Args:
        indicators: Dict from indicators.get_all_indicators()
    
    Returns:
        EntryQualityResult
    """
    return calculate_entry_quality(
        trend_score=indicators.get('trend_score_value', 50),
        timing_score=indicators.get('timing_score_value', 50),
        psar_gap=indicators.get('psar_gap', 0),
        prsi_bullish=indicators.get('prsi_bullish', False),
        obv_bullish=indicators.get('obv_bullish'),
        momentum=indicators.get('momentum_score', 5),
        price_psar_bullish=(indicators.get('psar', {}).get('trend') == 'bullish'),
        atr_percent=indicators.get('atr_percent', 0)
    )


def format_entry_grade(result: EntryQualityResult) -> str:
    """Format entry grade for display."""
    return f"{result.grade.value} ({result.score})"


def get_grade_emoji(grade: EntryGrade) -> str:
    """Get emoji for grade."""
    emojis = {
        EntryGrade.A: '🅰️',
        EntryGrade.B: '🅱️',
        EntryGrade.C: '🇨',
        EntryGrade.D: '🇩',
        EntryGrade.X: '🚫'
    }
    return emojis.get(grade, '❓')


# =============================================================================
# STANDALONE TESTING
# =============================================================================
if __name__ == "__main__":
    print("Entry Quality Grading Module Test")
    print("=" * 70)
    
    test_cases = [
        {
            'name': 'Perfect Setup (Grade A)',
            'trend_score': 80,
            'timing_score': 55,
            'psar_gap': 2.0,
            'prsi_bullish': True,
            'obv_bullish': True,
            'momentum': 6,
            'price_psar_bullish': True
        },
        {
            'name': 'Good Setup (Grade B)',
            'trend_score': 65,
            'timing_score': 60,
            'psar_gap': 3.5,
            'prsi_bullish': True,
            'obv_bullish': True,
            'momentum': 7,
            'price_psar_bullish': True
        },
        {
            'name': 'META-like (High momentum, OBV red)',
            'trend_score': 70,
            'timing_score': 75,
            'psar_gap': 7.6,
            'prsi_bullish': True,
            'obv_bullish': False,
            'momentum': 8,
            'price_psar_bullish': True
        },
        {
            'name': 'NVDA-like (Oversold, OBV green)',
            'trend_score': 55,
            'timing_score': 35,
            'psar_gap': -6.3,
            'prsi_bullish': False,
            'obv_bullish': True,
            'momentum': 4,
            'price_psar_bullish': False
        },
        {
            'name': 'Exhausted (Momentum 10)',
            'trend_score': 85,
            'timing_score': 50,
            'psar_gap': 4.0,
            'prsi_bullish': True,
            'obv_bullish': True,
            'momentum': 10,
            'price_psar_bullish': True
        }
    ]
    
    for case in test_cases:
        name = case.pop('name')
        result = calculate_entry_quality(**case)
        
        print(f"\n{name}")
        print("-" * 50)
        print(f"  Grade: {get_grade_emoji(result.grade)} {result.grade.value} - {result.label}")
        print(f"  Score: {result.score}/100")
        print(f"  Action: {result.action}")
        print(f"  Factors: {result.factors}")
        
        if result.positives:
            print(f"  ✅ Positives:")
            for p in result.positives:
                print(f"     - {p}")
        
        if result.negatives:
            print(f"  ❌ Negatives:")
            for n in result.negatives:
                print(f"     - {n}")
        
        if result.blocked_reason:
            print(f"  🚫 BLOCKED: {result.blocked_reason}")

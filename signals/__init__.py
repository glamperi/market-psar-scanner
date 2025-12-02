"""
Market Scanner V2 - Signals Module
==================================

This module handles signal classification, entry grading, and warnings.

Components:
- zone_classifier: Classifies stocks into zones (STRONG_BUY, BUY, EARLY_BUY, etc.)
- entry_quality: Grades entries as A/B/C/D/X
- warnings: Generates alerts for overbought, oversold, divergences, etc.

V2 Key Changes:
- PRSI is the primary signal (not Price PSAR)
- New zones: EARLY_BUY, HOLD, WARNING, OVERSOLD_WATCH
- Entry blocked if gap > 5% or momentum 9-10
- OBV divergence detection for false signals
"""

# Zone Classifier
from .zone_classifier import (
    Zone,
    ZoneResult,
    ZONE_CONFIG,
    classify_zone_v1,
    classify_zone_v2,
    classify_from_indicators,
    get_zone_display,
    get_zone_color,
    compare_zones_v1_v2
)

# Entry Quality
from .entry_quality import (
    EntryGrade,
    EntryQualityResult,
    GRADE_CONFIG,
    calculate_entry_quality,
    calculate_from_indicators as calculate_entry_from_indicators,
    format_entry_grade,
    get_grade_emoji
)

# Warnings
from .warnings import (
    WarningType,
    Warning,
    WARNING_CONFIG,
    check_all_warnings,
    check_from_indicators as check_warnings_from_indicators,
    get_blocking_warnings,
    get_opportunity_warnings,
    format_warnings,
    format_warnings_short,
    has_entry_block,
    summarize_warnings
)


def get_complete_signal(indicators: dict) -> dict:
    """
    Get complete signal analysis from indicators.
    
    Args:
        indicators: Dict from indicators.get_all_indicators()
    
    Returns:
        Dict with zone, entry grade, and warnings
    """
    zone_result = classify_from_indicators(indicators)
    entry_result = calculate_entry_from_indicators(indicators)
    warnings_list = check_warnings_from_indicators(indicators)
    
    return {
        'zone': zone_result,
        'entry': entry_result,
        'warnings': warnings_list,
        
        # Quick access
        'zone_name': zone_result.zone.value,
        'zone_emoji': zone_result.emoji,
        'grade': entry_result.grade.value,
        'grade_score': entry_result.score,
        'entry_allowed': zone_result.entry_allowed and not has_entry_block(warnings_list),
        'has_opportunity': any(w.is_opportunity for w in warnings_list),
        'has_block': has_entry_block(warnings_list),
        
        # Formatted strings
        'zone_display': get_zone_display(zone_result),
        'grade_display': format_entry_grade(entry_result),
        'warnings_display': format_warnings_short(warnings_list),
        'action': zone_result.action
    }


__all__ = [
    # Zone Classifier
    'Zone', 'ZoneResult', 'ZONE_CONFIG',
    'classify_zone_v1', 'classify_zone_v2', 'classify_from_indicators',
    'get_zone_display', 'get_zone_color', 'compare_zones_v1_v2',
    
    # Entry Quality
    'EntryGrade', 'EntryQualityResult', 'GRADE_CONFIG',
    'calculate_entry_quality', 'calculate_entry_from_indicators',
    'format_entry_grade', 'get_grade_emoji',
    
    # Warnings
    'WarningType', 'Warning', 'WARNING_CONFIG',
    'check_all_warnings', 'check_warnings_from_indicators',
    'get_blocking_warnings', 'get_opportunity_warnings',
    'format_warnings', 'format_warnings_short',
    'has_entry_block', 'summarize_warnings',
    
    # Complete signal
    'get_complete_signal'
]

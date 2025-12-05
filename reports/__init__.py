"""
Market Scanner V2 - Reports Module
==================================

Report generation for scan results.

Available Reports:
- Console: Terminal output with colors
- HTML: Web-based reports (email, file)
- Formatters: Common formatting utilities

Note: The existing email_report.py and portfolio_report.py
in the reports/ folder should be updated to use these
formatters and the new V2 zone/signal data.
"""

# Formatters
from .formatters import (
    get_zone_color,
    get_zone_bg_color,
    format_ticker_html,
    format_price,
    format_psar_gap,
    format_value,
    format_momentum,
    format_grade,
    format_warnings_html,
    generate_table_header,
    generate_table_row,
    generate_scan_result_row,
    generate_zone_section_html,
    generate_summary_html,
    generate_legend_html,
    generate_full_report_html
)

# Console Report
from .console_report import (
    Colors,
    colorize,
    format_result_line,
    format_header,
    format_separator,
    print_zone_section,
    print_summary,
    print_early_entries,
    print_warnings_summary,
    print_full_report
)


__all__ = [
    # Formatters
    'get_zone_color', 'get_zone_bg_color',
    'format_ticker_html', 'format_price', 'format_psar_gap',
    'format_value', 'format_momentum', 'format_grade',
    'format_warnings_html',
    'generate_table_header', 'generate_table_row',
    'generate_scan_result_row', 'generate_zone_section_html',
    'generate_summary_html', 'generate_legend_html',
    'generate_full_report_html',
    
    # Console
    'Colors', 'colorize',
    'format_result_line', 'format_header', 'format_separator',
    'print_zone_section', 'print_summary',
    'print_early_entries', 'print_warnings_summary',
    'print_full_report'
]

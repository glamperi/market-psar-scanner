"""
Report Formatters
=================
Common formatting functions for all report types.

Provides:
- HTML table generation
- Zone/grade coloring
- Ticker formatting with IBD stars
- Number formatting
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

try:
    from utils.config import ZONE_COLORS, ZONE_EMOJIS, ENTRY_GRADES
    from signals import Zone, EntryGrade, ZONE_CONFIG, GRADE_CONFIG
except ImportError:
    ZONE_COLORS = {
        'STRONG_BUY': '#27ae60',
        'BUY': '#2ecc71',
        'EARLY_BUY': '#3498db',
        'HOLD': '#f39c12',
        'NEUTRAL': '#95a5a6',
        'WARNING': '#e67e22',
        'WEAK': '#e74c3c',
        'SELL': '#c0392b',
        'OVERSOLD_WATCH': '#9b59b6',
    }
    ZONE_EMOJIS = {}
    ENTRY_GRADES = {}


def get_zone_color(zone: str) -> str:
    """Get HTML color for a zone."""
    return ZONE_COLORS.get(zone, '#95a5a6')


def get_zone_bg_color(zone: str, opacity: float = 0.15) -> str:
    """Get background color for zone (with transparency)."""
    color = get_zone_color(zone)
    # Convert hex to rgba
    if color.startswith('#'):
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        return f"rgba({r},{g},{b},{opacity})"
    return color


def format_ticker_html(
    ticker: str,
    ibd_stock: bool = False,
    ibd_url: Optional[str] = None
) -> str:
    """
    Format ticker for HTML display with optional IBD star.
    
    Args:
        ticker: Stock ticker
        ibd_stock: Is this an IBD stock?
        ibd_url: URL to IBD research page
    
    Returns:
        HTML string
    """
    if ibd_stock and ibd_url:
        return f'<a href="{ibd_url}" target="_blank" style="text-decoration:none;">⭐</a>{ticker}'
    elif ibd_stock:
        return f'⭐{ticker}'
    else:
        return ticker


def format_price(price: float) -> str:
    """Format price for display."""
    if price >= 1000:
        return f"${price:,.0f}"
    elif price >= 100:
        return f"${price:.1f}"
    else:
        return f"${price:.2f}"


def format_psar_gap(gap: float) -> str:
    """Format PSAR gap with sign and color hint."""
    sign = '+' if gap >= 0 else ''
    return f"{sign}{gap:.1f}%"


def format_value(value: float) -> str:
    """Format dollar value for display."""
    if value >= 1_000_000:
        return f"${value/1_000_000:.1f}M"
    elif value >= 1_000:
        return f"${value/1_000:.1f}K"
    else:
        return f"${value:.0f}"


def format_momentum(momentum: int, emoji: str = "") -> str:
    """Format momentum score."""
    return f"{momentum}{emoji}"


def format_grade(grade: str, score: int) -> str:
    """Format entry grade."""
    return f"{grade}({score})"


def format_warnings_html(warnings: List[str], emojis: str = "") -> str:
    """Format warnings for HTML display."""
    if not warnings and not emojis:
        return ""
    
    if emojis:
        return f'<span title="{"; ".join(warnings)}">{emojis}</span>'
    
    return "; ".join(warnings)


# =============================================================================
# HTML TABLE GENERATION
# =============================================================================

def generate_table_header(columns: List[str], style: str = "") -> str:
    """Generate HTML table header row."""
    header_style = style or "background:#2c3e50; color:white; padding:8px; text-align:left;"
    
    cells = "".join(f'<th style="{header_style}">{col}</th>' for col in columns)
    return f"<tr>{cells}</tr>"


def generate_table_row(
    cells: List[str],
    zone: Optional[str] = None,
    style: str = ""
) -> str:
    """
    Generate HTML table row.
    
    Args:
        cells: List of cell contents
        zone: Optional zone for row background color
        style: Additional CSS style
    """
    row_style = style
    if zone:
        bg_color = get_zone_bg_color(zone)
        row_style = f"background:{bg_color}; {style}"
    
    cell_style = "padding:6px; border-bottom:1px solid #ddd;"
    cells_html = "".join(f'<td style="{cell_style}">{cell}</td>' for cell in cells)
    
    return f'<tr style="{row_style}">{cells_html}</tr>'


def generate_scan_result_row(result: Any, include_position: bool = False) -> str:
    """
    Generate HTML table row for a ScanResult.
    
    Args:
        result: ScanResult object
        include_position: Include position value column
    """
    ticker_html = format_ticker_html(
        result.ticker,
        result.ibd_stock,
        result.ibd_url
    )
    
    cells = [
        f"{result.zone_emoji}",
        ticker_html,
        format_price(result.price),
        format_psar_gap(result.psar_gap),
        result.prsi_emoji,
        result.obv_emoji,
        format_momentum(result.momentum, result.momentum_emoji),
        f"{result.trend_score}",
        format_grade(result.grade, result.grade_score),
        result.warnings_emoji
    ]
    
    if include_position and result.position_value:
        cells.insert(3, format_value(result.position_value))
    
    return generate_table_row(cells, zone=result.zone)


# =============================================================================
# REPORT SECTIONS
# =============================================================================

def generate_zone_section_html(
    zone: str,
    results: List[Any],
    include_position: bool = False
) -> str:
    """
    Generate HTML section for a zone.
    
    Args:
        zone: Zone name
        results: List of ScanResults in this zone
        include_position: Include position column
    
    Returns:
        HTML string
    """
    if not results:
        return ""
    
    zone_color = get_zone_color(zone)
    zone_emoji = ZONE_EMOJIS.get(zone, '')
    
    # Header columns
    columns = ['', 'Ticker', 'Price', 'PSAR%', 'PRSI', 'OBV', 'Mom', 'Trend', 'Grade', 'Warn']
    if include_position:
        columns.insert(3, 'Value')
    
    # Generate rows
    rows = [generate_scan_result_row(r, include_position) for r in results]
    
    html = f"""
    <div style="margin-bottom:20px;">
        <h3 style="color:{zone_color}; border-bottom:2px solid {zone_color}; padding-bottom:5px;">
            {zone_emoji} {zone} ({len(results)})
        </h3>
        <table style="width:100%; border-collapse:collapse; font-size:14px;">
            {generate_table_header(columns)}
            {"".join(rows)}
        </table>
    </div>
    """
    
    return html


def generate_summary_html(summary: Any) -> str:
    """
    Generate HTML summary section.
    
    Args:
        summary: ScanSummary object
    """
    by_zone_html = " | ".join(
        f'<span style="color:{get_zone_color(z)}">{z}: {count}</span>'
        for z, count in sorted(summary.by_zone.items())
    )
    
    html = f"""
    <div style="background:#f8f9fa; padding:15px; border-radius:5px; margin-bottom:20px;">
        <h3 style="margin-top:0;">Scan Summary</h3>
        <p><strong>Scanned:</strong> {summary.total_scanned} | <strong>Passed:</strong> {summary.total_passed}</p>
        <p><strong>By Zone:</strong> {by_zone_html}</p>
        <p><strong>Time:</strong> {summary.scan_time:.1f}s | {summary.timestamp.strftime('%Y-%m-%d %H:%M')}</p>
    </div>
    """
    
    return html


def generate_legend_html() -> str:
    """Generate legend explaining indicators."""
    return """
    <div style="background:#f0f0f0; padding:10px; border-radius:5px; margin-top:20px; font-size:12px;">
        <strong>Legend:</strong><br>
        ⭐ = IBD Stock (click for buy points) | 
        PRSI: ↗️ Bullish ↘️ Bearish | 
        OBV: 🟢 Accumulation 🔴 Distribution |
        Mom = Momentum (5-7 ideal, 9-10 hold only) |
        Grade: A=Excellent B=Good C=Poor X=Blocked
        <br>
        <strong>Zones:</strong>
        🟢🟢 STRONG_BUY | 🟢 BUY | ⚡ EARLY_BUY | ⏸️ HOLD | 🟡 NEUTRAL | ⚠️ WARNING | 🟠 WEAK | 🔴 SELL | ❄️ OVERSOLD_WATCH
    </div>
    """


# =============================================================================
# FULL REPORT GENERATION
# =============================================================================

def generate_full_report_html(
    summary: Any,
    results_by_zone: Dict[str, List[Any]],
    title: str = "Market Scan Report",
    include_position: bool = False,
    cboe_ratio: Optional[float] = None,
    cboe_sentiment: Optional[str] = None
) -> str:
    """
    Generate complete HTML report.
    
    Args:
        summary: ScanSummary object
        results_by_zone: Dict mapping zone name to list of results
        title: Report title
        include_position: Include position values
        cboe_ratio: Optional CBOE put/call ratio
        cboe_sentiment: Optional sentiment interpretation
    
    Returns:
        Complete HTML document
    """
    # Header with CBOE if available
    cboe_html = ""
    if cboe_ratio is not None:
        cboe_html = f"""
        <div style="background:#e8f4f8; padding:10px; border-radius:5px; margin-bottom:15px;">
            <strong>CBOE Put/Call Ratio:</strong> {cboe_ratio:.2f} - {cboe_sentiment or 'N/A'}
        </div>
        """
    
    # Zone sections in order
    zone_order = ['STRONG_BUY', 'EARLY_BUY', 'BUY', 'HOLD', 'NEUTRAL', 'WARNING', 'WEAK', 'SELL', 'OVERSOLD_WATCH']
    
    zones_html = ""
    for zone in zone_order:
        if zone in results_by_zone and results_by_zone[zone]:
            zones_html += generate_zone_section_html(
                zone, 
                results_by_zone[zone],
                include_position
            )
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{title}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #2c3e50; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 8px; text-align: left; }}
            a {{ color: #3498db; }}
        </style>
    </head>
    <body>
        <h1>📊 {title}</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        
        {cboe_html}
        {generate_summary_html(summary)}
        {zones_html}
        {generate_legend_html()}
    </body>
    </html>
    """
    
    return html


# =============================================================================
# STANDALONE TESTING
# =============================================================================
if __name__ == "__main__":
    print("Formatters Module Test")
    print("=" * 50)
    
    # Test formatting functions
    print(f"Price: {format_price(1234.56)}")
    print(f"Value: {format_value(1234567)}")
    print(f"PSAR Gap: {format_psar_gap(5.5)}")
    print(f"PSAR Gap (neg): {format_psar_gap(-3.2)}")
    print(f"Grade: {format_grade('A', 85)}")
    print(f"Ticker HTML: {format_ticker_html('AAPL', True, 'https://ibd.com/aapl')}")
    
    print("\nZone Colors:")
    for zone, color in ZONE_COLORS.items():
        print(f"  {zone}: {color}")

"""
Shorts Sheet Generator
Creates CSV files that become Google Sheets with GOOGLEFINANCE formulas
for tracking short positions and put options
"""

import os
from datetime import datetime


def generate_shorts_sheet(results, output_dir=None):
    """
    Generate a CSV file for Google Sheets with GOOGLEFINANCE formulas.
    
    When uploaded to Google Sheets, the formulas will auto-populate current prices.
    
    Columns:
    - Ticker
    - Entry Date
    - Entry Price (at time of scan)
    - Put Strike (long put)
    - Put Expiration
    - Sell Put Strike (if spread)
    - Spread Width
    - Net Cost
    - Current Price (GOOGLEFINANCE formula)
    - P&L % (formula)
    - Status (Open/Closed/Expired)
    - Notes
    """
    
    # Default to current directory if not specified
    if output_dir is None:
        output_dir = os.getcwd()
    
    # Create output dir if it doesn't exist
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
        except:
            output_dir = os.getcwd()  # Fall back to current dir
    
    date_str = datetime.now().strftime('%Y-%m-%d')
    filename = f"shorts_tracking_{date_str}.csv"
    filepath = os.path.join(output_dir, filename)
    
    # Build CSV content
    lines = []
    
    # Header
    header = [
        'Ticker',
        'Entry Date',
        'Entry Price',
        'Score',
        'Zone',
        'Put Strike',
        'Put Exp',
        'Sell Put',
        'Spread Width',
        'Net Cost',
        'Current Price',
        'Price Change %',
        'Put P&L Est',
        'Status',
        'Exp Price',
        'Notes'
    ]
    lines.append(','.join(header))
    
    # Data rows
    row_num = 2  # Start at row 2 (after header)
    for r in results:
        ticker = r.get('ticker', '')
        entry_price = r.get('price', 0)
        score = r.get('short_score', 0)
        zone = r.get('psar_zone', '')
        
        # Get put data if available
        put_data = r.get('put_recommendation', {})
        if put_data:
            put_strike = put_data.get('long_strike', '')
            put_exp = put_data.get('expiration', '')
            sell_put = put_data.get('short_strike', '')
            spread_width = put_data.get('spread_width', '')
            net_cost = put_data.get('spread_cost', put_data.get('long_mid', ''))
        else:
            put_strike = ''
            put_exp = ''
            sell_put = ''
            spread_width = ''
            net_cost = ''
        
        # GOOGLEFINANCE formula for current price
        # Format: =GOOGLEFINANCE("TICKER","price")
        current_price_formula = f'=GOOGLEFINANCE("{ticker}","price")'
        
        # Price change % formula
        # Format: =(K2-C2)/C2*100  where K=current price, C=entry price
        price_change_formula = f'=IF(K{row_num}<>"",((K{row_num}-C{row_num})/C{row_num})*100,"")'
        
        # Put P&L estimate (for long put)
        # If stock drops, put gains: (entry_price - current_price) * delta
        # Simplified: assume delta ~0.95 for deep ITM
        put_pl_formula = f'=IF(AND(K{row_num}<>"",F{row_num}<>""),(C{row_num}-K{row_num})*0.95-J{row_num},"")'
        
        row = [
            ticker,
            date_str,
            f'{entry_price:.2f}' if entry_price else '',
            str(score),
            zone,
            f'{put_strike:.0f}' if put_strike else '',
            put_exp if put_exp else '',
            f'{sell_put:.0f}' if sell_put else '',
            f'{spread_width:.0f}' if spread_width else '',
            f'{net_cost:.2f}' if net_cost else '',
            current_price_formula,
            price_change_formula,
            put_pl_formula,
            'Open',
            '',  # Exp Price - to be filled on expiration
            ''   # Notes
        ]
        
        # Escape any commas in values and wrap in quotes if needed
        escaped_row = []
        for val in row:
            val_str = str(val)
            if ',' in val_str or '"' in val_str:
                val_str = '"' + val_str.replace('"', '""') + '"'
            escaped_row.append(val_str)
        
        lines.append(','.join(escaped_row))
        row_num += 1
    
    # Write file
    csv_content = '\n'.join(lines)
    
    with open(filepath, 'w') as f:
        f.write(csv_content)
    
    return filepath, filename


def generate_shorts_sheet_with_puts(results, shorts_report):
    """
    Enhanced version that includes put recommendations from ShortsReport.
    
    Args:
        results: List of scan results
        shorts_report: ShortsReport instance (to call get_put_recommendation)
    """
    
    # Enrich results with put data
    for r in results:
        if r.get('price', 0) > 0:
            put = shorts_report.get_put_recommendation(
                r['ticker'], 
                r['price'],
                r.get('psar_distance', 0)
            )
            if put:
                r['put_recommendation'] = put
    
    return generate_shorts_sheet(results)


# Template for manual tracking sheet
TEMPLATE_HEADER = """
SHORTS TRACKING SHEET
Generated: {date}

Instructions:
1. Upload this CSV to Google Sheets
2. The GOOGLEFINANCE formulas will auto-populate current prices
3. Update 'Status' column as positions change (Open/Closed/Expired)
4. On expiration, fill in 'Exp Price' column with closing price
5. Add notes as needed

GOOGLEFINANCE updates every 15-20 minutes during market hours.
"""

if __name__ == '__main__':
    # Test with sample data
    sample_results = [
        {
            'ticker': 'IREN',
            'price': 47.81,
            'short_score': 75,
            'psar_zone': 'SELL',
            'put_recommendation': {
                'long_strike': 62,
                'expiration': '2026-01-02',
                'short_strike': 36,
                'spread_width': 26,
                'spread_cost': 14.50
            }
        },
        {
            'ticker': 'BYND',
            'price': 0.98,
            'short_score': 40,
            'psar_zone': 'WEAK',
            'put_recommendation': {
                'long_strike': 2,
                'expiration': '2026-01-02',
                'long_mid': 1.06
            }
        }
    ]
    
    filepath, filename = generate_shorts_sheet(sample_results, '/home/claude')
    print(f"Generated: {filepath}")

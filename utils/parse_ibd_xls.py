#!/usr/bin/env python3
"""
IBD XLS Parser - Extract ratings and convert to enhanced CSV format

Downloads IBD XLS files, extracts all useful columns (Composite, RS, EPS, etc.),
and creates enhanced CSV files for the scanner to use.

Usage:
    python parse_ibd_xls.py

Processes these files:
    - ibd_50.xls → ibd_50.csv
    - ibd_bigcap20.xls → ibd_bigcap20.csv
    - ibd_sector.xls → ibd_sector.csv
    - ibd_spotlight.xls → ibd_spotlight.csv
    - ibd_ipo.xls → ibd_ipo.csv
"""

import pandas as pd
import os
from datetime import datetime

def parse_ibd_xls(xls_file, csv_file):
    """
    Parse IBD XLS file and extract key columns
    
    Expected columns in IBD XLS files:
    - Symbol (required)
    - Company (optional but nice)
    - Composite Rating
    - EPS Rating
    - RS Rating
    - Group RS
    - SMR Rating
    - Acc/Dis
    - % Off High
    - Price
    - 50-Day Line
    - Vol % Chg
    
    Output CSV will have:
    - Symbol (required for scanner)
    - Company
    - Composite
    - EPS
    - RS
    - GroupRS
    - SMR
    - AccDis
    - OffHigh
    - Price
    - Vol
    """
    
    try:
        print(f"\nProcessing {xls_file}...")
        
        # Read XLS file
        # Try both .xls and .xlsx extensions
        if os.path.exists(xls_file):
            # IBD files have metadata rows at top, headers start around row 8
            df = pd.read_excel(xls_file, header=None)
        elif os.path.exists(xls_file.replace('.xls', '.xlsx')):
            df = pd.read_excel(xls_file.replace('.xls', '.xlsx'), header=None)
        else:
            print(f"  ✗ File not found: {xls_file}")
            return False
        
        # Find the header row (look for row where first cell is "Symbol" or "Ticker")
        header_row = None
        for idx, row in df.iterrows():
            first_cell = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''
            first_cell = first_cell.strip()
            if first_cell in ['Symbol', 'Ticker', 'SYMBOL', 'TICKER']:
                header_row = idx
                break
        
        if header_row is None:
            print(f"  ✗ Error: Could not find header row with 'Symbol' or 'Ticker' in first column")
            print(f"  First 10 rows:")
            for idx in range(min(10, len(df))):
                print(f"    Row {idx}: {df.iloc[idx, 0]}")
            return False
        
        # Re-read with correct header row
        if os.path.exists(xls_file):
            df = pd.read_excel(xls_file, header=header_row)
        else:
            df = pd.read_excel(xls_file.replace('.xls', '.xlsx'), header=header_row)
        
        print(f"  Found {len(df)} rows (header on row {header_row})")
        print(f"  Columns: {', '.join(df.columns.tolist())}")
        
        # Map IBD column names to our clean names
        # IBD uses different column names in different lists
        column_mapping = {
            # Symbol/Ticker
            'Symbol': 'Symbol',
            'Ticker': 'Symbol',
            'Stock': 'Symbol',
            
            # Company
            'Company': 'Company',
            'Name': 'Company',
            'Company Name': 'Company',
            
            # Ratings
            'Composite Rating': 'Composite',
            'Comp Rating': 'Composite',
            'Composite': 'Composite',
            
            'EPS Rating': 'EPS',
            'EPS Rtg': 'EPS',
            'EPS': 'EPS',
            
            'RS Rating': 'RS',
            'RS Rtg': 'RS',
            'RS': 'RS',
            'Relative Strength': 'RS',
            
            'Group RS': 'GroupRS',
            'Grp RS': 'GroupRS',
            
            'SMR Rating': 'SMR',
            'SMR': 'SMR',
            
            'Acc/Dis': 'AccDis',
            'Acc/Dis Rating': 'AccDis',
            'AccDis': 'AccDis',
            
            # Metrics
            '% Off High': 'OffHigh',
            'Off High': 'OffHigh',
            '% off High': 'OffHigh',
            
            'Price': 'Price',
            'Last': 'Price',
            'Close': 'Price',
            
            '50-Day Line': 'Day50',
            '50 Day': 'Day50',
            
            'Vol % Chg': 'Vol',
            'Volume % Change': 'Vol',
            'Vol': 'Vol',
        }
        
        # Rename columns
        df_renamed = df.rename(columns=column_mapping)
        
        # Select only columns we want (in order)
        desired_columns = [
            'Symbol',      # Required
            'Company',     # Nice to have
            'Composite',   # Key rating
            'EPS',         # Earnings rating
            'RS',          # Relative strength
            'GroupRS',     # Industry group strength
            'SMR',         # Sales/Margins/ROE
            'AccDis',      # Accumulation/Distribution
            'OffHigh',     # % off 52-week high
            'Price',       # Current price
            'Day50',       # 50-day moving average
            'Vol',         # Volume % change
        ]
        
        # Keep only columns that exist
        available_columns = [col for col in desired_columns if col in df_renamed.columns]
        
        if 'Symbol' not in available_columns:
            print(f"  ✗ Error: No Symbol/Ticker column found!")
            print(f"  Available columns: {', '.join(df_renamed.columns.tolist())}")
            return False
        
        df_clean = df_renamed[available_columns].copy()
        
        # Clean up data
        # Remove rows with NaN Symbol
        df_clean = df_clean[df_clean['Symbol'].notna()]
        
        # Strip whitespace from Symbol
        df_clean['Symbol'] = df_clean['Symbol'].astype(str).str.strip()
        
        # Remove any header rows that snuck in
        df_clean = df_clean[df_clean['Symbol'] != 'Symbol']
        df_clean = df_clean[df_clean['Symbol'] != 'Ticker']
        
        # Remove empty symbols
        df_clean = df_clean[df_clean['Symbol'] != '']
        
        # Convert numeric columns to proper types
        numeric_cols = ['Composite', 'EPS', 'RS', 'Price', 'Vol']
        for col in numeric_cols:
            if col in df_clean.columns:
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
        
        # Clean percentage columns (remove % sign)
        if 'OffHigh' in df_clean.columns:
            df_clean['OffHigh'] = df_clean['OffHigh'].astype(str).str.replace('%', '').str.strip()
            df_clean['OffHigh'] = pd.to_numeric(df_clean['OffHigh'], errors='coerce')
        
        # Save to CSV
        df_clean.to_csv(csv_file, index=False)
        
        print(f"  ✓ Saved {len(df_clean)} stocks to {csv_file}")
        print(f"  Columns: {', '.join(available_columns)}")
        
        # Show sample
        if len(df_clean) > 0:
            print(f"\n  Sample (first 3 rows):")
            print(f"  {'Symbol':<8} {'Comp':<6} {'RS':<6} {'EPS':<6} {'AccDis':<8}")
            print(f"  {'-'*40}")
            for _, row in df_clean.head(3).iterrows():
                symbol = str(row.get('Symbol', 'N/A'))[:7]
                comp = str(row.get('Composite', 'N/A'))[:5]
                rs = str(row.get('RS', 'N/A'))[:5]
                eps = str(row.get('EPS', 'N/A'))[:5]
                accdis = str(row.get('AccDis', 'N/A'))[:7]
                print(f"  {symbol:<8} {comp:<6} {rs:<6} {eps:<6} {accdis:<8}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error processing {xls_file}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Process all IBD XLS files"""
    
    print("=" * 70)
    print("IBD XLS PARSER - Extract Ratings to CSV")
    print("=" * 70)
    print()
    print("This will parse IBD XLS files and create enhanced CSV files")
    print("with all ratings (Composite, RS, EPS, Acc/Dis, etc.)")
    print()
    
    # Get current directory
    current_dir = os.getcwd()
    print(f"Working directory: {current_dir}")
    print()
    
    # List of IBD files to process
    ibd_files = [
        ('ibd_50.xls', 'ibd_50.csv'),
        ('ibd_bigcap20.xls', 'ibd_bigcap20.csv'),
        ('ibd_sector.xls', 'ibd_sector.csv'),
        ('ibd_spotlight.xls', 'ibd_spotlight.csv'),
        ('ibd_ipo.xls', 'ibd_ipo.csv'),
    ]
    
    processed = 0
    failed = 0
    
    for xls_file, csv_file in ibd_files:
        if parse_ibd_xls(xls_file, csv_file):
            processed += 1
        else:
            failed += 1
    
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"✓ Processed: {processed}")
    print(f"✗ Failed: {failed}")
    print()
    
    if processed > 0:
        print("✅ CSV files created! You can now:")
        print("   1. Review the CSV files")
        print("   2. Optionally add 'BuyPoint' and 'Comment' columns manually")
        print("   3. Upload to GitHub (git add *.csv && git commit && git push)")
        print()
    
    if failed > 0:
        print("⚠️  Some files failed to process.")
        print("   Make sure you've downloaded the XLS files from IBD")
        print("   and placed them in this directory.")
        print()


if __name__ == "__main__":
    main()

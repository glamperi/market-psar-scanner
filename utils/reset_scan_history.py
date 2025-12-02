#!/usr/bin/env python3
"""
Reset Scanner History - Fresh Start

This script resets scan_status.json to force ALL stocks to be treated as "new"
on the next scan. Use this when you want to start with a clean slate.

Run this before your next scheduled scan.
"""

import json
import os
from datetime import datetime

def reset_scan_history():
    """Reset scan_status.json to empty state"""
    
    # Path to scan_status.json
    status_file = 'scan_status.json'
    
    # Create backup of existing file
    if os.path.exists(status_file):
        backup_file = f'scan_status_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(status_file, 'r') as f:
            backup_data = json.load(f)
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2)
        print(f"✓ Backed up existing scan_status.json to {backup_file}")
    
    # Reset to empty state
    fresh_state = {
        "_exit_history": {},
        "_last_scan": datetime.now().isoformat(),
        "_note": "Fresh start - all stocks will be treated as new on next scan"
    }
    
    with open(status_file, 'w') as f:
        json.dump(fresh_state, f, indent=2)
    
    print(f"✓ Reset scan_status.json to fresh state")
    print(f"\nNext scan will:")
    print("  - Treat ALL stocks as new (no 'new entries' notifications)")
    print("  - Establish baseline for future change detection")
    print("  - Populate scan_status.json with current state")
    print("\nAfter that, subsequent scans will properly detect changes.")

if __name__ == "__main__":
    print("=" * 70)
    print("RESET SCANNER HISTORY - FRESH START")
    print("=" * 70)
    print()
    
    response = input("This will reset scan history. Continue? (yes/no): ")
    if response.lower() in ['yes', 'y']:
        reset_scan_history()
        print("\n✅ Reset complete!")
    else:
        print("\n❌ Reset cancelled.")

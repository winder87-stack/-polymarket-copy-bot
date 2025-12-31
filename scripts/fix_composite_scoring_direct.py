#!/usr/bin/env python3
"""
Direct fix for composite_scoring_engine.py line 614-616
"""

import subprocess
import sys


def fix_file():
    filepath = "core/composite_scoring_engine.py"

    # Use sed to fix the specific syntax error on line 614
    # Change: critical_count = len([f for f in red_flags if f[0] in []])
    # To:     critical_flags = ["MARKET_MAKER", "WASH_TRADING", "INSIDER_TRADING"]
    #         critical_count = len([f for f in red_flags if f[0] in critical_flags])

    cmd = [
        "sed",
        "-i",
        "-e",
        "614,616c\\critical_count = len([f for f in red_flags if f[0] in \\[]])\\n",
        '                "MARKET_MAKER", "WASH_TRADING", "INSIDER_TRADING"\\n',
        "            ]])",
        '614,616d\\critical_flags = ["MARKET_MAKER", "WASH_TRADING", "INSIDER_TRADING"]',
        "            critical_count = len([f for f in red_flags if f[0] in critical_flags])",
        filepath,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✅ Fixed {filepath}")
        print("   Lines 614-616 corrected")
        return True
    else:
        print(f"❌ Failed to fix {filepath}")
        print(f"   Error: {result.stderr}")
        return False


if __name__ == "__main__":
    success = fix_file()
    sys.exit(0 if success else 1)

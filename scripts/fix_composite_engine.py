#!/usr/bin/env python3
"""
Direct fix for composite_scoring_engine.py syntax error
"""


def main():
    filepath = "core/composite_scoring_engine.py"

    with open(filepath, "r") as f:
        lines = f.readlines()

    # Fix lines 614-616
    for i in range(len(lines)):
        line = lines[i]

        # Check for the problematic pattern
        if "critical_count = len([f for f in red_flags if f[0] in []])" in line:
            # Replace with corrected version
            fixed_line = line.replace(
                "critical_count = len([f for f in red_flags if f[0] in []])",
                'critical_count = len([f for f in red_flags if f[0] in ["MARKET_MAKER", "WASH_TRADING", "INSIDER_TRADING"]])',
            )
            lines[i] = fixed_line
            print(f"✅ Fixed line {i + 1}: {line.strip()[:50]}...")
            print(f"   To: {fixed_line.strip()[:50]}...")

    with open(filepath, "w") as f:
        f.writelines(lines)

    print(f"✅ Fixed {filepath}")


if __name__ == "__main__":
    main()

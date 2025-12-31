#!/usr/bin/env python3
"""
Final fix for composite_scoring_engine.py syntax error
"""


def fix_file():
    filepath = "core/composite_scoring_engine.py"

    with open(filepath, "r") as f:
        lines = f.readlines()

    # Fix line 614-616: broken list comprehension
    # Line 614: critical_count = len([f for f in red_flags if f[0] in []])
    # Line 615: "MARKET_MAKER", "WASH_TRADING", "INSIDER_TRADING"
    # Line 616: ]])

    # Fix lines 614-616 together
    for i in range(len(lines)):
        line = lines[i]

        # Find and fix the problematic section
        if "critical_count = len([f for f in red_flags if f[0] in []])" in line:
            lines[i] = (
                '            critical_flags = ["MARKET_MAKER", "WASH_TRADING", "INSIDER_TRADING"]'
            )
            i += 1  # Skip the next two lines
            # Remove line 615
            lines[i] = ""
            i += 1  # Remove line 616
            print(f"✅ Fixed lines {i - 1}-{i}: {line.strip()}")

    # Remove the empty line
    lines = [line for line in lines if line.strip()]

    with open(filepath, "w") as f:
        f.writelines(lines)

    print(f"✅ Fixed {filepath}")
    return True


if __name__ == "__main__":
    success = fix_file()
    import sys

    sys.exit(0 if success else 1)

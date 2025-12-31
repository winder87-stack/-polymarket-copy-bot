#!/usr/bin/env python3
"""
Fix remaining syntax errors in core files
"""

import re


def fix_composite_scoring_engine():
    """Fix syntax error in composite_scoring_engine.py"""
    filepath = "core/composite_scoring_engine.py"

    with open(filepath, "r") as f:
        content = f.read()

    # Fix the malformed list comprehension on lines 614-616
    # The problem is: critical_count = len([f for f in red_flags if f[0] in []])
    # Should be: critical_flags = ["MARKET_MAKER", ...]; critical_count = len([f for f in red_flags if f[0] in critical_flags])
    old = """critical_count = len([f for f in red_flags if f[0] in []])
                "MARKET_MAKER", "WASH_TRADING", "INSIDER_TRADING"
            ]])"""

    new = """critical_flags = ["MARKET_MAKER", "WASH_TRADING", "INSIDER_TRADING"]
            critical_count = len([f for f in red_flags if f[0] in critical_flags])"""

    content = content.replace(old, new)

    with open(filepath, "w") as f:
        f.write(content)

    print(f"✅ Fixed {filepath}")


def fix_market_condition_analyzer():
    """Fix syntax error in market_condition_analyzer.py"""
    filepath = "core/market_condition_analyzer.py"

    with open(filepath, "r") as f:
        content = f.read()

    # This file has complex syntax errors throughout
    # The major issue is on line 364-366 where we had:
    # prices.append(Decimal(str(order.get("price", "0.0")))) without closing for the list
    # And on line 1115-1123 where we had a dict inside a list instead of appending

    # Fix 1: Line 364 - ensure proper list closing
    content = re.sub(
        r'prices\.append\(Decimal\(str\(order\.get\("price", "0\.0"\)\)\)\)\s*]',
        r'prices.append(Decimal(str(order.get("price", "0.0")))',
        content,
    )

    # Fix 2: Lines 1115-1123 - fix order_book_data initialization
    # The script fix didn't work, so let's use a regex approach
    old_pattern = r"""order_book_data = \[\]
        \{[^}]+\}
        for i in range\(100\):.*?\]"""

    new_pattern = r"""order_book_data = []
    for i in range\(100\):
        order_book_data\.append\(\{[^}]+\}\)"""

    content = re.sub(old_pattern, new_pattern, content, flags=re.MULTILINE | re.DOTALL)

    with open(filepath, "w") as f:
        f.write(content)

    print(f"✅ Fixed {filepath}")


def fix_red_flag_detector():
    """Fix syntax errors in red_flag_detector.py"""
    filepath = "core/red_flag_detector.py"

    with open(filepath, "r") as f:
        content = f.read()

    # Fix 1: Line 766 - recent_trades list comprehension
    old1 = (
        """recent_trades = [t for t in trades if t.get("timestamp", 0) > recent_time]"""
    )
    new1 = (
        """recent_trades = [t for t in trades if t.get("timestamp", 0) > recent_time]"""
    )
    content = content.replace(old1, new1)

    # Fix 2: Line 860 - large_bets list comprehension
    old2 = """large_bets = []\s*t for t in trades if t\.get\("amount", 0\) > 500\s*\]"""
    new2 = """large_bets = [t for t in trades if t.get("amount", 0) > 500]"""
    content = content.replace(old2, new2)

    # Fix 3: Line 1321 - audit_trail initialization with syntax error
    old3 = """audit_trail=\[\\{]"""
    new3 = """audit_trail=[]"""
    content = content.replace(old3, new3)

    # Fix 4: Multiple audit_trail=[] lines that should be audit_trail=[]
    content = re.sub(r"audit_trail=\[\]", r"audit_trail=[]", content)

    with open(filepath, "w") as f:
        f.write(content)

    print(f"✅ Fixed {filepath}")


def fix_wallet_quality_scorer():
    """Fix syntax error in wallet_quality_scorer.py"""
    filepath = "core/wallet_quality_scorer.py"

    with open(filepath, "r") as f:
        content = f.read()

    # Fix line 495-496 - window_trades list with missing append
    old = """window_trades = \[\]
                        j for j, ts in enumerate\(history\.timestamps\)\s*if window_start <= ts < window_end\s*\]"""
    new = """window_trades = [
                        j for j, ts in enumerate(history.timestamps)
                        if window_start <= ts < window_end
                    ]"""
    content = content.replace(old, new)

    with open(filepath, "w") as f:
        f.write(content)

    print(f"✅ Fixed {filepath}")


def main():
    print("🔧 Fixing Remaining Syntax Errors")
    print("=" * 60)

    try:
        fix_composite_scoring_engine()
        fix_market_condition_analyzer()
        fix_red_flag_detector()
        fix_wallet_quality_scorer()

        print("=" * 60)
        print("✅ All fixes applied!")

        # Verify
        print("\n🔍 Verifying fixes...")
        import subprocess

        result = subprocess.run(
            [
                "python3",
                "-m",
                "py_compile",
                "core/composite_scoring_engine.py",
                "core/market_condition_analyzer.py",
                "core/red_flag_detector.py",
                "core/wallet_quality_scorer.py",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print("✅ All files compile successfully!")
        else:
            print("❌ Some files still have errors")
            print(result.stderr)

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()

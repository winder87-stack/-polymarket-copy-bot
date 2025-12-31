#!/usr/bin/env python3
"""
Quick fix script for complex syntax errors in Python files
"""


def fix_composite_scoring_engine():
    """Fix syntax error in composite_scoring_engine.py"""
    filepath = "core/composite_scoring_engine.py"

    with open(filepath, "r") as f:
        content = f.read()

    # Fix line 614-616: broken list comprehension
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

    # Fix lines 1115-1123: broken dict appending to list
    # The original had a dict inside the loop that should be appended
    old = """    # Sample order book data
    order_book_data = []
        {
            "timestamp": time.time() - (86400 * i),  # i days ago
            "price": str(100.0 + (time.time() % 1000) * 0.1),  # Slight price variation
            "volume": 1000 + (time.time() % 500) * 10,
            "side": "buy" if i % 2 == 0 else "sell",
        }
        for i in range(100):  # 100 order book entries
    ]"""

    new = """    # Sample order book data
    order_book_data = []
    for i in range(100):  # 100 order book entries
        order_book_data.append({
            "timestamp": time.time() - (86400 * i),  # i days ago
            "price": str(100.0 + (time.time() % 1000) * 0.1),  # Slight price variation
            "volume": 1000 + (time.time() % 500) * 10,
            "side": "buy" if i % 2 == 0 else "sell",
        })"""

    content = content.replace(old, new)

    with open(filepath, "w") as f:
        f.write(content)

    print(f"✅ Fixed {filepath}")


def main():
    print("🔧 Fixing Complex Syntax Errors")
    print("=" * 60)

    fix_composite_scoring_engine()
    fix_market_condition_analyzer()

    print("=" * 60)
    print("✅ All fixes applied!")


if __name__ == "__main__":
    main()

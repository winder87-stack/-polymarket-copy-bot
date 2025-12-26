#!/usr/bin/env python3
"""
Safe configuration validation script for pre-commit hooks.
Validates configuration syntax without loading sensitive data.
"""

import ast
import sys
from pathlib import Path


def main():
    """Main validation function"""
    config_file = Path('config/settings.py')

    if not config_file.exists():
        print('❌ config/settings.py not found')
        sys.exit(1)

    try:
        with open(config_file, 'r') as f:
            content = f.read()

        # Parse the file to check syntax
        ast.parse(content)
        print('✅ Configuration file syntax is valid')

        # Basic validation without loading sensitive data
        if 'private_key' in content and 'target_wallets' in content:
            print('✅ Configuration structure looks correct')
        else:
            print('⚠️ Configuration may be missing required fields')
            sys.exit(1)

    except SyntaxError as e:
        print(f'❌ Syntax error in configuration: {e}')
        sys.exit(1)
    except Exception as e:
        print(f'❌ Configuration validation failed: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()

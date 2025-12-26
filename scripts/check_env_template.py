#!/usr/bin/env python3
"""
Environment template validation script for pre-commit hooks.
Checks if .env.template exists and has required variables.
"""

import sys
from pathlib import Path


def main():
    """Main validation function"""
    # Check if .env.template exists
    template_file = Path('.env.template')
    if not template_file.exists():
        print('❌ .env.template file is missing')
        sys.exit(1)

    # Check if .env exists
    env_file = Path('.env')
    if not env_file.exists():
        print('⚠️ .env file is missing (copy from .env.example)')
    else:
        print('✅ Environment files exist')

    # Basic validation of template structure
    with open(template_file, 'r') as f:
        content = f.read()

    required_vars = ['POLYGONSCAN_API_KEY', 'POLYGON_RPC_URL']
    missing_vars = []
    for var in required_vars:
        if var not in content:
            missing_vars.append(var)

    if missing_vars:
        print(f'⚠️ .env.template may be missing: {missing_vars}')
    else:
        print('✅ .env.template has required variables')


if __name__ == '__main__':
    main()

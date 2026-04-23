#!/usr/bin/env python3
"""
Security Check Script

This script checks your repository for potential security issues before
committing to GitHub. It scans for:
- AWS credentials in files
- Private keys
- Sensitive patterns
- Large files
- Unignored sensitive files

Run this before pushing to GitHub!
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

# Patterns that might indicate credentials or secrets
SENSITIVE_PATTERNS = [
    (r'AKIA[0-9A-Z]{16}', 'AWS Access Key ID'),
    (r'aws_access_key_id\s*=\s*["\']?[A-Z0-9]{20}', 'AWS Access Key in config'),
    (r'aws_secret_access_key\s*=\s*["\']?[A-Za-z0-9/+=]{40}', 'AWS Secret Key in config'),
    (r'-----BEGIN (?:RSA |DSA |EC )?PRIVATE KEY-----', 'Private Key'),
    (r'password\s*=\s*["\'][^"\']+["\']', 'Password in config'),
    (r'api[_-]?key\s*=\s*["\'][^"\']+["\']', 'API Key'),
    (r'secret\s*=\s*["\'][^"\']+["\']', 'Secret in config'),
]

# Files that should never be committed
SENSITIVE_FILES = [
    '.env',
    'credentials',
    '.aws/credentials',
    '.aws/config',
    '*.pem',
    '*.key',
    'secrets.yaml',
    'secrets.yml',
]

# Maximum file size (in KB)
MAX_FILE_SIZE_KB = 1000


def check_file_for_secrets(file_path: Path) -> List[Tuple[str, str, int]]:
    """
    Check a file for potential secrets.
    
    Returns:
        List of (pattern_name, matched_text, line_number) tuples
    """
    issues = []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                for pattern, name in SENSITIVE_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        # Mask the actual secret
                        masked = re.sub(r'[A-Za-z0-9/+=]', '*', line.strip())
                        issues.append((name, masked, line_num))
    except Exception as e:
        print(f"  ⚠️  Warning: Could not read {file_path}: {e}")
    
    return issues


def check_file_size(file_path: Path) -> bool:
    """Check if file is too large."""
    size_kb = file_path.stat().st_size / 1024
    return size_kb > MAX_FILE_SIZE_KB


def should_check_file(file_path: Path) -> bool:
    """Determine if file should be checked."""
    # Skip binary files
    binary_extensions = {'.pyc', '.pyo', '.so', '.dll', '.exe', '.bin', '.pkl', '.h5', '.pt'}
    if file_path.suffix in binary_extensions:
        return False
    
    # Skip directories we don't want to check
    skip_dirs = {'venv', 'env', '__pycache__', '.git', 'node_modules', '.hypothesis', '.mypy_cache'}
    if any(skip_dir in file_path.parts for skip_dir in skip_dirs):
        return False
    
    # Skip documentation files (they contain example patterns)
    if file_path.name in {'SECURITY.md', 'SECURITY_QUICK_REFERENCE.md', 'SECURITY_SETUP_SUMMARY.md'}:
        return False
    
    # Skip log files (already gitignored)
    if file_path.suffix == '.log' or 'logs' in file_path.parts:
        return False
    
    return True


def main():
    """Run security checks."""
    print("🔒 Running Security Checks...")
    print("=" * 60)
    
    repo_root = Path(__file__).parent.parent
    os.chdir(repo_root)
    
    issues_found = False
    
    # Check 1: Scan for secrets in files
    print("\n1️⃣  Scanning for secrets in files...")
    files_with_secrets = []
    
    for file_path in repo_root.rglob('*'):
        if file_path.is_file() and should_check_file(file_path):
            secrets = check_file_for_secrets(file_path)
            if secrets:
                files_with_secrets.append((file_path, secrets))
    
    if files_with_secrets:
        issues_found = True
        print("  ❌ FOUND POTENTIAL SECRETS:")
        for file_path, secrets in files_with_secrets:
            rel_path = file_path.relative_to(repo_root)
            print(f"\n  📄 {rel_path}")
            for name, masked, line_num in secrets:
                print(f"     Line {line_num}: {name}")
                print(f"     Content: {masked[:80]}...")
    else:
        print("  ✅ No secrets detected")
    
    # Check 2: Look for sensitive files
    print("\n2️⃣  Checking for sensitive files...")
    sensitive_found = []
    
    for pattern in SENSITIVE_FILES:
        matches = list(repo_root.glob(pattern))
        matches.extend(list(repo_root.glob(f'**/{pattern}')))
        for match in matches:
            if match.is_file():
                # Check if it's actually ignored by git
                result = os.system(f'git check-ignore -q "{match}"')
                if result != 0:  # Not ignored
                    sensitive_found.append(match)
    
    if sensitive_found:
        issues_found = True
        print("  ❌ FOUND SENSITIVE FILES NOT IN .gitignore:")
        for file_path in sensitive_found:
            rel_path = file_path.relative_to(repo_root)
            print(f"     {rel_path}")
    else:
        print("  ✅ No unignored sensitive files")
    
    # Check 3: Check for large files
    print("\n3️⃣  Checking for large files...")
    large_files = []
    
    for file_path in repo_root.rglob('*'):
        if file_path.is_file() and should_check_file(file_path):
            if check_file_size(file_path):
                size_mb = file_path.stat().st_size / (1024 * 1024)
                large_files.append((file_path, size_mb))
    
    if large_files:
        print("  ⚠️  FOUND LARGE FILES:")
        for file_path, size_mb in large_files:
            rel_path = file_path.relative_to(repo_root)
            print(f"     {rel_path} ({size_mb:.2f} MB)")
        print("  💡 Consider adding large files to .gitignore")
    else:
        print("  ✅ No large files detected")
    
    # Check 4: Verify .gitignore exists and has AWS patterns
    print("\n4️⃣  Checking .gitignore...")
    gitignore_path = repo_root / '.gitignore'
    
    if not gitignore_path.exists():
        issues_found = True
        print("  ❌ .gitignore file not found!")
    else:
        with open(gitignore_path, 'r') as f:
            gitignore_content = f.read()
        
        required_patterns = ['.env', '.aws/', '*.pem', '*.key', 'credentials']
        missing_patterns = [p for p in required_patterns if p not in gitignore_content]
        
        if missing_patterns:
            issues_found = True
            print("  ⚠️  .gitignore missing patterns:")
            for pattern in missing_patterns:
                print(f"     {pattern}")
        else:
            print("  ✅ .gitignore looks good")
    
    # Check 5: Check AWS credentials location
    print("\n5️⃣  Checking AWS credentials location...")
    home = Path.home()
    aws_creds = home / '.aws' / 'credentials'
    
    if aws_creds.exists():
        print(f"  ✅ AWS credentials found in correct location: {aws_creds}")
    else:
        print(f"  ℹ️  No AWS credentials file found at {aws_creds}")
        print("     This is OK if you're using environment variables or IAM roles")
    
    # Final summary
    print("\n" + "=" * 60)
    if issues_found:
        print("❌ SECURITY ISSUES FOUND!")
        print("\n⚠️  DO NOT PUSH TO GITHUB until issues are resolved!")
        print("\nRecommended actions:")
        print("1. Remove any secrets from files")
        print("2. Add sensitive files to .gitignore")
        print("3. Move credentials to ~/.aws/credentials")
        print("4. Run this script again to verify")
        print("\nSee SECURITY.md for detailed guidance.")
        sys.exit(1)
    else:
        print("✅ ALL SECURITY CHECKS PASSED!")
        print("\n🎉 Your repository looks safe to push to GitHub!")
        print("\nReminder: Always review your changes before pushing:")
        print("  git diff --staged")
        sys.exit(0)


if __name__ == '__main__':
    main()

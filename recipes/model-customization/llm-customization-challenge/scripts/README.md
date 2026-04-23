# Security Scripts

This directory contains security and utility scripts for the project.

## check_security.py

**Purpose:** Scan your repository for potential security issues before pushing to GitHub.

**What it checks:**
- AWS credentials in files
- Private keys and certificates
- Sensitive patterns (passwords, API keys, secrets)
- Large files that shouldn't be committed
- Unignored sensitive files
- .gitignore configuration

**Usage:**

```bash
# Run security check
python scripts/check_security.py

# Or make it executable and run directly (Linux/Mac)
chmod +x scripts/check_security.py
./scripts/check_security.py
```

**When to run:**
- Before your first `git push`
- Before pushing to a public repository
- After adding new configuration files
- Periodically as part of your workflow

**Example output:**

```
🔒 Running Security Checks...
============================================================

1️⃣  Scanning for secrets in files...
  ✅ No secrets detected

2️⃣  Checking for sensitive files...
  ✅ No unignored sensitive files

3️⃣  Checking for large files...
  ✅ No large files detected

4️⃣  Checking .gitignore...
  ✅ .gitignore looks good

5️⃣  Checking AWS credentials location...
  ✅ AWS credentials found in correct location: C:\Users\username\.aws\credentials

============================================================
✅ ALL SECURITY CHECKS PASSED!

🎉 Your repository looks safe to push to GitHub!
```

## Best Practices

1. **Run before every push to a new repository**
2. **Add to your pre-commit workflow** (see `.pre-commit-config.yaml`)
3. **Review the output carefully** - automated checks can't catch everything
4. **When in doubt, don't commit** - you can always add files later

## See Also

- [SECURITY.md](../SECURITY.md) - Comprehensive security guide
- [.gitignore](../.gitignore) - Files excluded from git
- [.pre-commit-config.yaml](../.pre-commit-config.yaml) - Automated pre-commit hooks

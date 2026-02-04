# Security Best Practices

This document outlines security best practices for the Automated LLM Finetuning Pipeline, with a focus on protecting AWS credentials and sensitive data.

## Table of Contents

1. [AWS Credentials Management](#aws-credentials-management)
2. [Pre-Commit Checklist](#pre-commit-checklist)
3. [Environment Variables](#environment-variables)
4. [Configuration Files](#configuration-files)
5. [Git Security Tools](#git-security-tools)
6. [What to Never Commit](#what-to-never-commit)
7. [Emergency Response](#emergency-response)

---

## AWS Credentials Management

### ✅ CORRECT: Use AWS Credentials File

Your AWS credentials should be stored in `~/.aws/credentials` (Linux/Mac) or `%USERPROFILE%\.aws\credentials` (Windows):

```ini
[default]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY
region = us-east-1
```

**Why this is safe:**
- This file is in your home directory, NOT in the project
- The `.gitignore` excludes `.aws/` directories
- boto3 automatically reads from this location
- You can use AWS profiles for multiple accounts

### ✅ CORRECT: Use Environment Variables

Set environment variables for temporary use:

**Linux/Mac:**
```bash
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_DEFAULT_REGION="us-east-1"
```

**Windows (PowerShell):**
```powershell
$env:AWS_ACCESS_KEY_ID="your_access_key"
$env:AWS_SECRET_ACCESS_KEY="your_secret_key"
$env:AWS_DEFAULT_REGION="us-east-1"
```

**Windows (CMD):**
```cmd
set AWS_ACCESS_KEY_ID=your_access_key
set AWS_SECRET_ACCESS_KEY=your_secret_key
set AWS_DEFAULT_REGION=us-east-1
```

### ✅ CORRECT: Use IAM Roles (Production)

For production deployments on EC2, ECS, or Lambda:
- Attach IAM roles to your compute resources
- No credentials needed in code or config files
- Automatic credential rotation
- Better security and audit trail

### ❌ NEVER: Hardcode Credentials

**NEVER do this:**
```python
# ❌ WRONG - Never hardcode credentials!
aws_access_key = "AKIAIOSFODNN7EXAMPLE"
aws_secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
```

**NEVER do this:**
```yaml
# ❌ WRONG - Never put credentials in config files!
aws:
  access_key_id: AKIAIOSFODNN7EXAMPLE
  secret_access_key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

---

## Pre-Commit Checklist

Before committing code, verify:

### 1. Check for Credentials
```bash
# Search for potential AWS credentials
git grep -i "aws_access_key"
git grep -i "aws_secret"
git grep -i "AKIA"  # AWS access key prefix
git grep -i "secret_access_key"
```

### 2. Check Staged Files
```bash
# Review what you're about to commit
git diff --staged

# Check for sensitive patterns
git diff --staged | grep -i "password\|secret\|key\|token"
```

### 3. Verify .gitignore is Working
```bash
# Check what files are tracked
git status

# Verify sensitive files are ignored
git check-ignore -v config/pipeline_config.yaml
git check-ignore -v .aws/credentials
```

### 4. Review Configuration Files
- Ensure `config/pipeline_config.yaml` only contains placeholders or example values
- Check that use case files don't contain sensitive customer data
- Verify log files are excluded

---

## Environment Variables

### Create a .env.example File

Create `.env.example` (safe to commit) with placeholder values:

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012

# SageMaker Configuration
SAGEMAKER_ROLE_ARN=arn:aws:iam::ACCOUNT_ID:role/SageMakerRole
SAGEMAKER_BUCKET=s3://your-bucket-name

# Bedrock Configuration
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514-v1:0

# Optional: Logging
LOG_LEVEL=INFO
```

### Create Your Actual .env File (NOT committed)

Copy `.env.example` to `.env` and fill in real values:

```bash
cp .env.example .env
# Edit .env with your actual credentials
```

The `.gitignore` ensures `.env` is never committed.

---

## Configuration Files

### Safe Configuration Pattern

**config/pipeline_config.example.yaml** (safe to commit):
```yaml
aws_region: "us-east-1"
sagemaker_role_arn: "arn:aws:iam::ACCOUNT_ID:role/SageMakerRole"
s3_bucket: "your-bucket-name"
bedrock_model_id: "anthropic.claude-sonnet-4-20250514-v1:0"
```

**config/pipeline_config.yaml** (NOT committed):
```yaml
aws_region: "us-east-1"
sagemaker_role_arn: "arn:aws:iam::123456789012:role/MyActualRole"
s3_bucket: "my-actual-bucket-2024"
bedrock_model_id: "anthropic.claude-sonnet-4-20250514-v1:0"
```

### Current Project Setup

This project follows AWS best practices:

1. **No credentials in code**: The `AWSClientManager` uses boto3's credential chain
2. **Config files use placeholders**: Example configs show structure, not real values
3. **Credentials from standard locations**: `~/.aws/credentials` or environment variables
4. **IAM roles for production**: Recommended for EC2/ECS/Lambda deployments

---

## Git Security Tools

### Install git-secrets (Recommended)

Prevents committing secrets:

```bash
# Install git-secrets
# Mac:
brew install git-secrets

# Linux:
git clone https://github.com/awslabs/git-secrets.git
cd git-secrets
sudo make install

# Configure for your repo
cd /path/to/your/repo
git secrets --install
git secrets --register-aws
```

### Install pre-commit Hooks

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: check-added-large-files
      - id: check-yaml
      - id: detect-aws-credentials
      - id: detect-private-key
      
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
```

Install and run:
```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

---

## What to Never Commit

### 🚫 Credentials and Keys
- AWS access keys and secret keys
- SSH private keys (`.pem`, `.key` files)
- API tokens and passwords
- Database connection strings with passwords
- Encryption keys

### 🚫 Personal Data
- Customer data or PII
- Internal company information
- Proprietary training data
- Personal notes with sensitive info

### 🚫 Large Files
- Model checkpoints (`.pt`, `.h5`, `.ckpt`)
- Training datasets (`.jsonl`, `.csv` with data)
- Compressed archives (`.tar.gz`, `.zip`)
- Binary artifacts

### 🚫 Environment-Specific Files
- Local configuration overrides
- IDE workspace files
- OS-specific files (`.DS_Store`, `Thumbs.db`)
- Virtual environment directories

---

## Emergency Response

### If You Accidentally Commit Credentials

**1. Immediately Rotate Credentials**
```bash
# Go to AWS Console → IAM → Users → Security Credentials
# Delete the compromised access key
# Create a new access key
```

**2. Remove from Git History**
```bash
# Install BFG Repo-Cleaner
brew install bfg  # Mac
# or download from: https://rtyley.github.io/bfg-repo-cleaner/

# Remove credentials from history
bfg --replace-text passwords.txt  # File with patterns to remove
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push (WARNING: Rewrites history)
git push --force
```

**3. Notify Your Team**
- Alert team members about the incident
- Have them re-clone the repository
- Update any systems using the old credentials

**4. Audit Access**
- Check AWS CloudTrail for unauthorized access
- Review recent API calls
- Look for unusual resource creation

### Prevention is Better Than Cure

- Use `git-secrets` to prevent commits with secrets
- Enable AWS CloudTrail for audit logging
- Use AWS Secrets Manager for production secrets
- Implement least-privilege IAM policies
- Regularly rotate credentials

---

## Additional Resources

- [AWS Security Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [GitHub Security Best Practices](https://docs.github.com/en/code-security/getting-started/best-practices-for-preventing-data-leaks-in-your-organization)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [git-secrets on GitHub](https://github.com/awslabs/git-secrets)

---

## Quick Reference

### Before Every Commit
```bash
# 1. Check for secrets
git diff --staged | grep -i "password\|secret\|key\|token\|AKIA"

# 2. Verify .gitignore is working
git status --ignored

# 3. Review changes
git diff --staged

# 4. Commit safely
git commit -m "Your commit message"
```

### Safe Credential Storage Locations
✅ `~/.aws/credentials` (home directory)
✅ Environment variables (temporary)
✅ AWS Secrets Manager (production)
✅ IAM roles (EC2/ECS/Lambda)

### Never Store Credentials Here
❌ Project files
❌ Config files in repo
❌ Code files
❌ Git history
❌ Public repositories

---

**Remember: When in doubt, don't commit it. You can always add it later, but removing it from Git history is difficult.**

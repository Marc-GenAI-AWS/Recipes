# Security Quick Reference Card

**Print this and keep it handy!**

## ✅ DO

- Store AWS credentials in `~/.aws/credentials`
- Use environment variables for temporary credentials
- Run `python scripts/check_security.py` before pushing
- Review `git diff --staged` before committing
- Keep `.gitignore` up to date
- Use IAM roles in production
- Rotate credentials regularly

## ❌ DON'T

- Hardcode credentials in code
- Commit `.env` files with real values
- Store credentials in config files
- Commit private keys (`.pem`, `.key`)
- Push large model files
- Commit customer data or PII
- Ignore security warnings

## 🚨 Before Every Push

```bash
# 1. Check for secrets
python scripts/check_security.py

# 2. Review changes
git diff --staged

# 3. Search for patterns
git diff --staged | grep -i "password\|secret\|key\|AKIA"

# 4. Verify gitignore
git status --ignored
```

## 📍 Safe Credential Locations

| Location | Use Case | Safe? |
|----------|----------|-------|
| `~/.aws/credentials` | Development | ✅ Yes |
| Environment variables | Temporary | ✅ Yes |
| IAM roles | Production | ✅ Yes |
| AWS Secrets Manager | Production | ✅ Yes |
| Project files | Never | ❌ No |
| Git repository | Never | ❌ No |

## 🔍 Quick Checks

```bash
# Check for AWS keys
git grep -i "AKIA"

# Check for secrets
git grep -i "aws_secret"

# Check what's staged
git diff --staged --name-only

# Verify file is ignored
git check-ignore -v .env
```

## 🆘 Emergency: Committed Credentials

1. **Immediately rotate credentials** in AWS Console
2. Remove from git history: `bfg --replace-text passwords.txt`
3. Force push: `git push --force`
4. Notify team to re-clone
5. Check CloudTrail for unauthorized access

## 📚 Resources

- Full guide: [SECURITY.md](SECURITY.md)
- Security scanner: `python scripts/check_security.py`
- Example env: [.env.example](.env.example)
- Gitignore: [.gitignore](.gitignore)

## 🎯 Remember

**When in doubt, don't commit it!**

You can always add files later, but removing them from Git history is difficult and may not be complete if others have already cloned the repository.

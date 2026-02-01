## Description
<!-- Provide a brief description of the changes in this PR -->

## Type of Change
<!-- Mark the relevant option with an "x" -->
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Refactoring
- [ ] Configuration change

## Changes Made
<!-- List the specific changes made in this PR -->
- 
- 
- 

## Testing
<!-- Describe how you tested these changes -->
- [ ] Tested locally
- [ ] Tested on staging/deployment platform
- [ ] All existing tests pass

## 🔐 Security Checklist
<!-- CRITICAL: Review before submitting PR -->

### Credentials & Secrets
- [ ] **NO credentials** in code (no API keys, tokens, passwords)
- [ ] All secrets use `os.getenv()` or config files
- [ ] `.env` file is NOT included (ignored by Git)
- [ ] `credentials.json` is NOT included (ignored by Git)
- [ ] `groups.json` is NOT included (or sanitized if needed)
- [ ] `houses.json` is NOT included (or sanitized if needed)
- [ ] No Telegram user IDs or group IDs exposed (unless in `.example` files)

### Configuration Files
- [ ] If updated, only `.example` templates are committed
- [ ] No real data in example files
- [ ] All template files clearly marked with placeholder values

### Code Review
- [ ] No `TODO: Add token here` or similar comments with actual secrets
- [ ] No hardcoded IDs, tokens, or sensitive values
- [ ] Sensitive file paths use environment variables or config

### Git History
- [ ] No sensitive files were ever added to this branch
- [ ] Used `git status --ignored` to verify ignored files
- [ ] Reviewed `git diff` before committing

### Documentation
- [ ] Updated `.env.example` if new variables added
- [ ] Updated `SECURITY.md` if security-related changes
- [ ] Added comments explaining any security-sensitive code

## Screenshots (if applicable)
<!-- Add screenshots to help explain your changes -->

## Additional Notes
<!-- Any additional information reviewers should know -->

---

**By submitting this PR, I confirm that:**
- ✅ I have reviewed the security checklist
- ✅ No credentials or sensitive data are included
- ✅ All secrets are properly handled via environment variables

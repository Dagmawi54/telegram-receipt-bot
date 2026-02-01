# 🔐 Security Guide

## Overview

This document explains how to properly handle credentials and secrets for the Telegram Receipt Bot project. **Never commit sensitive information to version control.**

---

## 🚨 What NOT to Commit

The following files contain sensitive data and are protected by `.gitignore`:

### Critical Files (Already Ignored)
- ❌ `credentials.json` - Google Sheets service account credentials
- ❌ `token.txt` - Telegram bot token
- ❌ `.env` - Environment variables with secrets
- ❌ `groups.json` - Contains real group IDs and user IDs
- ❌ `houses.json` - Contains real resident names and data
- ❌ `*.session` - Telethon session files
- ❌ `processed_messages.json` - User data
- ❌ `receipts/` - User-submitted receipt images

### Template Files (Safe to Commit)
- ✅ `.env.example` - Template showing required variables (NO real values)
- ✅ `groups.json.example` - Structure example (NO real IDs)
- ✅ `houses.json.example` - Structure example (NO real data)

---

## 🛠️ Local Development Setup

### Step 1: Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/telegram-receipt-bot.git
cd telegram-receipt-bot
```

### Step 2: Create Environment File
```bash
# Copy the template
cp .env.example .env

# Edit with your actual credentials
notepad .env  # or your preferred editor
```

### Step 3: Set Up Google Sheets Credentials

1. **Create a Google Cloud Project:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project

2. **Enable Google Sheets API:**
   - In your project, enable "Google Sheets API"

3. **Create Service Account:**
   - Go to "IAM & Admin" → "Service Accounts"
   - Create a new service account
   - Create and download a JSON key

4. **Save Credentials:**
   ```bash
   # Rename the downloaded file to credentials.json
   # Place it in the project root directory
   ```

5. **Share Your Spreadsheet:**
   - Open your Google Sheet
   - Share it with the service account email (from credentials.json)
   - Give it "Editor" permissions

### Step 4: Get Telegram Bot Token

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow the instructions
3. Copy the bot token
4. Paste it into `.env` as `BOT_TOKEN=`

### Step 5: Configure Groups and Houses

```bash
# Copy templates
cp groups.json.example groups.json
cp houses.json.example houses.json

# Edit with your actual data
notepad groups.json
notepad houses.json
```

### Step 6: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 7: Run the Bot
```bash
python better1.py
```

---

## ☁️ Cloud Deployment

### Render (Recommended)

#### Deploy the Bot (Background Worker)

1. **Push to GitHub** (credentials will NOT be in the repo)
2. **Create New Background Worker:**
   - Go to [Render Dashboard](https://dashboard.render.com/)
   - New → Background Worker
   - Connect your GitHub repository
   - Root Directory: `.` (leave empty)
   - Start Command: `python better1.py`

3. **Add Environment Variables:**
   ```
   BOT_TOKEN=your_actual_bot_token
   SPREADSHEET_ID=your_spreadsheet_id
   TOPIC_ID=154
   ADMIN_USER_IDS=123456789,987654321
   DEFAULT_CHAT_ID=-1001234567890
   OCR_API_KEY=K89427089988957
   ```

4. **Upload credentials.json:**
   - In Render dashboard, go to "Secret Files"
   - Click "Add Secret File"
   - Filename: `credentials.json`
   - Paste the entire contents of your credentials.json
   - Click "Save"

5. **Upload groups.json and houses.json:**
   - Repeat the above for `groups.json`
   - Repeat for `houses.json`

#### Deploy the Web App

1. **Create New Web Service:**
   - New → Web Service
   - Same GitHub repository
   - Root Directory: `webapp`
   - Start Command: `gunicorn api:app --bind 0.0.0.0:$PORT`

2. **Add Environment Variables:**
   ```
   BOT_TOKEN=your_actual_bot_token
   OCR_API_KEY=K89427089988957
   PORT=5000
   ```

3. **Add Google Credentials:**
   - Method 1 (Recommended): Use `GOOGLE_CREDENTIALS_JSON` environment variable
     - Copy the entire contents of `credentials.json` as a single line
     - Add as environment variable
   
   - Method 2: Upload as secret file
     - Upload `credentials.json` as secret file
     - Ensure it's in the webapp directory or adjust `CREDENTIALS_FILE` path

4. **Upload groups.json and houses.json:**
   - Add as secret files in the webapp directory

5. **Get the URL:**
   - Copy your webapp URL (e.g., `https://your-app.onrender.com`)

6. **Set Web App URL in Telegram:**
   - Message @BotFather
   - Send `/mybots` → Select your bot → Menu Button
   - Set URL to your Render webapp URL

---

### Railway

1. **Push to GitHub**
2. **Create New Project:**
   - Go to [Railway](https://railway.app/)
   - New Project → Deploy from GitHub
   - Select your repository

3. **Add Environment Variables:**
   - Same as Render instructions above

4. **Add credentials.json:**
   - Railway supports file uploads similar to Render
   - Or use `GOOGLE_CREDENTIALS_JSON` environment variable

---

### Fly.io

1. **Install Fly CLI:**
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. **Login and Launch:**
   ```bash
   fly auth login
   fly launch
   ```

3. **Set Secrets:**
   ```bash
   fly secrets set BOT_TOKEN="your_token"
   fly secrets set SPREADSHEET_ID="your_id"
   fly secrets set ADMIN_USER_IDS="123456789,987654321"
   ```

4. **Deploy:**
   ```bash
   fly deploy
   ```

---

## 🔍 Security Checklist

Before pushing to GitHub, verify:

- [ ] `.env` is listed in `.gitignore`
- [ ] `credentials.json` is listed in `.gitignore`
- [ ] `groups.json` is listed in `.gitignore`
- [ ] `houses.json` is listed in `.gitignore`
- [ ] No tokens or API keys are hardcoded in `.py` files
- [ ] `.env.example` contains NO real credentials
- [ ] `groups.json.example` contains NO real IDs
- [ ] `houses.json.example` contains NO real names
- [ ] Run `git status` and verify sensitive files show as "ignored"

---

## 🚨 What to Do If Credentials Are Exposed

If you accidentally committed credentials:

### 1. Immediately Rotate All Credentials
- **Telegram Bot:** Message @BotFather → `/revoke` → Create new token
- **Google Service Account:** Delete the compromised service account, create a new one
- **Update all deployment platforms** with new credentials

### 2. Remove from Git History
```bash
# Install BFG Repo-Cleaner
# Download from: https://rtyley.github.io/bfg-repo-cleaner/

# Remove the file from history
bfg --delete-files credentials.json

# Or remove by content
bfg --replace-text passwords.txt  # File containing secrets to replace

# Clean up
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push (WARNING: This rewrites history!)
git push --force
```

### 3. Consider the Repository Compromised
- If the repository was public, assume credentials were seen
- Create a new private repository if needed
- Inform all team members

---

## 📚 Additional Resources

- [Google Cloud Service Accounts](https://cloud.google.com/iam/docs/service-accounts)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Render Secret Files](https://render.com/docs/configure-environment-variables)
- [Git Credential Best Practices](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)

---

## 💬 Support

If you have questions about security setup:
1. Check the `.env.example` file for required variables
2. Review deployment documentation in `DEPLOYMENT.md`
3. Ensure all template files (`.example`) are properly configured

**Remember: When in doubt, don't commit it! Secrets belong in environment variables, not in code.**

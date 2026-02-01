# Free Deployment Guide

This guide covers deploying both the Telegram Bot and Web App for free.

## 🚀 Recommended Free Hosting Options

### Option 1: Render (Recommended - Easiest)
- **Free Tier**: 750 hours/month (enough for 24/7)
- **Supports**: Both bot and web app
- **Auto-deploy**: From GitHub
- **URL**: https://render.com

### Option 2: Railway
- **Free Tier**: $5 credit/month
- **Supports**: Both bot and web app
- **Easy setup**: GitHub integration
- **URL**: https://railway.app

### Option 3: Fly.io
- **Free Tier**: 3 shared VMs
- **Supports**: Both bot and web app
- **Good performance**: Global edge network
- **URL**: https://fly.io

---

## 📋 Prerequisites

1. **GitHub Account** (free)
2. **Google Cloud Service Account** (already have credentials.json)
3. **Telegram Bot Token** (from @BotFather)
4. **OCR API Key** (optional, has default)

---

## 🎯 Deployment Steps

### Step 1: Prepare Your Code

1. **Clean up requirements.txt** (remove duplicates)
2. **Create .gitignore** (if not exists)
3. **Push to GitHub**

### Step 2: Set Environment Variables

You'll need to set these in your hosting platform:

#### For Bot (better1.py):
```
BOT_TOKEN=your_telegram_bot_token
SPREADSHEET_ID=your_google_sheet_id
TOPIC_ID=your_topic_id
ADMIN_USER_IDS=638333361,6513030907
DEFAULT_CHAT_ID=-1003290908954
OCR_API_KEY=K89427089988957
TELEGRAM_API_ID=your_api_id (optional, for history scanner)
TELEGRAM_API_HASH=your_api_hash (optional, for history scanner)
```

#### For Web App (webapp/api.py):
```
BOT_TOKEN=your_telegram_bot_token
GOOGLE_CREDENTIALS_JSON={"type":"service_account",...} (paste full JSON)
OCR_API_KEY=K89427089988957
```

**Important**: For Google Credentials:
- Option A: Upload `credentials.json` file to hosting platform
- Option B: Set `GOOGLE_CREDENTIALS_JSON` environment variable with full JSON content

---

## 🎨 Option 1: Render Deployment

### Deploy Web App:

1. Go to https://render.com and sign up
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Name**: `payment-webapp`
   - **Environment**: `Python 3`
   - **Build Command**: `cd webapp && pip install -r requirements.txt`
   - **Start Command**: `cd webapp && gunicorn api:app --bind 0.0.0.0:$PORT`
   - **Port**: `5000` (auto-set by Render)

5. Add Environment Variables:
   - `BOT_TOKEN`
   - `GOOGLE_CREDENTIALS_JSON` (or upload credentials.json)
   - `OCR_API_KEY`
   - `DEV_MODE` (leave empty for production)

6. Click "Create Web Service"
7. Your app will be live at: `https://payment-webapp.onrender.com`

### Deploy Bot:

1. Click "New +" → "Background Worker"
2. Connect same GitHub repository
3. Configure:
   - **Name**: `payment-bot`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python better1.py`

4. Add Environment Variables (same as above)
5. Upload `credentials.json` file (or use env var)
6. Click "Create Background Worker"

---

## 🚂 Option 2: Railway Deployment

### Deploy Both:

1. Go to https://railway.app and sign up
2. Click "New Project" → "Deploy from GitHub"
3. Select your repository

### For Web App:
1. Add new service → "GitHub Repo"
2. Configure:
   - **Root Directory**: `webapp`
   - **Start Command**: `gunicorn api:app --bind 0.0.0.0:$PORT`
3. Add environment variables
4. Railway auto-generates URL

### For Bot:
1. Add new service → "GitHub Repo"
2. Configure:
   - **Root Directory**: `.` (root)
   - **Start Command**: `python better1.py`
3. Add environment variables
4. Upload `credentials.json` via Railway dashboard

---

## ✈️ Option 3: Fly.io Deployment

### Setup Fly.io:

1. Install Fly CLI: `curl -L https://fly.io/install.sh | sh`
2. Sign up: `fly auth signup`
3. Login: `fly auth login`

### Deploy Web App:

1. In `webapp/` directory:
```bash
fly launch
# Follow prompts:
# - App name: payment-webapp
# - Region: choose closest
# - PostgreSQL: No
```

2. Create `webapp/fly.toml`:
```toml
app = "payment-webapp"
primary_region = "iad"

[build]

[env]
  PORT = "8080"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0

[[services]]
  processes = ["app"]
  http_checks = []
  internal_port = 8080
```

3. Deploy:
```bash
fly deploy
```

### Deploy Bot:

1. In root directory:
```bash
fly launch
# App name: payment-bot
```

2. Create `fly.toml`:
```toml
app = "payment-bot"
primary_region = "iad"

[build]

[env]

[processes]
  app = "python better1.py"

[[services]]
  processes = ["app"]
  internal_port = 0
```

3. Deploy:
```bash
fly deploy
```

---

## 🔧 Configuration Files Needed

### Create `.gitignore`:
```
credentials.json
*.session
token.txt
__pycache__/
*.pyc
.env
.env.local
processed_messages.json
last_run.json
receipts/
attached_assets/
```

### Update `webapp/api.py` for production:
- Remove `DEV_MODE` hardcoding
- Use environment variable for port

---

## 📝 Post-Deployment Checklist

- [ ] Bot is responding to messages
- [ ] Web app is accessible via URL
- [ ] Google Sheets connection works
- [ ] OCR extraction works
- [ ] Beneficiary validation works
- [ ] Duplicate TXID check works
- [ ] Edit mode works
- [ ] Admin panel accessible
- [ ] User panel accessible

---

## 🔗 Setting Up Telegram Web App

After deploying web app:

1. Get your web app URL (e.g., `https://payment-webapp.onrender.com`)
2. Go to @BotFather on Telegram
3. Send `/newapp` or edit existing bot
4. Set Web App URL to your deployed URL
5. Users can now access via Telegram Mini App button

---

## 💡 Tips

1. **Free Tier Limits**:
   - Render: Spins down after 15 min inactivity (takes ~30s to wake)
   - Railway: $5 credit/month (usually enough for 24/7)
   - Fly.io: 3 shared VMs (good for both services)

2. **Keep Services Running**:
   - Use uptime monitoring (UptimeRobot - free) to ping your web app
   - Keeps Render from spinning down

3. **Monitoring**:
   - Check logs regularly
   - Set up error alerts if platform supports

4. **Backup**:
   - Google Sheets is your database (already backed up)
   - Keep `groups.json` and `houses.json` in GitHub

---

## 🆘 Troubleshooting

**Bot not responding:**
- Check bot token is correct
- Check logs for errors
- Verify group ID and topic ID

**Web app not loading:**
- Check environment variables
- Verify Google credentials
- Check port configuration

**OCR not working:**
- Verify OCR API key
- Check API quota/limits
- Review logs for OCR errors

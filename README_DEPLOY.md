# 🚀 Free Deployment - Quick Start

## TL;DR - Deploy in 5 Minutes

### 1. Push to GitHub
```bash
git init
git add .
git commit -m "Ready for deployment"
git remote add origin https://github.com/YOUR_USERNAME/payment-bot.git
git push -u origin main
```

### 2. Deploy on Render (Free)

**Web App:**
- Go to https://render.com
- New → Web Service
- Connect GitHub repo
- Root Directory: `webapp`
- Start Command: `gunicorn api:app --bind 0.0.0.0:$PORT`
- Add env vars (see below)

**Bot:**
- New → Background Worker
- Same repo
- Root Directory: `.`
- Start Command: `python better1.py`
- Add env vars + upload credentials.json

### 3. Environment Variables

**Web App:**
```
BOT_TOKEN=your_token
GOOGLE_CREDENTIALS_JSON={"type":"service_account",...}
OCR_API_KEY=K89427089988957
PORT=5000
```

**Bot:**
```
BOT_TOKEN=your_token
SPREADSHEET_ID=your_sheet_id
TOPIC_ID=154
ADMIN_USER_IDS=638333361,6513030907
DEFAULT_CHAT_ID=-1003290908954
OCR_API_KEY=K89427089988957
```

### 4. Set Telegram Web App URL
- @BotFather → /mybots → Menu Button
- URL: `https://your-app.onrender.com`

Done! ✅

---

## 📚 Full Guides

- **QUICK_DEPLOY.md** - Step-by-step for beginners
- **DEPLOYMENT.md** - Detailed guide with all options

---

## 🆓 Free Hosting Options

1. **Render** - Easiest, 750 hours/month free
2. **Railway** - $5 credit/month
3. **Fly.io** - 3 shared VMs free

All support both bot and web app!

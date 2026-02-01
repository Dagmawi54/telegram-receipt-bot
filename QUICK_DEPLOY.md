# 🚀 Quick Deployment Guide (5 Minutes)

## Option 1: Render (Easiest - Recommended)

### Step 1: Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/payment-bot.git
git push -u origin main
```

### Step 2: Deploy Web App on Render

1. Go to https://render.com → Sign up (free)
2. Click "New +" → "Web Service"
3. Connect GitHub → Select your repo
4. Settings:
   - **Name**: `payment-webapp`
   - **Root Directory**: `webapp`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn api:app --bind 0.0.0.0:$PORT`

5. Environment Variables:
   ```
   BOT_TOKEN=your_bot_token
   GOOGLE_CREDENTIALS_JSON={"type":"service_account",...}
   OCR_API_KEY=K89427089988957
   PORT=5000
   ```

6. Click "Create Web Service"
7. Wait 2-3 minutes → Your app is live! 🎉

### Step 3: Deploy Bot on Render

1. Click "New +" → "Background Worker"
2. Connect same GitHub repo
3. Settings:
   - **Name**: `payment-bot`
   - **Root Directory**: `.` (root)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements_clean.txt`
   - **Start Command**: `python better1.py`

4. Environment Variables:
   ```
   BOT_TOKEN=your_bot_token
   SPREADSHEET_ID=your_sheet_id
   TOPIC_ID=154
   ADMIN_USER_IDS=638333361,6513030907
   DEFAULT_CHAT_ID=-1003290908954
   OCR_API_KEY=K89427089988957
   ```

5. Upload `credentials.json` file (or use GOOGLE_CREDENTIALS_JSON env var)
6. Click "Create Background Worker"
7. Bot is running! 🤖

---

## Option 2: Railway (Alternative)

### Deploy Both at Once:

1. Go to https://railway.app → Sign up
2. "New Project" → "Deploy from GitHub"
3. Select your repo

**For Web App:**
- Add service → Set root directory to `webapp`
- Start command: `gunicorn api:app --bind 0.0.0.0:$PORT`
- Add environment variables

**For Bot:**
- Add service → Root directory: `.`
- Start command: `python better1.py`
- Add environment variables
- Upload `credentials.json`

---

## 🔑 Getting Your Google Credentials JSON

**Option A: Upload File**
- Upload `credentials.json` directly to hosting platform

**Option B: Environment Variable**
1. Open `credentials.json`
2. Copy entire JSON content
3. Paste into `GOOGLE_CREDENTIALS_JSON` environment variable
4. Make sure it's all on one line (no line breaks)

---

## ✅ Verify Deployment

**Web App:**
- Visit your Render/Railway URL
- Should see loading screen or app interface

**Bot:**
- Send `/start` to your bot in Telegram
- Should receive response

---

## 🎯 Set Telegram Web App URL

1. Go to @BotFather on Telegram
2. Send `/mybots` → Select your bot
3. "Bot Settings" → "Menu Button"
4. Set URL to: `https://your-webapp-url.onrender.com`
5. Done! Users can now access via Telegram Mini App

---

## 💡 Pro Tips

1. **Keep Web App Awake** (Render only):
   - Use https://uptimerobot.com (free)
   - Ping your web app every 5 minutes
   - Prevents 15-minute spin-down

2. **Monitor Logs**:
   - Check Render/Railway dashboard logs
   - Watch for errors

3. **Update Code**:
   - Push to GitHub → Auto-deploys
   - No manual deployment needed

---

## 🆘 Common Issues

**"Module not found"**
- Check requirements.txt includes all packages
- Rebuild service

**"Credentials error"**
- Verify GOOGLE_CREDENTIALS_JSON is valid JSON
- Check file uploaded correctly

**"Bot not responding"**
- Check BOT_TOKEN is correct
- Verify bot is running (check logs)
- Make sure bot is added to group

**"Web app shows error"**
- Check all environment variables set
- Verify PORT is set correctly
- Check logs for specific errors

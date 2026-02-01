#!/bin/bash
# Quick deployment script for Render/Railway

echo "🚀 Deployment Helper Script"
echo "=========================="
echo ""
echo "This script helps you prepare for deployment."
echo ""

# Check if .gitignore exists
if [ ! -f .gitignore ]; then
    echo "✅ Creating .gitignore..."
    # Already created
fi

# Check for credentials.json
if [ -f credentials.json ]; then
    echo "⚠️  WARNING: credentials.json found!"
    echo "   Make sure it's in .gitignore (it should be)"
    echo "   You'll need to upload this to your hosting platform"
    echo ""
fi

# Check for required files
echo "📋 Checking required files..."
files=("requirements_clean.txt" "webapp/requirements.txt" "groups.json" "better1.py" "webapp/api.py")
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✅ $file"
    else
        echo "   ❌ $file (MISSING)"
    fi
done

echo ""
echo "📝 Next Steps:"
echo "1. Push your code to GitHub"
echo "2. Go to https://render.com (or railway.app)"
echo "3. Follow QUICK_DEPLOY.md guide"
echo ""
echo "🔑 Environment Variables Needed:"
echo "   - BOT_TOKEN"
echo "   - GOOGLE_CREDENTIALS_JSON (or upload credentials.json)"
echo "   - OCR_API_KEY"
echo "   - SPREADSHEET_ID, TOPIC_ID, etc. (for bot)"
echo ""

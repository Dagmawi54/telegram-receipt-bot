# Overview

This is a Telegram bot designed to process payment receipts for an apartment complex. The bot extracts transaction details from receipt images using OCR, validates payment information, and stores records in Google Sheets. It supports multi-group deployment, beneficiary validation, and includes features like message editing, auto-deletion, and Ethiopian calendar conversion.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Bot Framework & Communication
- **Technology**: Python Telegram Bot library (v21.7)
- **Communication Pattern**: Asynchronous message handling with webhook or polling
- **Message Processing**: 
  - Tracks processed message IDs to prevent duplicate processing during offline periods
  - Supports buffered message processing when bot comes back online
  - Auto-deletes success messages after 10 minutes and error messages after 3 minutes

## Multi-Group Support
- **Design Pattern**: Configuration-based multi-tenancy
- **Configuration File**: `groups.json` - Maps Telegram group IDs to their respective configurations
- **Group Isolation**: Each group has:
  - Its own Google Sheets spreadsheet
  - Specific topic/thread ID for responses
  - Admin user list for privileged operations
  - Custom house number mapping file
- **Rationale**: Allows single bot instance to serve multiple apartment complexes without data mixing

## OCR & Data Extraction
- **Technology**: Tesseract OCR via pytesseract library
- **Image Processing**: Pillow (PIL) for image manipulation
- **Extraction Features**:
  - Transaction IDs (with/without colon format)
  - Payment amounts (VAT-free extraction)
  - Payment dates (with Gregorian to Ethiopian calendar conversion)
  - Beneficiary/receiver names from receipts
  - Payment reasons (displayed in Amharic)
  - House numbers (3-4 digit format)

## Beneficiary Validation
- **Purpose**: Prevents saving receipts sent to incorrect accounts
- **Expected Accounts**: SEYOUM ASSEFA and/or SENAIT DAGNIE
- **Validation Flow**:
  1. Extract beneficiary name from receipt OCR
  2. Compare against expected account names
  3. Block save operation if mismatch detected
  4. Display clear error message with account details
  
## Edit Mode System
- **User-Specific Editing**: Each user can enter edit mode independently via `/edit` command or Edit button
- **Extended Timeout**: 60 seconds for edit mode vs 30 seconds for normal processing
- **Thread Isolation**: Edit timeout notifications sent only to correct topic/thread
- **Prevention Logic**: Smart sheet updates prevent duplicate entries
- **Message Deletion Detection**: Bot checks if user deleted message during buffer window and aborts processing if so

## DM Support & Admin Features
- **/start Command**: Professional popup asking user to select Admin or User access
  - **Admin Access**: Shows admin panel if user is admin, access denied otherwise
  - **User Access**: Shows bot info and how to use instructions with user ID
  - **Navigation**: Back to Start button on all panels for easy navigation
- **Admin Panel in DMs**: Admins can access panel via /admin command or /start button
- **Multi-Group Selection**: Admins of multiple groups can select which group to manage
- **Excel Download**: Admins can download payment data as Excel file from admin panel
- **Payment History Button**: Users see "ታሪክ" (History) button after successful payment
  - **Deep Link Redirect**: Button directly opens bot DM and shows history instantly (no extra message in group)
  - **URL Button**: Uses Telegram deep linking (`t.me/BOT?start=history_...`) for seamless redirect
  - **Sender-Only Access**: Only the original message sender can view their history (validated via user_id in deep link)
  - **Access Denied**: Unauthorized users receive error in their DM (not the group)
- **Professional Menu Layout**: Admin menu uses horizontal 2-button layout per row for cleaner interface
- **Admin Contact**: All error messages reference @sphinxlike for support

## Duplicate Transaction ID Prevention
- **Validation**: Receipts with already-used transaction IDs are rejected
- **Comma-Separated Handling**: Checks TXIDs within comma-separated lists (e.g., "ABC123, XYZ456")
- **Cross-Sheet Check**: Validates across all payment sheets (water, electricity, penalty, etc.)
- **User Feedback**: Clear error message with location of duplicate entry

## Data Storage
- **Primary Storage**: Google Sheets via gspread library
- **Authentication**: Service account credentials (`credentials.json`)
- **Local Storage**:
  - `processed_messages.json`: Tracks processed message IDs for offline resilience
  - `houses.json`: Maps house numbers to resident names (Amharic)
  - `groups.json`: Group configuration database

## Calendar System
- **Conversion Library**: convertdate
- **Purpose**: Converts Gregorian dates to Ethiopian calendar for local context
- **Integration**: Automatic conversion during receipt processing

## Localization
- **Language**: Amharic support for payment reasons and house names
- **Display**: Payment reasons shown in Amharic (ውሃ, ኤሌክትሪክ, ቅጣት, etc.)
- **House Mappings**: Resident names stored in Amharic characters

# External Dependencies

## Third-Party Services
- **Telegram Bot API**: Core bot functionality and message handling
- **Hugging Face API**: Token included in `token.txt` (purpose: possibly AI/ML features - token present but usage unclear from main code)

## Google Services
- **Google Sheets API**: 
  - Data persistence layer
  - Accessed via service account authentication
  - Project ID: `stone-bindery-477314-t2`
  - Service account: `pbt-409@stone-bindery-477314-t2.iam.gserviceaccount.com`

## Python Libraries
- **python-telegram-bot** (21.7): Telegram bot framework
- **gspread** (5.11.3): Google Sheets integration
- **google-auth** (2.22.0): Google API authentication
- **oauth2client** (4.1.3): OAuth2 authentication flow
- **pytesseract** (0.3.10): OCR text extraction
- **Pillow** (10.0.1): Image processing
- **convertdate**: Calendar conversion utilities
- **pandas**: Data manipulation
- **openpyxl**: Excel file handling
- **requests** (2.31.0): HTTP requests

## System Dependencies
- **Tesseract OCR**: Required system package for pytesseract (not in requirements.txt but needed for OCR functionality)
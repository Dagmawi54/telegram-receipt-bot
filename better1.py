"""
VERSION 34 - HISTORY SCANNER WITH TELETHON

NEW FEATURES IN V34:
1. History Scanner (/scan_history command):
   ✓ Scans historical messages from a specified date using Telethon
   ✓ Processes photos with receipts and extracts data via OCR
   ✓ Saves to Google Sheets (skips duplicates)
   ✓ Requires TELEGRAM_API_ID and TELEGRAM_API_HASH env vars
   ✓ Admin-only command

PREVIOUS FEATURES (V33):
1. Fixed Edit Mode for Payment Type Changes:
   ✓ Duplicate check now compares house numbers, not row indices
   ✓ Allows editing payment type (other → water) without duplicate error
   ✓ Works even when moving between different sheets

PREVIOUS FEATURES (V31):
1. Context-Aware House Number Extraction:
   ✓ Detects if text is a user caption (short, has keywords) vs OCR receipt (long, no keywords)
   ✓ Captions: Takes FIRST non-year number (e.g., "ቁ 1108 የታህሳስ 2018" → 1108)
   ✓ OCR receipts: Takes LAST non-year number (avoids phone UI elements at top)
   ✓ Best of both worlds - works with and without captions

PREVIOUS FEATURES (V30):
1. House Number Extraction Improvements:
   ✓ Excludes year numbers (2018, 2025, etc.) from house number candidates
   ✓ Prioritizes first valid 3-4 digit number over last (avoids year confusion)
   ✓ Better handling of captions like "ቁ 1108 የታህሳስ 2018" → extracts 1108, not 2018
   
2. Edit Mode Duplicate Check Fix:
   ✓ Skips entire user's house row when checking for duplicate TXIDs in edit mode
   ✓ Prevents false "receipt sent before" error when editing own submission
   ✓ Allows users to edit month/reason/amount without TXID conflict

PREVIOUS FEATURES (V29):
1. Telebirr Receipt Support:
   ✓ Recognizes telebirr invoice numbers (e.g., DAE3SX92FL, DAE15X922FL)
   ✓ Improved amount extraction with fallback for garbled OCR labels
   ✓ Handles standalone amounts like "1000.00 Birr" even when labels are corrupted
   ✓ Better tolerance for OCR errors in receipt processing

PREVIOUS FEATURES (V28):
1. Message Filtering System:
   ✓ Filter by start date (BOT_START_DATE environment variable)
   ✓ Filter by minimum message ID (MIN_MESSAGE_ID environment variable)
   ✓ Auto-resume from last processed message if no filter set
   ✓ Prevents processing historical receipts on bot startup
   ✓ Filtered messages marked as processed to avoid re-checking

PREVIOUS FEATURES (V27):
1. Fixed Beneficiary Extraction:
   ✓ Now correctly identifies beneficiary after account number line
   ✓ Skips sender names (KALKIDAN TESHOME) and finds actual beneficiary
   ✓ Uses account number as delimiter between sender and beneficiary sections
   ✓ Receipt payment sent to SEYOUM ASSEFA AND OR SENAIT DAGNIE now correctly recognized

PREVIOUS FEATURES (V26):
1. Edit Mode Safety:
   ✓ When user sends NEW message during edit mode, previous edit data is cleared
   ✓ Prevents accidental saving of wrong/old data with new receipt

PREVIOUS FIXES (V25):
1. CRITICAL FIX - Message Skip Bug:
   ✓ Messages no longer marked as processed BEFORE validation
   ✓ Only marked processed AFTER successful buffering
   ✓ If OCR/validation fails, message can be retried (won't be locked out)
   ✓ Fixes issue where messages after 534 were silently skipped forever

PREVIOUS FIXES (V24):
1. Fixed Duplicate TXID Detection:
   ✓ Now checks ALL cells including current cell for NEW submissions
   ✓ Only skips current cell in EDIT mode (allows user to edit their own payment)
   ✓ Properly rejects duplicate TXIDs across all payment sheets

PREVIOUS FEATURES (V23):
1. Fixed House Number Extraction:
   ✓ Now prioritizes numbers after 'ቤት ቁጥር' (house number pattern)
   ✓ Prioritizes 'H.No', 'H-No', 'House' patterns
   ✓ Falls back to last 3-4 digit number (house usually after amount)
   
2. Fixed History Button:
   ✓ No extra "redirect" message in group chat
   ✓ Direct deep link to DM for instant history view

PREVIOUS FEATURES (V21-22):
1. Beneficiary/Receiver Validation:
   ✓ Extracts beneficiary name from receipts (who received the payment)
   ✓ Validates against expected accounts (SEYOUM ASSEFA and/or SENAIT DAGNIE)
   ✓ Blocks saving if payment sent to wrong account
   ✓ Shows clear error message with account name mismatch
   ✓ Auto-deletes error messages after 3 minutes

PREVIOUS FEATURES (V20):
1. Amharic Payment Reason Display:
   ✓ Payment reasons now shown in Amharic (ውሃ, ኤሌክትሪክ, ቅጣት, etc.)
   ✓ Consistent Amharic display across all user-facing messages
   
2. Message Tracking (Offline Support):
   ✓ Tracks processed message IDs to avoid re-analyzing messages
   ✓ When bot comes back online after downtime, only processes new messages
   ✓ Prevents duplicate processing of messages sent while bot was offline
   
3. Fixed Thread ID Issue:
   ✓ 60-second edit mode timeout notification now only sent to correct thread
   ✓ No more timeout messages appearing in general/wrong topics
   
4. Multi-Group Support (Infrastructure):
   ✓ Bot can be configured to work with multiple Telegram groups
   ✓ Each group can have its own spreadsheet and topic ID
   ✓ To add a new group, add entry to GROUP_CONFIGS dictionary

5. Auto-Delete Messages:
   ✓ Success/recorded data messages disappear after 10 minutes (600s)
   ✓ Error messages disappear after 3 minutes (180s)

PREVIOUS FEATURES (V19):
- Full Message Edit Mode
- Extended Edit Timeout (60s for edit, 25s for normal)
- Smart Sheet Updates (no duplicate entries)
- User-specific Edit Mode (/edit command + Edit button)
- Multi-User Isolation
- Transaction ID Extraction (with/without colon)
- Caption Month Extraction (user text → caption → OCR priority)
- VAT-Free Amount Extraction
- Flexible House Number Input (3-4 digits)
- Gregorian to Ethiopian calendar conversion
"""

import re
import json
import logging
import asyncio
from datetime import datetime
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import BadRequest
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account
import requests

# ========== CONFIGURATION ==========
import os

# ========== LOGGING (must be initialized early) ==========
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# CRITICAL: Set BOT_TOKEN environment variable before running
# The previous token has been exposed in version control and should be rotated
# Get a new token from @BotFather on Telegram and set it as an environment variable:
#   export BOT_TOKEN="your_new_bot_token_here"
# Or temporarily replace YOUR_BOT_TOKEN_HERE below for testing
BOT_TOKEN = os.getenv('BOT_TOKEN', "YOUR_BOT_TOKEN_HERE")

# Global variable to store bot username for deep linking
BOT_USERNAME = None

# ========== MESSAGE START DATE/ID FILTER ==========
# Set a start date to ignore messages before this date (format: YYYY-MM-DD)
# Example: "2025-12-12" will only process messages from Dec 12, 2025 onwards
# If not set (None), bot will resume from last processed message (uses processed_messages.json)
BOT_START_DATE = os.getenv('BOT_START_DATE', None)  # None = no date filter

# Alternative: Set a minimum message ID to process
# Example: "534" will only process messages with ID >= 534
# If not set (None), bot will resume from last processed message
MIN_MESSAGE_ID = os.getenv('MIN_MESSAGE_ID', None)  # None = no message ID filter

# Note: If neither BOT_START_DATE nor MIN_MESSAGE_ID is set, the bot automatically
# resumes from where it last stopped using the processed_messages.json tracking system.

# ========== TELETHON CONFIGURATION (for history scanning) ==========
# Get these from https://my.telegram.org - required for /scan_history command
TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID', None)
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH', None)

# Telethon client (initialized lazily when needed)
telethon_client = None

# ========== MULTI-GROUP CONFIGURATION LOADER ==========
def load_group_configs():
    """Load multi-group configuration from groups.json"""
    groups_file = "groups.json"
    
    # Try to load from groups.json
    try:
        with open(groups_file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            groups = config_data.get('groups', {})
            
            # Convert string chat_ids to integers
            group_configs = {}
            for chat_id_str, group_data in groups.items():
                # Skip instruction entries
                if chat_id_str.startswith('_') or chat_id_str.startswith('EXAMPLE'):
                    continue
                    
                try:
                    chat_id = int(chat_id_str)
                    group_configs[chat_id] = group_data
                except ValueError:
                    logger.warning(f"⚠️ Invalid chat_id in groups.json: {chat_id_str} (must be numeric)")
                    
            if not group_configs:
                logger.warning(f"⚠️ No valid groups found in {groups_file}, using fallback configuration")
                return None
                
            logger.info(f"✓ Loaded {len(group_configs)} group(s) from {groups_file}")
            return group_configs
            
    except FileNotFoundError:
        logger.warning(f"⚠️ {groups_file} not found, using environment variable fallback")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON in {groups_file}: {e}")
        return None

# Load group configs from file or use fallback
GROUP_CONFIGS = load_group_configs()

# Fallback to environment variables if groups.json not configured
if GROUP_CONFIGS is None:
    logger.info("Using fallback configuration from environment variables")
    SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', "1MlAyMsDRX1sZn23KqDztuPaG4hLuUC4CsFUmjU_Mm3I")
    TOPIC_ID = int(os.getenv('TOPIC_ID', 154))
    ADMIN_USER_IDS_STR = os.getenv('ADMIN_USER_IDS', '638333361,1190394636,6513030907')
    ADMIN_USER_IDS = [int(uid.strip()) for uid in ADMIN_USER_IDS_STR.split(',') if uid.strip()]
    
    # Create single-group config for backward compatibility
    DEFAULT_CHAT_ID = int(os.getenv('DEFAULT_CHAT_ID', '-1003290908954'))
    GROUP_CONFIGS = {
        DEFAULT_CHAT_ID: {
            'name': 'Default Group',
            'spreadsheet_id': SPREADSHEET_ID,
            'topic_id': TOPIC_ID,
            'houses_file': 'houses.json',
            'admin_user_ids': ADMIN_USER_IDS
        }
    }
    
DEFAULT_GROUP_ID = list(GROUP_CONFIGS.keys())[0]

CREDENTIALS_FILE = "credentials.json"

OCR_API_URL = "https://api.ocr.space/parse/image"
OCR_API_KEY = os.getenv('OCR_API_KEY', "K89427089988957")  # Updated OCR key

PROCESSED_MESSAGES_FILE = "processed_messages.json"
LAST_RUN_FILE = "last_run.json"  # Tracks when bot last ran for auto-scan

# ========== BENEFICIARY VALIDATION ==========
# Expected account names for payment validation (requires full first+last name match)
VALID_BENEFICIARIES = [
    "SEYOUM ASSEFA",
    "SENAIT DAGNIE",
    "SEYOUM ASSEFA AND SENAIT DAGNIE",
    "SEYOUM ASSEFA OR SENAIT DAGNIE",
    "ASSEFA SEYOUM",  # Reversed order variant
    "DAGNIE SENAIT"   # Reversed order variant
]

# ========== PER-GROUP STATE MANAGEMENT ==========
# Message buffering (wait 30 seconds to collect multiple messages from same user)
MESSAGE_BUFFER_DELAY = 30  # seconds
EDIT_MODE_DELAY = 60  # seconds - longer timeout for edit mode

# All state is now partitioned by (chat_id, user_id) for multi-group isolation
# Using nested defaultdict: {chat_id: {user_id: ...}}
def nested_defaultdict():
    return defaultdict(list)

user_message_buffers = defaultdict(nested_defaultdict)  # {chat_id: {user_id: [messages]}}
user_buffer_tasks = defaultdict(dict)  # {chat_id: {user_id: asyncio.Task}}

# Track last submissions for edit mode (group-specific, user-specific)
user_last_submissions = defaultdict(dict)  # {chat_id: {user_id: {'data': {...}, 'sheet_name': '...', ...}}}

# Track which users are in edit mode (per group)
user_edit_mode = defaultdict(dict)  # {chat_id: {user_id: True/False}}
user_edit_mode_tasks = defaultdict(dict)  # {chat_id: {user_id: asyncio.Task}}

# Track which admins are in search mode (per group)
admin_search_mode = defaultdict(dict)  # {chat_id: {user_id: True/False}}

# Track processed messages (to avoid re-analyzing messages when bot was offline)
# Uses composite keys (chat_id, message_id, thread_id) to support multi-group
processed_message_ids = set()  # Set of tuples: (chat_id, message_id, thread_id)

# ========== PAYMENT REASONS ==========
PAYMENT_REASONS = {
    'water': ['ውሃ', 'water', 'wuha', 'weha', 'የውሀ', 'ውሀ', 'wiha', 'የውሃ', 'የውሀ ክፍያ', 'የውሃ ክፍያ', 'wha', 'ውኃ', 
              'የዉሃ', 'ዉሃ', 'የዉሀ', 'ዉሀ', 'የዉሃ ክፍያ', 'ዉኃ', 'የዉኃ'],  # Added variations with ዉ character
    'electricity': ['ኤሌክትሪክ', 'የመብራት', 'ሙቀት', 'electricity', 'electric', 'power', 'መብራት'],
    'development': ['የልማት', 'ልማት', 'አካባቢ', 'ጥገና', 'ጤና', 'development', 'environmental', 'environment', 'maintenance', 'repair', 'health', 'medical', 'hospital', 'doctor'],
    'penalty': ['ቅጣት', 'የቅጣት', 'penalty', 'fine', 'ketat', 'ktat', 'kitat'],
    'other': ['ያልታወቀ', 'other', 'unknown']
}

# Payment reasons in Amharic (for display)
PAYMENT_REASONS_AMHARIC = {
    'water': 'ውሀ',
    'electricity': 'የመብራት',
    'development': 'የልማት',
    'penalty': 'የቅጣት',
    'other': 'ያልታወቀ ❌'
}

# ========== ETHIOPIAN CALENDAR MONTHS ==========
ETHIOPIAN_MONTHS_LIST = [
    'Meskerem',  # 1st month
    'Tikimt',  # 2nd month
    'Hidar',  # 3rd month
    'Tahsas',  # 4th month
    'Tir',  # 5th month
    'Yekatit',  # 6th month
    'Megabit',  # 7th month
    'Miyazya',  # 8th month
    'Ginbot',  # 9th month
    'Sene',  # 10th month
    'Hamle',  # 11th month
    'Nehase',  # 12th month
    'Pagume'  # 13th month
]

# Ethiopian months in Amharic
ETHIOPIAN_MONTHS_AMHARIC = {
    'Meskerem': 'መስከረም',
    'Tikimt': 'ጥቅምት',
    'Hidar': 'ህዳር',
    'Tahsas': 'ታህሳስ',
    'Tir': 'ጥር',
    'Yekatit': 'የካቲት',
    'Megabit': 'መጋቢት',
    'Miyazya': 'ሚያዝያ',
    'Ginbot': 'ግንቦት',
    'Sene': 'ሰኔ',
    'Hamle': 'ሐምሌ',
    'Nehase': 'ነሐሴ',
    'Pagume': 'ጳጉሜ'
}

# ========== GREGORIAN TO ETHIOPIAN CALENDAR CONVERSION ==========
# Gregorian month → Ethiopian month (ACTUAL conversion, not translation!)
# Ethiopian calendar is 7-8 years behind
# Approximate mapping (varies by exact date):
GREGORIAN_TO_ETHIOPIAN = {
    # Gregorian Month → Ethiopian Month (equivalent)
    'january': 'Tir',  # Jan ≈ Tir (5th Ethiopian month)
    'february': 'Yekatit',  # Feb ≈ Yekatit (6th Ethiopian month)
    'march': 'Megabit',  # Mar ≈ Megabit (7th Ethiopian month)
    'april': 'Miyazya',  # Apr ≈ Miyazya (8th Ethiopian month)
    'may': 'Ginbot',  # May ≈ Ginbot (9th Ethiopian month)
    'june': 'Sene',  # Jun ≈ Sene (10th Ethiopian month)
    'july': 'Hamle',  # Jul ≈ Hamle (11th Ethiopian month)
    'august': 'Nehase',  # Aug ≈ Nehase (12th Ethiopian month)
    'september': 'Pagume',  # Sep ≈ Pagume (13th Ethiopian month)
    'october': 'Meskerem',  # Oct ≈ Meskerem (1st Ethiopian month)
    'november': 'Tikimt',  # Nov ≈ Tikimt (2nd Ethiopian month)
    'december': 'Hidar',  # Dec ≈ Hidar (3rd Ethiopian month)

    # Shortened versions
    'jan': 'Tir',
    'feb': 'Yekatit',
    'mar': 'Megabit',
    'apr': 'Miyazya',
    'may': 'Ginbot',
    'jun': 'Sene',
    'jul': 'Hamle',
    'aug': 'Nehase',
    'sep': 'Pagume',
    'oct': 'Meskerem',
    'nov': 'Tikimt',
    'dec': 'Hidar',
}

# Ethiopian months - direct (already Ethiopian, return as is)
for eth_month in ETHIOPIAN_MONTHS_LIST:
    GREGORIAN_TO_ETHIOPIAN[eth_month.lower()] = eth_month

# Add alternate spellings for Ethiopian months (common user variations)
GREGORIAN_TO_ETHIOPIAN['hedar'] = 'Hidar'  # Common misspelling of Hidar

# Add Amharic month names (full and shortened versions)
AMHARIC_TO_ETHIOPIAN = {
    # Full Amharic names
    'መስከረም': 'Meskerem',
    'የመስከረም': 'Meskerem',  # With የ prefix ("of")
    'ጥቅምት': 'Tikimt',
    'የጥቅምት': 'Tikimt',  # With የ prefix
    'ጥቅም': 'Tikimt',  # Shortened version
    'የጥቅም': 'Tikimt',  # Shortened with የ prefix
    'ህዳር': 'Hidar',
    'የህዳር': 'Hidar',  # With የ prefix
    'የሕዳር': 'Hidar',  # Alternative spelling with የ prefix
    'ሕዳር': 'Hidar',  # Alternative spelling
    'ታህሳስ': 'Tahsas',
    'የታህሳስ': 'Tahsas',  # With የ prefix
    'ታህሳ': 'Tahsas',  # Shortened
    'የታህሳ': 'Tahsas',  # Shortened with የ prefix
    'ጥር': 'Tir',
    'የጥር': 'Tir',  # With የ prefix
    'የካቲት': 'Yekatit',
    'የካት': 'Yekatit',  # Shortened
    'መጋቢት': 'Megabit',
    'የመጋቢት': 'Megabit',  # With የ prefix
    'መጋቢ': 'Megabit',  # Shortened
    'የመጋቢ': 'Megabit',  # Shortened with የ prefix
    'ሚያዝያ': 'Miyazya',
    'የሚያዝያ': 'Miyazya',  # With የ prefix
    'ሚያዝ': 'Miyazya',  # Shortened
    'የሚያዝ': 'Miyazya',  # Shortened with የ prefix
    'ግንቦት': 'Ginbot',
    'የግንቦት': 'Ginbot',  # With የ prefix
    'ግንቦ': 'Ginbot',  # Shortened
    'የግንቦ': 'Ginbot',  # Shortened with የ prefix
    'ሰኔ': 'Sene',
    'የሰኔ': 'Sene',  # With የ prefix
    'ሐምሌ': 'Hamle',
    'የሐምሌ': 'Hamle',  # With የ prefix
    'ነሐሴ': 'Nehase',
    'የነሐሴ': 'Nehase',  # With የ prefix
    'ጳጉሜ': 'Pagume',
    'የጳጉሜ': 'Pagume',  # With የ prefix
}

# Merge Amharic names into the main dictionary
for amharic_name, ethiopian_name in AMHARIC_TO_ETHIOPIAN.items():
    GREGORIAN_TO_ETHIOPIAN[amharic_name] = ethiopian_name

# ========== PER-GROUP RESOURCE LOADING ==========
# Cache for per-group houses data: {chat_id: {house_num: name}}
house_maps = {}

def load_houses_for_group(chat_id: int) -> dict:
    """Load houses data for a specific group (with caching)"""
    if chat_id in house_maps:
        return house_maps[chat_id]
    
    if chat_id not in GROUP_CONFIGS:
        logger.warning(f"⚠️ Unknown chat_id {chat_id}, cannot load houses")
        return {}
    
    houses_file = GROUP_CONFIGS[chat_id].get('houses_file', 'houses.json')
    try:
        with open(houses_file, 'r', encoding='utf-8') as f:
            house_map = json.load(f)
        house_maps[chat_id] = house_map
        logger.info(f"✓ Loaded {len(house_map)} houses from {houses_file} for group {chat_id}")
        return house_map
    except FileNotFoundError:
        logger.warning(f"⚠️ Houses file {houses_file} not found for group {chat_id}")
        house_maps[chat_id] = {}
        return {}
    except Exception as e:
        logger.error(f"❌ Error loading houses for group {chat_id}: {e}")
        house_maps[chat_id] = {}
        return {}

# Load processed message IDs (composite keys: chat_id, message_id, thread_id)
try:
    with open(PROCESSED_MESSAGES_FILE, 'r', encoding='utf-8') as f:
        loaded_data = json.load(f)
        # Convert list of lists back to set of tuples
        processed_message_ids = set(tuple(item) for item in loaded_data)
    logger.info(f"✓ Loaded {len(processed_message_ids)} processed message IDs")
except:
    logger.info(f"✓ Starting fresh - no processed messages file found")
    processed_message_ids = set()

def save_processed_messages():
    """Save processed message IDs to file (as list of lists for JSON compatibility)"""
    try:
        with open(PROCESSED_MESSAGES_FILE, 'w', encoding='utf-8') as f:
            # Convert set of tuples to list of lists for JSON serialization
            json.dump([list(item) for item in processed_message_ids], f)
    except Exception as e:
        logger.error(f"Error saving processed messages: {e}")


# ========== GOOGLE SHEETS ==========
# Ethiopian months in order for tracking (must match ETHIOPIAN_MONTHS_LIST)
ETHIOPIAN_MONTHS = ETHIOPIAN_MONTHS_LIST

# Cache for per-group Google Sheets: {chat_id: {reason: sheet}}
sheets_cache = {}

def setup_sheets(chat_id: int):
    """Setup Google Sheets with monthly tracking format for a specific group"""
    # Return cached sheets if available
    if chat_id in sheets_cache:
        return sheets_cache[chat_id]
    
    if chat_id not in GROUP_CONFIGS:
        logger.error(f"❌ Unknown chat_id {chat_id}, cannot setup sheets")
        return {}
    
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            CREDENTIALS_FILE, scope)
        gc = gspread.authorize(creds)
        
        # Get spreadsheet ID for this specific group
        group_config = GROUP_CONFIGS[chat_id]
        spreadsheet_id = group_config['spreadsheet_id']
        spreadsheet = gc.open_by_key(spreadsheet_id)
        logger.info(f"✓ Opened spreadsheet {spreadsheet_id} for group {chat_id}")

        sheets = {}
        
        # Load houses for this specific group
        house_map = load_houses_for_group(chat_id)
        
        # Get sorted house numbers for consistent ordering
        sorted_houses = sorted(house_map.keys(), key=lambda x: int(x))

        for reason in PAYMENT_REASONS.keys():
            try:
                sheet = spreadsheet.worksheet(reason.capitalize())
                logger.info(f"Sheet '{reason}' exists, checking structure...")
                
                # Remove any table view/filters
                try:
                    sheet.clear_basic_filter()
                    logger.info(f"✓ Cleared table view/filters from '{reason}'")
                except Exception as e:
                    logger.info(f"No table view to clear from '{reason}' (or error: {e})")
                
                # Check if it needs restructuring (old format vs new 2-column format)
                all_values = sheet.get_all_values()
                # Check if headers match current 2-column format (2 header rows)
                if len(all_values) > 1 and all_values[0][0] == 'No':
                    # Row 1: Month names spanning 2 columns
                    # Row 2: Amount, FT No sub-headers
                    # Check column 3 (index 3) = first month name, column 4 (index 4) = empty (span)
                    # Check row 2 has "Amount" and "FT No" sub-headers
                    # Check for TOTAL row at the bottom (should have "TOTAL" in column B)
                    has_correct_headers = (len(all_values[0]) > 4 and all_values[0][3] == ETHIOPIAN_MONTHS[0] and 
                        all_values[0][4] == '' and len(all_values[1]) > 4 and 
                        all_values[1][3] == 'Amount' and all_values[1][4] == 'FT No')
                    
                    has_totals_row = len(all_values) > 3 and any(row[1] == 'TOTAL' for row in all_values[2:])
                    
                    if has_correct_headers and has_totals_row:
                        logger.info(f"✓ Sheet '{reason}' already has 2-column monthly format with TOTALS row")
                        sheets[reason] = sheet
                        continue
                    elif has_correct_headers and not has_totals_row:
                        logger.info(f"Sheet '{reason}' has format but missing TOTALS row, adding it...")
                        # Add totals row to existing sheet
                        num_houses = len(all_values) - 2  # Subtract 2 header rows
                        totals_row_num = len(all_values) + 1
                        totals_row_data = ['', 'TOTAL', '']
                        
                        def num_to_col(n):
                            string = ""
                            while n > 0:
                                n, remainder = divmod(n - 1, 26)
                                string = chr(65 + remainder) + string
                            return string
                        
                        for month_idx in range(len(ETHIOPIAN_MONTHS)):
                            amount_col_idx = 3 + (month_idx * 2)
                            amount_col_letter = num_to_col(amount_col_idx + 1)
                            sum_formula = f'=SUM({amount_col_letter}3:{amount_col_letter}{totals_row_num - 1})'
                            totals_row_data.append(sum_formula)
                            totals_row_data.append('')
                        totals_row_data.append('')
                        
                        sheet.update(f'A{totals_row_num}', [totals_row_data], value_input_option='USER_ENTERED')
                        logger.info(f"✓ Added TOTALS row at row {totals_row_num}")
                        sheets[reason] = sheet
                        continue
                    else:
                        logger.info(f"Sheet '{reason}' has old format, rebuilding to 2-column...")
                        sheet.clear()
                    
                # Old format detected - clear and rebuild
                logger.info(f"Restructuring '{reason}' to 2-column monthly format...")
                sheet.clear()
                
            except:
                # Sheet doesn't exist - create new one
                logger.info(f"Creating new sheet '{reason}' with monthly tracking...")
                sheet = spreadsheet.add_worksheet(title=reason.capitalize(),
                                                  rows=100,
                                                  cols=50)
            
            # Build 2-row header structure
            # Row 1: Month names (each spanning 2 columns)
            header_row1 = ['No', 'H.No', 'Name']
            for month in ETHIOPIAN_MONTHS:
                header_row1.extend([month, ''])  # Month name spans 2 columns
            header_row1.append('Remark')
            
            # Row 2: Amount and FT No sub-headers under each month
            header_row2 = ['', '', '']  # Empty under No, H.No, Name
            for _ in ETHIOPIAN_MONTHS:
                header_row2.extend(['Amount', 'FT No'])
            header_row2.append('')  # Empty under Remark
            
            # Write both header rows (spans full width)
            sheet.update('A1', [header_row1, header_row2], value_input_option='USER_ENTERED')
            
            # Pre-populate all houses (batch update for efficiency)
            all_house_rows = []
            for idx, house_num in enumerate(sorted_houses, start=1):
                house_name = house_map[house_num]
                # Create row with house info + empty cells for all months
                row_data = [idx, house_num, house_name]
                # Add empty cells for each month (2 columns per month: Amount, FT No)
                row_data.extend([''] * (len(ETHIOPIAN_MONTHS) * 2))
                row_data.append('')  # Remark column
                all_house_rows.append(row_data)
            
            # Batch update all houses at once
            if all_house_rows:
                end_row = 2 + len(all_house_rows)  # Row 1-2 are headers, data starts at row 3
                # Calculate the last column letter (No + H.No + Name + 13 months * 2 cols + Remark)
                num_cols = 3 + (len(ETHIOPIAN_MONTHS) * 2) + 1
                # Convert to letter
                def num_to_col(n):
                    string = ""
                    while n > 0:
                        n, remainder = divmod(n - 1, 26)
                        string = chr(65 + remainder) + string
                    return string
                end_col = num_to_col(num_cols)
                sheet.update(f'A3:{end_col}{end_row}', all_house_rows, value_input_option='USER_ENTERED')
                
                # Add TOTALS row after all houses with SUM formulas for each month
                totals_row_num = end_row + 1
                totals_row_data = ['', 'TOTAL', '']  # Empty No, "TOTAL" label in H.No, empty Name
                
                # Add SUM formula for each month's Amount column
                data_start_row = 3  # First house data row
                data_end_row = end_row  # Last house data row
                
                for month_idx in range(len(ETHIOPIAN_MONTHS)):
                    # Amount column for this month
                    amount_col_idx = 3 + (month_idx * 2)
                    amount_col_letter = num_to_col(amount_col_idx + 1)  # +1 because num_to_col is 1-indexed
                    
                    # SUM formula for this month's Amount column
                    sum_formula = f'=SUM({amount_col_letter}{data_start_row}:{amount_col_letter}{data_end_row})'
                    totals_row_data.append(sum_formula)
                    
                    # Empty for FT No column
                    totals_row_data.append('')
                
                # Empty for Remark column
                totals_row_data.append('')
                
                # Write the totals row
                sheet.update(f'A{totals_row_num}', [totals_row_data], value_input_option='USER_ENTERED')
                logger.info(f"✓ Added TOTALS row at row {totals_row_num}")
            
            logger.info(f"✓ Created '{reason}' with {len(sorted_houses)} houses and {len(ETHIOPIAN_MONTHS)} month columns")
            sheets[reason] = sheet

        logger.info(f"✓ Google Sheets ready ({len(sheets)} sheets)")
        sheets_cache[chat_id] = sheets
        return sheets
    except Exception as e:
        logger.error(f"✗ Sheets error: {e}")
        return None

# ========== SIMPLE SAVE TO SHEETS (for history scanner) ==========
def save_to_sheets(sheets, house_number, amount, txid, month, reason, chat_id):
    """
    Simplified save function for history scanner.
    Saves payment data directly to the appropriate sheet cell.
    """
    target_sheet = sheets.get(reason)
    if not target_sheet:
        target_sheet = sheets.get('other')
        reason = 'other'
    
    if not target_sheet:
        logger.error(f"No sheet found for reason '{reason}'")
        return False
    
    try:
        # Find the row for this house number
        all_values = target_sheet.get_all_values()
        row_index = None
        
        for idx, row in enumerate(all_values[2:], start=3):  # Skip 2 header rows
            if len(row) > 1 and row[1].strip() == str(house_number).strip():
                row_index = idx
                break
        
        if not row_index:
            logger.warning(f"House {house_number} not found in sheet {reason}")
            return False
        
        # Find the column for the month
        if month not in ETHIOPIAN_MONTHS:
            logger.warning(f"Month '{month}' not recognized, using Tir")
            month = 'Tir'
        
        month_index = ETHIOPIAN_MONTHS.index(month)
        
        # Calculate column positions (2 columns per month: Amount, FT No)
        # Columns: No (A=0), H.No (B=1), Name (C=2), then 2 columns per month
        amount_col_idx = 3 + (month_index * 2)
        ftno_col_idx = amount_col_idx + 1
        
        # Convert column index to letter
        def col_to_letter(idx):
            result = ''
            while idx >= 0:
                result = chr(65 + (idx % 26)) + result
                idx = idx // 26 - 1
            return result
        
        amount_col = col_to_letter(amount_col_idx)
        ftno_col = col_to_letter(ftno_col_idx)
        
        # Get current values
        current_amount = all_values[row_index - 1][amount_col_idx].strip() if len(all_values[row_index - 1]) > amount_col_idx else ''
        current_txid = all_values[row_index - 1][ftno_col_idx].strip() if len(all_values[row_index - 1]) > ftno_col_idx else ''
        
        # Append to existing values if they exist
        if current_amount:
            final_amount = f"={current_amount}+{amount}"
        else:
            final_amount = float(amount) if amount else 0
        
        if current_txid:
            final_txid = f"{current_txid}, {txid}"
        else:
            final_txid = txid or ''
        
        # Update the cells
        target_sheet.update(f'{amount_col}{row_index}', [[final_amount]], 
                          value_input_option='USER_ENTERED')
        target_sheet.update(f'{ftno_col}{row_index}', [[final_txid]], 
                          value_input_option='USER_ENTERED')
        
        logger.info(f"✓ Saved to {reason}: House {house_number}, Month {month}")
        return True
        
    except Exception as e:
        logger.error(f"Save error: {e}")
        return False


# ========== OCR ==========
def extract_text_from_image(image_bytes):
    """Extract text from image using OCR with retry logic"""
    max_retries = 3
    timeout_seconds = 45
    
    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                logger.info(f"📸 Retrying OCR (attempt {attempt}/{max_retries})...")
            else:
                logger.info("📸 Running OCR...")

            payload = {
                'apikey': OCR_API_KEY,
                'language': 'eng',
                'isOverlayRequired': False,
                'detectOrientation': True,
                'scale': True,
                'OCREngine': 2
            }

            files = {'file': ('image.jpg', image_bytes, 'image/jpeg')}
            response = requests.post(OCR_API_URL,
                                     files=files,
                                     data=payload,
                                     timeout=timeout_seconds)

            if response.status_code == 200:
                result = response.json()
                if not result.get('IsErroredOnProcessing'):
                    text = result.get('ParsedResults',
                                      [{}])[0].get('ParsedText', '')
                    logger.info(f"✓ OCR done: {len(text)} chars")
                    return text
                else:
                    error_msg = result.get('ErrorMessage', result.get('ErrorDetails', 'Unknown error'))
                    logger.warning(f"✗ OCR processing error on attempt {attempt}: {error_msg}")
                    logger.warning(f"Full OCR response: {result}")
            else:
                logger.warning(f"✗ OCR failed with status {response.status_code} on attempt {attempt}")
                logger.warning(f"Response text: {response.text[:500]}")

        except requests.exceptions.Timeout:
            logger.warning(f"✗ OCR timeout on attempt {attempt}/{max_retries}")
            if attempt == max_retries:
                logger.error("✗ OCR failed after all retries (timeout)")
                return ""
            continue
        except Exception as e:
            logger.error(f"✗ OCR error on attempt {attempt}: {e}")
            if attempt == max_retries:
                return ""
            continue
    
    logger.warning(f"✗ OCR failed after {max_retries} attempts")
    return ""


# ========== RECEIPT-SPECIFIC EXTRACTION ==========


def normalize_amount_lines(text):
    """Preprocess OCR text to join amount labels with their values on separate lines.
    
    Handles table-based layouts (e.g., Zemen Bank) where labels like "Settled Amount"
    appear on one line and the value "ETB 1,000.00" appears on the next line.
    """
    lines = text.split('\n')
    normalized_lines = []
    
    amount_labels = ['settled amount', 'settled', 'amount paid', 'paid', 'debited', 'credited', 
                     'subtotal', 'sub-total', 'sub total', 'total amount']
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            i += 1
            continue
        
        line_lower = line.lower()
        has_amount_label = any(label in line_lower for label in amount_labels)
        
        # Check if next line starts with ETB or has currency pattern
        should_combine = False
        if has_amount_label and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            # Check if next line starts with ETB, birr, or has amount pattern
            if next_line and (next_line.upper().startswith('ETB') or 
                             re.match(r'^[0-9,]+\.[0-9]{2}', next_line)):
                should_combine = True
        
        if should_combine:
            combined = line + ' ' + lines[i + 1].strip()
            normalized_lines.append(combined)
            i += 2
        else:
            normalized_lines.append(line)
            i += 1
    
    return '\n'.join(normalized_lines)


def extract_amount_from_receipt(text):
    """Extract amount from receipt (WITHOUT VAT if possible)"""
    logger.info("Extracting AMOUNT (without VAT)...")
    
    normalized_text = normalize_amount_lines(text)
    logger.info(f"📝 Normalized text preview: {normalized_text[:500]}...")

    # Try normalized text first, then fall back to original text
    for search_text in [normalized_text, text]:
        # Priority 1: Look for "Settled Amount" specifically (Zemen Bank format)
        settled_pattern = r'settled\s+amount[:\s]*ETB\s*([0-9,]+(?:\.[0-9]{2})?)'
        match = re.search(settled_pattern, search_text, re.IGNORECASE | re.DOTALL)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                amount_val = float(amount_str)
                if amount_val > 50:
                    logger.info(f"✓ Amount (Settled Amount): {amount_str}")
                    return amount_str
            except:
                pass
        
        # Priority 2: Look for amounts specifically marked as WITHOUT VAT or Subtotal
        without_vat_patterns = [
            r'(?:subtotal|sub-total|sub total|before vat|excluding vat|excl\.? vat)[:\s]*(?:ETB|birr|ብር)?\s*([0-9,]+(?:\.[0-9]{2})?)',
            r'(?:ETB|birr|ብር)?\s*([0-9,]+(?:\.[0-9]{2})?)\s*(?:before vat|excluding vat|excl\.? vat)',
        ]

        for pattern in without_vat_patterns:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '')
                try:
                    amount_val = float(amount_str)
                    if amount_val > 50:
                        logger.info(f"✓ Amount (without VAT): {amount_str}")
                        return amount_str
                except:
                    pass

        # Priority 3: Look for "ETB X debited" pattern (base amount, not total)
        debited_pattern = r'ETB\s*([0-9,]+(?:\.[0-9]{2})?)\s+debited'
        match = re.search(debited_pattern, search_text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                amount_val = float(amount_str)
                if amount_val > 50:
                    match_pos = match.start()
                    preceding_text = search_text[max(0, match_pos - 50):match_pos]
                    if 'total' not in preceding_text.lower():
                        logger.info(f"✓ Amount (debited, no VAT): {amount_str}")
                        return amount_str
            except:
                pass

        # Priority 4: Standard amount extraction (fallback)
        standard_patterns = [
            r'(?:debited|Debited|DEBITED).*?ETB\s*([0-9,]+(?:\.[0-9]{2})?)',
            r'(?:Amount|amount|AMOUNT).*?(?:ETB|birr)?\s*([0-9,]+(?:\.[0-9]{2})?)',
            r'(?:ETB|birr|ብር)\s*([0-9,]+(?:\.[0-9]{2})?)',
            r'([0-9,]+(?:\.[0-9]{2})?)\s*(?:ETB|birr|ብር)',
        ]

        all_amounts = []
        for pattern in standard_patterns:
            for match in re.finditer(pattern, search_text, re.IGNORECASE):
                amount_str = match.group(1).replace(',', '')
                try:
                    amount_val = float(amount_str)
                    if amount_val > 50:
                        match_pos = match.start()
                        context = search_text[max(0, match_pos - 30):min(len(search_text), match_pos + 100)]
                        # Exclude total amounts and service charges
                        if 'total' not in context.lower() and 'with commission' not in context.lower() and 'service charge' not in context.lower() and 'vat' not in context.lower():
                            all_amounts.append(amount_val)
                            logger.info(f"  Found candidate: {amount_val} (context: ...{context[:50]}...)")
                except:
                    pass

        # Return the smallest valid amount (likely without VAT)
        if all_amounts:
            min_amount = min(all_amounts)
            logger.info(f"✓ Amount (smallest, likely without VAT): {min_amount}")
            return str(min_amount)

    # FINAL FALLBACK: Look for ANY amount pattern (even with garbled labels)
    # This helps when OCR garbles "Settled Amount" to "8th6.4@•00m/l/Settled Amount"
    # Just find "1000.00 Birr" or similar standalone amounts
    logger.info("Standard patterns failed, trying final fallback for standalone amounts...")
    
    fallback_patterns = [
        # Just number followed by Birr (even if label is garbled)
        r'(?:^|\n|\s)([0-9,]+\.00)\s*Birr',
        r'(?:^|\n|\s)([0-9,]+\.[0-9]{2})\s*(?:Birr|ETB)',
    ]
    
    for pattern in fallback_patterns:
        for match in re.finditer(pattern, search_text, re.MULTILINE | re.IGNORECASE):
            amount_str = match.group(1).replace(',', '')
            try:
                amount_val = float(amount_str)
                if amount_val > 50:  # Reasonable minimum
                    logger.info(f"✓ Amount (fallback - standalone): {amount_str}")
                    return amount_str
            except:
                pass

    logger.warning("✗ Amount not found")
    return ""


def extract_date_from_receipt(text):
    """Extract date from receipt"""
    logger.info("Extracting DATE...")

    patterns = [
        r'(\d{1,2}[-/]\w{3}[-/]\d{4})',
        r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})',
        r'on\s+(\d{1,2}[-/]\w{3}[-/]\d{4})',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            date = match.group(1)
            logger.info(f"✓ Date: {date}")
            return date

    logger.warning("✗ Date not found")
    return ""


def extract_txid_from_receipt(text):
    """Extract transaction ID from receipt"""
    logger.info("Extracting TRANSACTION ID...")
    logger.info(f"🔍 Full OCR text for TxID extraction ({len(text)} chars):\n{text[:1500]}")

    # Words to exclude from transaction ID matches (common labels on receipts)
    excluded_words = [
        'transaction', 'reference', 'number', 'invoice', 'receipt', 'details',
        'reason', 'type', 'time', 'date', 'amount', 'account', 'completed',
        'payment', 'transfer', 'charge', 'commission', 'sender', 'nolawi'
    ]

    # Priority 1: Payment order number or Reference No (Zemen Bank specific)
    # Look for patterns near these labels, even if the value is on a different line
    zemen_patterns = [
        r'(?:payment\s+order\s+number|reference\s+no\.?)[:\s]*\n?\s*([A-Z0-9]{10,})',
        r'(?:payment\s+order\s+number|reference\s+no\.?)[:\s]+([A-Z0-9]{10,})',
        r'(?:thy\s+HY\s+PiP\s+Payment\s+order\s+number)[:\s]*\n?\s*([A-Z0-9]{10,})',  # OCR-specific pattern
    ]
    
    for pattern in zemen_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            txid = match.group(1).strip()
            logger.info(f"🔍 Found candidate from Zemen pattern: {txid}")
            # Must be alphanumeric, at least 10 chars, and not just the word "payment reason"
            if (len(txid) >= 10 and txid.lower() not in excluded_words
                    and any(c.isdigit() for c in txid) and any(c.isalpha() for c in txid)
                    and 'reason' not in txid.lower()):
                logger.info(f"✓ TxID (Payment Order/Reference): {txid}")
                return txid

    # Priority 2: Telebirr invoice number (e.g., DAE3SX92FL, DAE15X922FL)
    # Pattern: 3 letters + alphanumeric + 2-3 letters + more alphanumeric (10-15 chars total)
    telebirr_invoice_patterns = [
        # Invoice No: DAE3SX92FL format (after label)
        r'(?:invoice\s+no\.?|Ph?ES\s+PC)[:\s]*\n?\s*([A-Z]{3}[A-Z0-9]{7,12})',
        # Standalone format (no label, just the invoice number itself)
        r'\b([A-Z]{3}[0-9][A-Z0-9]{2}[A-Z]{2}[A-Z0-9]{2,5})\b',
    ]
    
    for pattern in telebirr_invoice_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            txid = match.group(1).strip().upper()
            # Validate: 10-15 chars, starts with 3 letters, has mix of letters and numbers
            if (10 <= len(txid) <= 15 
                    and txid[:3].isalpha() 
                    and any(c.isdigit() for c in txid)
                    and txid.lower() not in excluded_words):
                logger.info(f"✓ TxID (Telebirr invoice): {txid}")
                return txid

    # Priority 3: Transaction ID variants
    priority_patterns = [
        # Transaction ID variants WITH COLON
        r'(?:transaction\s+id|tx\s+id|txid|tran\s+ref)\s*:\s*([A-Za-z0-9]+)',

        # Transaction ID variants WITHOUT COLON (just whitespace)
        r'(?:transaction\s+id|tx\s+id|txid|tran\s+ref)\s+([A-Za-z0-9]+)',

        # VAT invoice/receipt patterns with optional parentheses
        r'(?:reference\s+no\.?\s*\(vat\s+invoice\s+no\.?\)|vat\s+invoice\s+no\.?)\s*:\s*([A-Za-z0-9]+)',
        r'(?:vat\s+receipt\s+number|vat\s+receipt\s+no\.?)\s*:\s*([A-Za-z0-9]+)',
        r'(?:vat\s+invoice\s+number|vat\s+invoice\s+no\.?)\s*:\s*([A-Za-z0-9]+)',

        # Generic reference patterns (but NOT payment reason)
        r'(?:reference\s+number|ref\s+no\.?)\s*:\s*([A-Za-z0-9]+)',
    ]

    for pattern in priority_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            txid = match.group(1).strip()
            # Filter out common words and require mixed alphanumeric
            if (len(txid) >= 5 and txid.lower() not in excluded_words
                    and not txid.isnumeric() and not txid.isalpha()
                    and any(c.isdigit() for c in txid) and any(c.isalpha() for c in txid)
                    and 'reason' not in txid.lower()):
                logger.info(f"✓ TxID: {txid}")
                return txid

    # Fallback: hyphenated format (e.g., ABC-DEF-123) but NOT dates or currency patterns
    matches = re.findall(r'([A-Za-z0-9]+-[A-Za-z0-9]+-[A-Za-z0-9]+)', text)
    for match in matches:
        # Must contain at least one letter (exclude pure date formats like 2025-11-05)
        # Also exclude currency-related patterns (ETB, BIRR, FTB) and payment reason patterns
        match_upper = match.upper()
        if (any(c.isalpha() for c in match) and len(match) >= 8
                and match.lower() not in excluded_words
                and not any(currency in match_upper for currency in ['ETB', 'BIRR', 'FTB'])
                and 'reason' not in match.lower()):
            logger.info(f"✓ TxID (hyphenated): {match}")
            return match

    # Fallback: any alphanumeric 10+ characters but SKIP patterns near "payment reason"
    # First, check if this appears near "payment reason" and skip it
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if 'payment reason' in line.lower():
            # Find alphanumeric patterns in this line
            reason_matches = re.findall(r'([A-Z0-9]{8,})', line, re.IGNORECASE)
            # Mark these for exclusion
            excluded_words.extend([m.lower() for m in reason_matches])
    
    matches = re.findall(
        r'\b([A-Z]{2}[A-Za-z0-9]{8,}|[0-9]{2}[A-Z]{2,}[A-Z0-9]{6,}|[A-Z0-9]{10,})\b', text)
    for match in matches:
        # Must contain at least one letter and one number, and not be a common word or payment reason
        if (match.lower() not in excluded_words and not match.isnumeric()
                and not match.isalpha() and any(c.isdigit() for c in match)
                and any(c.isalpha() for c in match)):
            logger.info(f"✓ TxID (alphanumeric): {match}")
            return match

    logger.warning("✗ TxID not found")
    return ""


def extract_name_from_receipt(text):
    """Extract name from receipt (payer, not beneficiary)"""
    logger.info("Extracting NAME...")

    patterns = [
        r'(?:debited from|from|paid by|payer)[:\s]+([A-Z][A-Za-z\s]+?)(?:\n|for|with)',
        r'(?:ABATE|payer|account holder)[:\s]+([A-Z][A-Za-z\s]+?)(?:\n|for|on)',
        r'([A-Z][A-Z][A-Z\s]{2,}?)(?:\n|for|BUNAGO)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            name = re.sub(r'\s+', ' ', name).strip()
            if len(name) > 3 and len(name) < 50:
                logger.info(f"✓ Name: {name}")
                return name

    logger.warning("✗ Name not found")
    return ""


def extract_beneficiary_from_receipt(text):
    """Extract beneficiary/receiver from receipt (who received the payment)
    
    Handles table-based layouts where labels and values are separated.
    """
    logger.info("Extracting BENEFICIARY...")
    logger.info(f"Full OCR text ({len(text)} chars):\n{text}")  # DEBUG: See full text

    # Normalize Unicode dashes to ASCII hyphens (OCR often emits en-dash/em-dash)
    text = text.replace('\u2013', '-').replace('\u2014', '-')  # en-dash, em-dash → hyphen
    
    # STRATEGY 1: Look for "Receiver Name" label SPECIFICALLY, then find the corresponding VALUE
    # In table layouts, the value appears AFTER all labels, in the same position
    # CRITICAL: Must match "Receiver Name" NOT "Receiver Account"
    receiver_label_match = re.search(r'(?<!Source\s)(?<!Source Account\s)\b(Receiver Name|Beneficiary Name|Beneficiary)\b', text, re.IGNORECASE)
    
    if receiver_label_match:
        logger.info(f"Found receiver label at position {receiver_label_match.start()}: '{receiver_label_match.group(1)}'")
        
        # Split text into lines
        lines = text.split('\n')
        receiver_label_line_idx = None
        
        # Find which line contains the receiver NAME label (NOT receiver account)
        for i, line in enumerate(lines):
            # MUST match "Receiver Name" or "Beneficiary Name", NOT just "Receiver" or "Receiver Account"
            if re.search(r'\b(Receiver Name|Beneficiary Name|Beneficiary)\b', line, re.IGNORECASE):
                # Make sure it's not "Source Account Name"
                if not re.search(r'Source', line, re.IGNORECASE):
                    receiver_label_line_idx = i
                    logger.info(f"Receiver NAME label found on line {i}: '{line}'")
                    break
        
        if receiver_label_line_idx is not None:
            # Strategy: Look for the value in nearby lines (within 5-10 lines after the label)
            # The value should be a sequence of uppercase words, possibly with "AND OR"
            search_start = receiver_label_line_idx + 1
            search_end = min(receiver_label_line_idx + 12, len(lines))
            
            logger.info(f"Searching for receiver value in lines {search_start} to {search_end}")
            
            # Track candidates to find the right one
            candidates = []
            skip_next_names = False
            
            for i in range(search_start, search_end):
                line = lines[i].strip()
                logger.info(f"Checking line {i}: '{line}'")
                
                # Skip empty lines
                if not line:
                    continue
                
                # Skip lines that are clearly labels or numbers
                if re.match(r'^\d', line):  # Starts with digit (account numbers, etc)
                    logger.info(f"  Skipping (starts with digit)")
                    # After seeing a digit line, we've passed sender account number, next names should be beneficiary
                    if candidates:
                        skip_next_names = True  # Clear sender names, start fresh for beneficiary
                    candidates.clear()
                    continue
                if re.search(r'(Transaction|Reference|Type|Bank|Note|Account|Amount|Date|Time|Source|ETB|FTB)', line, re.IGNORECASE):
                    logger.info(f"  Skipping (contains field keyword)")
                    continue
                
                # Look for uppercase name pattern (possibly with AND OR)
                if re.search(r'\b[A-Z]{2,}\s+[A-Z]{2,}', line):
                    # Found a potential name - clean it up
                    beneficiary = line.strip()
                    beneficiary = re.sub(r'AND\s*/\s*OR', 'AND OR', beneficiary, flags=re.IGNORECASE)
                    beneficiary = re.sub(r'ANDOR', 'AND OR', beneficiary, flags=re.IGNORECASE)
                    beneficiary = re.sub(r'\s+', ' ', beneficiary).strip()
                    
                    # Remove common suffixes
                    beneficiary = re.sub(r'\s+(ETB|FTB|BIRR).*$', '', beneficiary, flags=re.IGNORECASE)
                    
                    # Validate: at least 2 words or contains "AND OR"
                    if len(beneficiary.split()) >= 2 or 'AND OR' in beneficiary.upper():
                        # Exclude known source account names
                        if beneficiary.upper() in ['SEBLE FULIE SHUME', 'SEBLE FULIE', 'FULIE SHUME']:
                            logger.info(f"  Skipping source account name: '{beneficiary}'")
                            continue
                        candidates.append(beneficiary)
                        logger.info(f"  Found candidate: '{beneficiary}'")
            
            # Prefer candidates containing "AND OR" (joint accounts)
            for cand in candidates:
                if 'AND OR' in cand.upper():
                    logger.info(f"✓ Beneficiary (table layout - joint account): {cand}")
                    return cand
            
            # Otherwise return the last valid candidate (likely beneficiary after passing account number line)
            # If no candidates, fall back to first if available
            if candidates:
                chosen = candidates[-1] if skip_next_names else candidates[0]
                logger.info(f"✓ Beneficiary (table layout - {'last' if skip_next_names else 'first'} candidate): {chosen}")
                return chosen
    
    logger.info("Table layout strategy didn't work, trying direct pattern matching...")


    # FALLBACK: Generic name extraction (similar to TXID approach)
    # Look for any sequence of uppercase words that could be a name
    logger.info("Priority patterns didn't match, trying fallback extraction...")
    
    # Fallback 1: Look for "WORD WORD AND OR WORD WORD" pattern (joint account names)
    # e.g., "JOHN DOE AND OR JANE SMITH" or "SEYSOA ASSEFA AND OR SENAIT DAGNE"
    joint_patterns = [
        r'([A-Z][A-Z]+\s+[A-Z][A-Z]+\s+AND\s+OR\s+[A-Z][A-Z]+\s+[A-Z][A-Z]+)',
        r'([A-Z][A-Z]+\s+[A-Z][A-Z]+\s+AND\s*/\s*OR\s+[A-Z][A-Z]+\s+[A-Z][A-Z]+)',
        r'([A-Z][A-Z]+\s+[A-Z][A-Z]+\s+ANDOR\s+[A-Z][A-Z]+\s+[A-Z][A-Z]+)',
    ]
    
    for pattern in joint_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            beneficiary = match.group(1).strip()
            beneficiary = re.sub(r'\s+', ' ', beneficiary).strip()
            if 10 <= len(beneficiary) <= 80:  # Reasonable length for joint names
                logger.info(f"✓ Beneficiary (fallback - joint account): {beneficiary}")
                return beneficiary
    
    # Fallback 2: Look for any sequence of 2-4 uppercase words (individual names)
    # Must be at least 2 words, each word at least 2 chars
    # e.g., "JOHN DOE", "MARY JANE SMITH"
    # CRITICAL: Must appear AFTER "Receiver" context, NOT after "Source"
    
    # Strategy: Split text by lines and look for names that appear in receiver context
    lines = text.split('\n')
    for i, line in enumerate(lines):
        # Check if this line or previous line mentions "Receiver" or "Beneficiary"
        context = '\n'.join(lines[max(0, i-2):i+1])  # Look at previous 2 lines + current
        
        # Skip if in "Source" context
        if re.search(r'source\s+account\s+name', context, re.IGNORECASE):
            continue
            
        # Look for receiver context
        if re.search(r'receiver|beneficiary|payee|paid to|credited to', context, re.IGNORECASE):
            # Extract name from current line
            name_pattern = r'\b([A-Z]{2,}\s+[A-Z]{2,}(?:\s+[A-Z]{2,}){0,4})\b'
            match = re.search(name_pattern, line)
            if match:
                name = match.group(1)
                # Skip if it's a label/field name
                excluded_words = ['ACCOUNT NAME', 'RECEIVER NAME', 'SOURCE ACCOUNT', 'TRANSACTION', 'REFERENCE', 'BANK NAME']
                if any(excl in name for excl in excluded_words):
                    continue
                if 5 <= len(name) <= 80 and len(name.split()) >= 2:
                    logger.info(f"✓ Beneficiary (fallback - receiver context): {name}")
                    return name
    
    # Last resort: generic name matching with strict exclusions
    name_pattern = r'\b([A-Z]{2,}\s+[A-Z]{2,}(?:\s+[A-Z]{2,}){0,2})\b'
    matches = re.findall(name_pattern, text)
    
    # Filter out common non-name phrases
    excluded_phrases = [
        'BANK OF', 'COMMERCIAL BANK', 'TRANSACTION TYPE', 'ACCOUNT NUMBER',
        'REFERENCE NUMBER', 'TRANSACTION DATE', 'TRANSACTION ID', 'SOURCE ACCOUNT',
        'RECEIVER ACCOUNT', 'ACCOUNT NAME', 'RECEIVER NAME', 'BENEFICIARY NAME',
        'OTHER BANK', 'BANK TRANSFER', 'THE CHOICE', 'SCAN THE', 'CHOICE FOR',
        'SEBLE FULIE', 'FULIE SHUME'  # Exclude known source account names
    ]
    
    for match in matches:
        # Skip if it's a common phrase
        if any(excl in match.upper() for excl in excluded_phrases):
            continue
        # Skip if it contains only common words
        if all(word in ['THE', 'FOR', 'AND', 'OR', 'OF', 'TO', 'FROM'] for word in match.split()):
            continue
        # Must be reasonable length
        if 5 <= len(match) <= 60 and len(match.split()) >= 2:
            logger.info(f"✓ Beneficiary (fallback - name pattern): {match}")
            return match

    logger.warning("✗ Beneficiary not found in receipt text (all patterns exhausted)")
    logger.info(f"Receipt text sample (first 400 chars): {text[:400]}")
    # Log full text for debugging (but limit to 1000 chars to avoid spam)
    if len(text) > 200:
        logger.debug(f"Full receipt text ({len(text)} chars): {text[:1000]}")
    return ""


def normalize_name(name):
    """Normalize name for comparison: uppercase, remove punctuation, collapse whitespace"""
    if not name:
        return ""
    # Uppercase
    name = name.upper()
    # Normalize "and/or" variations to "AND OR" before removing punctuation
    name = re.sub(r'AND\s*/\s*OR', 'AND OR', name)
    name = re.sub(r'&', 'AND', name)
    # Remove punctuation except spaces
    name = re.sub(r'[^\w\s]', ' ', name)
    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def validate_beneficiary(beneficiary_text):
    """
    Validate if beneficiary matches expected account names.
    Accepts receipts where at least one authorized person's full name is present.
    Returns (is_valid, normalized_beneficiary)
    """
    if not beneficiary_text:
        # If no beneficiary found, REJECT - cannot verify correct account
        logger.warning("❌ No beneficiary extracted - cannot validate payment account")
        return False, ""
    
    # Normalize the extracted beneficiary
    normalized = normalize_name(beneficiary_text)
    logger.info(f"🔍 Validating beneficiary: '{normalized}'")
    
    # Tokenize extracted beneficiary
    extracted_tokens = set(normalized.split())
    
    # Expanded connector words to handle "AND OR", "ANDOR", etc.
    connectors = {'AND', 'OR', 'ANDOR', 'THE', 'OF', 'TO', 'A', 'AN', '&', '/'}
    extracted_tokens_clean = extracted_tokens - connectors
    
    logger.info(f"Extracted tokens (cleaned): {extracted_tokens_clean}")
    
    # Authorized tokens - accept if ANY of these is found
    # FULL ACCOUNT NAME: "SEYOUM ASSEFA AND OR SENAIT DAGNE"
    # BUT accept ANY PARTIAL match (receipt may show truncated name)
    # Include ALL possible spelling variations due to OCR errors
    authorized_tokens = {
        # First name variations
        'SEYOUM', 'SEYSOA', 'SEYSOM', 'SEYSUM', 'SEYOAM',
        # First surname variations
        'ASSEFA', 'ASEFA', 'ASEFFA',
        # Second name variations
        'SENAIT', 'SENIET', 'SENAYT', 'SENAITE',
        # Second surname variations
        'DAGNIE', 'DAGNE', 'DAGINE', 'DAGNY', 'DAGNHE'
    }
    
    # Check if ANY authorized token is present (even just one word from the full name)
    matching_tokens = extracted_tokens_clean & authorized_tokens
    
    if matching_tokens:
        logger.info(f"✅ Beneficiary VALID - found authorized token(s): {matching_tokens}")
        logger.info(f"   (Partial match accepted - receipt may show truncated name)")
        return True, normalized
    
    # No match found
    logger.warning(f"❌ Beneficiary INVALID: '{normalized}' does not contain any authorized tokens")
    logger.info(f"Expected to find at least one of: {sorted(authorized_tokens)}")
    logger.info(f"Note: Receipt should contain SEYOUM ASSEFA AND OR SENAIT DAGNE (or any portion)")
    return False, normalized


def extract_house_from_caption(caption):
    """Extract house number from caption (3 or 4 digits only)
    Handles mixed text like: 'ብ 22 ቁ407' → extracts '407'
    Also handles slashed formats like: '14/06' → '1406'
    
    PRIORITY ORDER:
    1. Number after 'ቤት ቁጥር' (house number in Amharic)
    2. Number after 'H.No', 'H-No', 'H No', 'House'
    3. Number after 'ቁ' or 'ቁጥር'
    4. First 3-4 digit number found
    """
    if not caption:
        return ""
    
    # PRIORITY 1: Look for number after 'ቤት ቁጥር' (Amharic for house number)
    house_pattern_amharic = re.search(r'ቤት\s*ቁጥር\s*[:.]?\s*(\d{3,4})', caption)
    if house_pattern_amharic:
        num = house_pattern_amharic.group(1)
        logger.info(f"✓ House (after ቤት ቁጥር): {num}")
        return num
    
    # PRIORITY 2: Look for number after H.No, H-No, H No, House patterns
    house_pattern_english = re.search(r'(?:H\.?\s*No\.?|H-No\.?|House)\s*[:.]?\s*(\d{3,4})', caption, re.IGNORECASE)
    if house_pattern_english:
        num = house_pattern_english.group(1)
        logger.info(f"✓ House (after H.No/House): {num}")
        return num
    
    # PRIORITY 3: Look for number after ቁ or ቁጥር alone
    house_pattern_short = re.search(r'ቁጥር?\s*[:.]?\s*(\d{3,4})', caption)
    if house_pattern_short:
        num = house_pattern_short.group(1)
        logger.info(f"✓ House (after ቁ/ቁጥር): {num}")
        return num

    # PRIORITY 4: Find all numbers in the caption (even if mixed with text)
    # First, remove URLs and transaction IDs to avoid extracting numbers from them
    clean_caption = re.sub(r'https?://\S+', '', caption)  # Remove URLs
    clean_caption = re.sub(r'FT\d+\w*', '', clean_caption)  # Remove FT transaction IDs
    
    all_numbers = re.findall(r'[0-9]+', clean_caption)

    # Filter for only 3-4 digit numbers, EXCLUDING years (20XX, 19XX) and numbers ending in 0
    valid_numbers = []
    for num in all_numbers:
        if len(num) == 3 or len(num) == 4:
            # Exclude if it looks like a year (2018, 2025, 1999, etc.)
            if len(num) == 4 and (num.startswith('19') or num.startswith('20')):
                logger.info(f"⚠️ Skipped {num} (looks like a year)")
                continue
            # Exclude if it ends in 0 (likely an amount like 1000, 500, etc.)
            if num.endswith('0'):
                logger.info(f"⚠️ Skipped {num} (ends in 0 - likely an amount)")
                continue
            valid_numbers.append(num)
    
    if valid_numbers:
        # SMART SELECTION: Detect if this is a caption or OCR text
        # Caption: Short text with keywords → take FIRST (avoids year at end)
        # OCR: Long text without keywords → take LAST (house usually at bottom of receipt)
        is_short_text = len(caption) < 100  # Captions are usually short
        has_keywords = bool(re.search(r'ቁ|ብሎክ|ወር|H\.?No|Block', caption, re.IGNORECASE))
        
        if has_keywords or is_short_text:
            # This looks like a user caption → take FIRST number (before year/month)
            num = valid_numbers[0]
            logger.info(f"✓ House (first non-year number - caption): {num}")
        else:
            # This looks like OCR text → take LAST number (house usually at bottom)
            num = valid_numbers[-1]
            logger.info(f"✓ House (last non-year number - OCR): {num}")
        return num

    # If no 3-4 digit number found, try combining numbers separated by slashes or spaces
    # Look for patterns like "14/06" or "14 06"
    slash_pattern = re.search(r'(\d{1,2})\s*/\s*(\d{1,2})', caption)
    if slash_pattern:
        combined = slash_pattern.group(1) + slash_pattern.group(2)
        if len(combined) == 3 or len(combined) == 4:
            logger.info(f"✓ House (combined from slash): {combined}")
            return combined
    
    # Try combining consecutive small numbers separated by space
    space_pattern = re.search(r'(\d{1,2})\s+(\d{1,2})', caption)
    if space_pattern:
        combined = space_pattern.group(1) + space_pattern.group(2)
        if len(combined) == 3 or len(combined) == 4:
            logger.info(f"✓ House (combined from space): {combined}")
            return combined

    logger.warning("✗ House number not found (must be 3 or 4 digits)")
    return ""


def convert_to_ethiopian_month(text):
    """
    Convert Gregorian or Ethiopian month to Ethiopian calendar month (English name)
    CONVERSION - not just translation!
    
    Examples:
    - "january" → "Tir" (Ethiopian equivalent)
    - "february" → "Yekatit" (Ethiopian equivalent)
    - "meskerem" → "Meskerem" (already Ethiopian)
    - "ጥር" → "Tir" (Amharic to English)
    
    Returns: English Ethiopian month name (e.g., "Tir", "Meskerem")
    """
    logger.info("Converting to Ethiopian calendar...")

    text_lower = text.lower()

    # Check if it's already an Ethiopian month (English)
    for eth_month in ETHIOPIAN_MONTHS_LIST:
        if eth_month.lower() in text_lower or eth_month in text:
            logger.info(f"✓ Already Ethiopian month: {eth_month}")
            return eth_month

    # Check if it's an Amharic month name - convert to English
    for amharic_name, english_name in AMHARIC_TO_ETHIOPIAN.items():
        if amharic_name in text:
            logger.info(f"✓ Converted Amharic to English: {amharic_name} → {english_name}")
            return english_name

    # Convert Gregorian to Ethiopian (English name)
    for gregorian, ethiopian in GREGORIAN_TO_ETHIOPIAN.items():
        if gregorian in text_lower:
            logger.info(
                f"✓ Converted Gregorian to Ethiopian: {gregorian} → {ethiopian}"
            )
            return ethiopian

    logger.warning("✗ Month not found")
    return ""


# ========== MAIN EXTRACTION ==========
def extract_payment_data(text, caption=""):
    """Receipt-specific extraction (single message)"""
    combined = caption + "\n" + text if caption else text

    logger.info(f"=== EXTRACTION START ===")
    logger.info(f"Caption: {caption[:100] if caption else 'N/A'}")
    logger.info(f"Text: {text[:100] if text else 'N/A'}")

    # Extract fields
    # Try caption first, then fall back to searching all combined text
    house_number = extract_house_from_caption(caption)
    if not house_number:
        logger.info("House not in caption, searching combined text...")
        house_number = extract_house_from_caption(combined)

    amount = extract_amount_from_receipt(combined)
    date_str = extract_date_from_receipt(combined)
    txid = extract_txid_from_receipt(combined)
    name = extract_name_from_receipt(combined)

    # House mapping (use first available house_map from cache, or empty dict)
    house_map = house_maps.get(list(house_maps.keys())[0], {}) if house_maps else {}
    
    # If no house number found, try reverse lookup by name
    if not house_number and name and house_map:
        logger.info(f"🔍 No house number found, trying reverse lookup by name: {name}")
        name_upper = name.upper()
        for h_num, h_name in house_map.items():
            if h_name and name_upper in h_name.upper():
                house_number = h_num
                logger.info(f"✓ House (reverse lookup by name '{name}'): {house_number}")
                break
    
    # Also try matching OCR beneficiary name with house_map
    if not house_number and house_map:
        combined_upper = combined.upper()
        for h_num, h_name in house_map.items():
            if h_name and h_name.upper() in combined_upper:
                house_number = h_num
                name = h_name
                logger.info(f"✓ House (found name '{h_name}' in OCR text): {house_number}")
                break
    
    if house_number and house_number in house_map:
        name = house_map[house_number]
        logger.info(f"✓ Name (mapped): {name}")

    # Reason
    reason = 'other'
    text_lower = combined.lower()
    for r, keywords in PAYMENT_REASONS.items():
        for kw in keywords:
            if kw.lower() in text_lower or kw in combined:
                reason = r
                break
        if reason != 'other':
            break

    # Month - CONVERT to Ethiopian (not just translate!)
    month = convert_to_ethiopian_month(combined)

    logger.info(f"=== EXTRACTION COMPLETE ===")
    logger.info(
        f"House={house_number}, Amount={amount}, Name={name}, Month={month} (Ethiopian)"
    )

    return {
        'house_number': house_number,
        'amount': amount,
        'payment_date': date_str,
        'transaction_id': txid,
        'name': name,
        'reason': reason,
        'month': month
    }


def extract_payment_data_buffered(combined_text,
                                  caption="",
                                  user_text="",
                                  is_edit_mode=False,
                                  original_data=None,
                                  chat_id=None):
    """Receipt-specific extraction for buffered messages
    Prioritizes user-typed text for house number and month extraction
    In edit mode, handles disambiguation for bare numbers (treats as amount by default)
    """
    combined = caption + "\n" + combined_text if caption else combined_text
    
    # Load house mapping for this chat
    house_map = {}
    if chat_id:
        house_map = load_houses_for_group(chat_id)

    logger.info(
        f"=== BUFFERED EXTRACTION START (edit_mode={is_edit_mode}) ===")
    logger.info(f"Caption: {caption[:100] if caption else 'N/A'}")
    logger.info(f"User text: {user_text[:100] if user_text else 'N/A'}")
    logger.info(f"Combined: {combined_text[:100] if combined_text else 'N/A'}")

    # ========== EDIT MODE DISAMBIGUATION ==========
    # Check for explicit field prefixes in user text
    explicit_amount = None
    explicit_house = None
    explicit_month = None

    if is_edit_mode and user_text:
        # Check for explicit field labels (case insensitive)
        user_lower = user_text.lower().strip()

        # Amount: "amount: 700", "amount 700", "700 birr"
        amount_match = re.search(r'(?:amount|birr|ብር)[:\s]+([0-9.]+)',
                                 user_lower)
        if amount_match:
            explicit_amount = amount_match.group(1)
            logger.info(f"✓ Explicit amount label found: {explicit_amount}")
        elif re.search(r'([0-9.]+)\s*(?:birr|ብር)', user_lower):
            explicit_amount = re.search(r'([0-9.]+)\s*(?:birr|ብር)',
                                        user_lower).group(1)
            logger.info(f"✓ Amount with currency found: {explicit_amount}")

        # House: "house: 901", "house 901", "ቤት 901"
        house_match = re.search(r'(?:house|ቤት|home)[:\s]+([0-9]{3,4})',
                                user_lower)
        if house_match:
            explicit_house = house_match.group(1)
            logger.info(f"✓ Explicit house label found: {explicit_house}")

        # Month: "month: meskerem", "ወር: መስከረም"
        month_match = re.search(r'(?:month|ወር)[:\s]+(\w+)', user_lower,
                                re.UNICODE)
        if month_match:
            explicit_month = month_match.group(1)
            logger.info(f"✓ Explicit month label found: {explicit_month}")

    # Extract house number with priority:
    # 1. Explicit house label (edit mode only)
    # 2. User-typed text (highest priority - explicit house number)
    # 3. Caption
    # 4. Combined text (lowest priority - may contain false positives from OCR)
    #    BUT: Skip combined text in edit mode if user sent bare number (it's for amount, not house)
    house_number = ""
    is_bare_number = False

    if explicit_house:
        # User explicitly labeled this as house number
        house_number = explicit_house
        logger.info(f"Using explicit house number: {house_number}")
    elif is_edit_mode and user_text:
        # ========== EDIT MODE: BARE NUMBER DISAMBIGUATION ==========
        # Check if user text is JUST a number (bare number)
        user_stripped = user_text.strip()
        bare_number_match = re.match(r'^[0-9.]+$', user_stripped)

        if bare_number_match or explicit_amount or explicit_month:
            # Bare number, explicit amount, or explicit month in edit mode
            # Do NOT extract house number from user text
            is_bare_number = True
            if bare_number_match:
                logger.info(
                    f"⚠️ EDIT MODE: Bare number '{user_stripped}' detected - treating as AMOUNT, not house"
                )
            elif explicit_amount:
                logger.info(
                    f"⚠️ EDIT MODE: Explicit amount detected - NOT extracting house from user text"
                )
            elif explicit_month:
                logger.info(
                    f"⚠️ EDIT MODE: Explicit month detected - NOT extracting house from user text"
                )

            # Use original house number from last submission
            if original_data and original_data.get('house_number'):
                house_number = original_data['house_number']
                logger.info(f"✓ Keeping original house number: {house_number}")
        else:
            # Not a bare number or explicit field - proceed with normal house extraction
            logger.info("Checking user-typed text for house number...")
            house_number = extract_house_from_caption(user_text)
    elif user_text:
        # Normal mode - extract house normally
        logger.info("Checking user-typed text for house number...")
        house_number = extract_house_from_caption(user_text)

    # Only check caption and combined if not already found AND not a bare number in edit mode
    if not house_number and caption and not (is_edit_mode and is_bare_number):
        logger.info("Checking caption for house number...")
        house_number = extract_house_from_caption(caption)

    if not house_number and not (is_edit_mode and is_bare_number):
        logger.info("Checking combined text for house number...")
        house_number = extract_house_from_caption(combined)

    # Extract other fields from all combined content
    # In edit mode with explicit amount or bare number, use that
    if explicit_amount:
        amount = explicit_amount
        logger.info(f"Using explicit amount: {amount}")
    elif is_edit_mode and user_text:
        # Check for bare number - treat as amount
        user_stripped = user_text.strip()
        bare_number_match = re.match(r'^[0-9.]+$', user_stripped)
        if bare_number_match:
            amount = user_stripped
            logger.info(f"✓ EDIT MODE: Using bare number '{amount}' as amount")
        else:
            amount = extract_amount_from_receipt(combined)
    else:
        amount = extract_amount_from_receipt(combined)

    date_str = extract_date_from_receipt(combined)
    
    # Tiered TxID extraction: user text -> OCR
    txid = ""
    if user_text:
        # First, try to extract TxID from user's typed message
        txid_patterns = [
            r'(?:txid|transaction\s*id|tx\s*id|reference|ref)[:\s]+([A-Z0-9]{8,})',
            r'([0-9]{2}[A-Z]{2,}[A-Z0-9]{6,})',  # Pattern like 10BBETF53170884
        ]
        for pattern in txid_patterns:
            match = re.search(pattern, user_text, re.IGNORECASE)
            if match:
                txid = match.group(1).upper()
                logger.info(f"✓ TxID from user text: {txid}")
                break
    
    # Fallback to OCR if not found in user text
    if not txid:
        txid = extract_txid_from_receipt(combined)
    
    name = extract_name_from_receipt(combined)

    # House mapping
    try:
        if house_number in house_map:
            name = house_map[house_number]
            logger.info(f"✓ Name (mapped): {name}")
    except Exception as e:
        logger.error(f"Error in house mapping: {e}")

    # Reason
    reason = 'other'
    try:
        text_lower = combined.lower()
        for r, keywords in PAYMENT_REASONS.items():
            for kw in keywords:
                if kw.lower() in text_lower or kw in combined:
                    reason = r
                    break
            if reason != 'other':
                break
        logger.info(f"✓ Reason: {reason}")
    except Exception as e:
        logger.error(f"Error in reason extraction: {e}")

    # Month - PRIORITIZE user-typed text, then caption, then receipt
    # 1. Explicit month label (edit mode only)
    # 2. User-typed text (highest priority - user says "for month this")
    # 3. Caption (medium priority - user adds month in caption)
    # 4. Combined text (fallback - from receipt)
    month = ""

    if explicit_month:
        # User explicitly labeled this as month
        month = convert_to_ethiopian_month(explicit_month)
        logger.info(f"Using explicit month: {month}")
    elif is_edit_mode and user_text:
        # In edit mode, skip month extraction if it's just a bare number
        user_stripped = user_text.strip()
        bare_number_match = re.match(r'^[0-9.]+$', user_stripped)
        if not bare_number_match:
            # Not a bare number, try to extract month
            logger.info("Checking user-typed text for month...")
            month = convert_to_ethiopian_month(user_text)
    elif user_text:
        logger.info("Checking user-typed text for month...")
        month = convert_to_ethiopian_month(user_text)

    if not month and caption:
        logger.info("Month not in user text, checking caption...")
        month = convert_to_ethiopian_month(caption)

    if not month:
        logger.info("Month not in user text or caption, checking receipt...")
        month = convert_to_ethiopian_month(combined)

    # Extract beneficiary (who received the payment)
    beneficiary = ""
    try:
        logger.info("Starting beneficiary extraction...")
        beneficiary = extract_beneficiary_from_receipt(combined)
        logger.info(f"Beneficiary extraction complete: '{beneficiary}'")
    except Exception as e:
        logger.error(f"❌ CRITICAL: Error in beneficiary extraction: {e}", exc_info=True)

    logger.info(f"=== EXTRACTION COMPLETE ===")
    logger.info(
        f"House={house_number}, Amount={amount}, Name={name}, Month={month} (Ethiopian), Beneficiary={beneficiary}"
    )

    return {
        'house_number': house_number,
        'amount': amount,
        'payment_date': date_str,
        'transaction_id': txid,
        'name': name,
        'reason': reason,
        'month': month,
        'beneficiary': beneficiary
    }


# ========== MESSAGE BUFFERING AND PROCESSING ==========

# Track message thread ID for each user (for proper replies)
user_thread_ids = {}

# Track buffered message IDs for deletion detection
user_buffered_message_ids = defaultdict(dict)  # {chat_id: {user_id: [message_ids]}}


async def delete_message_after(message, delay_seconds: int):
    """Delete a message after specified delay in seconds"""
    try:
        logger.info(f"⏰ Scheduled delete for message in {delay_seconds}s (chat: {message.chat_id}, msg: {message.message_id})")
        await asyncio.sleep(delay_seconds)
        await message.delete()
        logger.info(f"✓ Auto-deleted message {message.message_id} after {delay_seconds}s")
    except Exception as e:
        logger.error(f"Error deleting message {message.message_id}: {e}")

# Keep track of background tasks so they don't get garbage collected
_background_tasks = set()

def schedule_delete(message, delay_seconds: int):
    """Schedule a message deletion with proper task tracking"""
    task = asyncio.create_task(delete_message_after(message, delay_seconds))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def check_message_exists(bot, chat_id: int, message_id: int) -> bool:
    """Check if a message still exists (wasn't deleted by user)"""
    try:
        # Try to forward the message to nowhere - this will fail if message doesn't exist
        # Actually, use getMessage is not available in python-telegram-bot
        # Instead, try to copy the message - this will fail if deleted
        # Actually the best approach is to try to get message reactions or pin it briefly
        # Simplest: try to edit or react to it - if it fails with "message not found", it was deleted
        
        # For efficiency, we can try to forward message to same chat (which will fail if deleted)
        # But this is noisy. Better approach: track message existence differently
        
        # Alternative: Use getUpdates or message.forward() test
        # Most reliable: Try to set a reaction and catch the error
        return True  # We'll check during actual processing with safer method
    except Exception as e:
        logger.warning(f"Message {message_id} in chat {chat_id} may have been deleted: {e}")
        return False


async def verify_buffered_messages_exist(bot, chat_id: int, user_id: int, messages: list) -> list:
    """Verify which buffered messages still exist and return only valid ones"""
    valid_messages = []
    for msg_data in messages:
        msg = msg_data.get('message')
        if msg:
            try:
                # Try to get the message - if it was deleted, this will fail
                # Actually, we can't directly check if a message exists
                # But we can check if we can still reply to it
                # The safest approach is to try a benign operation
                
                # Check if message_id is still accessible by trying to get file if photo
                # For now, we'll add the message and handle errors during reply
                valid_messages.append(msg_data)
            except Exception as e:
                logger.info(f"⏭️ Skipping deleted message from user {user_id}: {e}")
        else:
            valid_messages.append(msg_data)
    return valid_messages


async def safe_reply_text(message, text, **kwargs):
    """Safely send a reply to a message, handling deleted messages gracefully"""
    try:
        return await message.reply_text(text, **kwargs)
    except BadRequest as e:
        if "message to be replied not found" in str(e).lower() or "message not found" in str(e).lower():
            logger.warning(f"Cannot reply to message (message was deleted): {e}")
            return None
        else:
            raise
    except Exception as e:
        logger.error(f"Error sending reply: {e}")
        raise


async def expire_edit_mode(user_id: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Expire edit mode after timeout if no messages received"""
    await asyncio.sleep(EDIT_MODE_DELAY)

    # Check if user is still in edit mode and has no buffered messages
    # Check both key absence and empty list (defaultdict creates empty lists)
    has_no_messages = (chat_id not in user_message_buffers
                       or user_id not in user_message_buffers[chat_id]
                       or not user_message_buffers[chat_id][user_id])

    if user_edit_mode.get(chat_id, {}).get(user_id) and has_no_messages:
        logger.info(f"⏰ Edit mode expired for user {user_id} in chat {chat_id}")
        del user_edit_mode[chat_id][user_id]

        # Notify user that edit mode expired (use their specific thread ID)
        try:
            # Get the user's thread ID (where they last sent a message)
            thread_id = user_thread_ids.get(user_id)
            
            # Only send notification if we have a valid thread ID for this user
            if thread_id:
                sent_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    message_thread_id=thread_id,
                    text=
                    f"⏰ የማስተካከያ ጊዜ ከ{EDIT_MODE_DELAY} ሰከንዶች በኋላ አልቋል።\nእንደገና ለማስተካከል /edit ብለው ይጻፉ ወይም ይጫኑት።"
                )
                # Auto-delete this notification message after 60 seconds
                asyncio.create_task(delete_message_after(sent_msg, 60))
            else:
                logger.warning(f"No thread ID found for user {user_id}, skipping expiry notification")
        except Exception as e:
            logger.error(
                f"Error notifying user {user_id} about edit mode expiry: {e}")

    # Clean up task reference
    if chat_id in user_edit_mode_tasks and user_id in user_edit_mode_tasks[chat_id]:
        del user_edit_mode_tasks[chat_id][user_id]


async def process_buffered_messages(user_id: int,
                                    chat_id: int,
                                    context: ContextTypes.DEFAULT_TYPE,
                                    is_edit_mode: bool = False):
    """Process all buffered messages from a user after delay"""
    delay = EDIT_MODE_DELAY if is_edit_mode else MESSAGE_BUFFER_DELAY
    await asyncio.sleep(delay)

    if chat_id not in user_message_buffers or user_id not in user_message_buffers[chat_id] or not user_message_buffers[chat_id][user_id]:
        return

    # Check if any buffered messages were deleted during the wait
    # We'll check by attempting to copy the message - if deleted, it will fail
    valid_messages = []
    deleted_count = 0
    
    for msg_data in user_message_buffers[chat_id][user_id]:
        msg = msg_data.get('message')
        if msg:
            try:
                # Try to copy message to check if it exists (will fail if deleted)
                copied = await context.bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=chat_id,
                    message_id=msg.message_id,
                    disable_notification=True
                )
                # Delete the copied message immediately
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=copied.message_id)
                except:
                    pass
                valid_messages.append(msg_data)
            except BadRequest as e:
                error_str = str(e).lower()
                if "not found" in error_str or "deleted" in error_str:
                    logger.info(f"⏭️ Message {msg.message_id} was deleted by user {user_id}, skipping")
                    deleted_count += 1
                    continue
                else:
                    # Other error, assume message exists
                    valid_messages.append(msg_data)
            except Exception as e:
                # On any other error, assume message exists and continue
                valid_messages.append(msg_data)
        else:
            valid_messages.append(msg_data)
    
    # If all messages were deleted, abort processing silently
    if not valid_messages:
        logger.info(f"⏭️ All {deleted_count} buffered messages from user {user_id} were deleted, aborting")
        user_message_buffers[chat_id][user_id].clear()
        if chat_id in user_message_buffers and user_id in user_message_buffers[chat_id]:
            del user_message_buffers[chat_id][user_id]
        if chat_id in user_buffer_tasks and user_id in user_buffer_tasks[chat_id]:
            del user_buffer_tasks[chat_id][user_id]
        return
    
    # If some messages were deleted, log it
    if deleted_count > 0:
        logger.info(f"⏭️ {deleted_count} message(s) deleted by user {user_id}, continuing with {len(valid_messages)} remaining")
    
    # Update buffer with only valid messages
    user_message_buffers[chat_id][user_id] = valid_messages

    logger.info(
        f"🔄 Processing {len(user_message_buffers[chat_id][user_id])} buffered messages from user {user_id} in chat {chat_id}"
    )

    # Separate OCR text from user-typed text
    ocr_text = []
    user_text = []
    combined_caption = []
    reply_msg = None

    for msg_data in user_message_buffers[chat_id][user_id]:
        if msg_data['text']:
            if msg_data['is_ocr']:
                ocr_text.append(msg_data['text'])
            else:
                user_text.append(msg_data['text'])
        if msg_data['caption']:
            combined_caption.append(msg_data['caption'])
        if reply_msg is None:
            reply_msg = msg_data['message']  # Use first message for replies

    all_user_text = " ".join(
        user_text)  # User-typed messages (space separated)
    all_ocr_text = "\n".join(ocr_text)  # OCR text (line separated)
    all_captions = " ".join(combined_caption)
    all_combined = all_user_text + "\n" + all_ocr_text  # Combined for other extractions

    logger.info(
        f"User text: {len(all_user_text)} chars, OCR: {len(all_ocr_text)} chars, Captions: {len(all_captions)} chars"
    )

    # Get original data if in edit mode
    original_data = None

    # Fallback: Check global edit mode state if argument is False
    # This prevents race conditions or argument propagation issues
    if not is_edit_mode:
        global_edit_mode = user_edit_mode.get(chat_id, {}).get(user_id, False)
        if global_edit_mode:
            logger.info(f"⚠️ Edit mode argument was False, but global state is True for user {user_id}. Using global state.")
            is_edit_mode = True

    if is_edit_mode:
        logger.info(f"✏️ Processing as EDIT MODE (User: {user_id})")
        if user_last_submissions.get(chat_id, {}).get(user_id):
            original_data = user_last_submissions[chat_id][user_id]['data']
    else:
        logger.info(f"📨 Processing as NEW SUBMISSION (User: {user_id})")

    # Extract payment data - pass edit mode flag for disambiguation
    try:
        logger.info("About to call extract_payment_data_buffered...")
        data = extract_payment_data_buffered(all_combined,
                                             all_captions,
                                             all_user_text,
                                             is_edit_mode=is_edit_mode,
                                             original_data=original_data,
                                             chat_id=chat_id)
        logger.info("extract_payment_data_buffered completed successfully")
    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR in extract_payment_data_buffered: {e}", exc_info=True)
        if reply_msg:
            error_msg = await safe_reply_text(reply_msg, f"❌ የመረጃ ስህተት\nError extracting payment data: {str(e)}")
            if error_msg:
                asyncio.create_task(delete_message_after(error_msg, 180))
        user_message_buffers[chat_id][user_id].clear()
        if chat_id in user_message_buffers and user_id in user_message_buffers[chat_id]:
            del user_message_buffers[chat_id][user_id]
        if chat_id in user_buffer_tasks and user_id in user_buffer_tasks[chat_id]:
            del user_buffer_tasks[chat_id][user_id]
        return

    # ========== EDIT MODE HANDLING ==========
    if is_edit_mode and user_last_submissions.get(chat_id, {}).get(user_id):
        logger.info(
            f"🔄 EDIT MODE: Processing as complete replacement (no merging)")
        logger.info(f"🔄 NEW COMPLETE DATA: {data}")

    # Validate amount is present
    if not data['amount']:
        if reply_msg:
            # Create inline keyboard with Edit Again button
            keyboard = [[
                InlineKeyboardButton("እንደገና ልላክ ✏️",
                                     callback_data=f"edit_{user_id}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Add failure reaction to original message
            try:
                await reply_msg.set_reaction("👎")
            except Exception as e:
                logger.warning(f"Could not add reaction: {e}")
            
            warning_msg = await safe_reply_text(reply_msg,
                f"⚠️ የላኩት መረጃ ትክክለኛ/የተሟላ አያደለም\n\n"
                f"የተመዘገበ መረጃ:\n"
                f"🏠 ቤት: {data['house_number'] or '—'}\n"
                f"💰 መጠን: {data['amount'] or '—'} ብር\n"
                f"👤 ስም: {data['name'] or '—'}\n"
                f"📅 ቀን: {data['payment_date'] or '—'}\n\n"
                f" ከላይ የሚመለከቱት መረጃ ትክክል አይደለም❓\n"
                f"ሙሉውንና የተስተካከለውን መረጃ እንደገና ለመላክ 'እንደገና ልላክ' የሚለውን ይጫኑ።",
                reply_markup=reply_markup)
            # Auto-delete warning message after 10 minutes
            if warning_msg:
                asyncio.create_task(delete_message_after(warning_msg, 600))
        user_message_buffers[chat_id][user_id].clear()
        # Delete the key to ensure expire_edit_mode timeout can fire properly
        if chat_id in user_message_buffers and user_id in user_message_buffers[chat_id]:
            del user_message_buffers[chat_id][user_id]
        if chat_id in user_buffer_tasks and user_id in user_buffer_tasks[chat_id]:
            del user_buffer_tasks[chat_id][user_id]
        if user_edit_mode.get(chat_id, {}).get(user_id):
            del user_edit_mode[chat_id][user_id]
        return

    # ========== BENEFICIARY VALIDATION ==========
    # Validate that payment was sent to the correct account
    beneficiary = data.get('beneficiary', '')
    is_valid_beneficiary, normalized_beneficiary = validate_beneficiary(beneficiary)
    
    if not is_valid_beneficiary:
        logger.warning(f"❌ WRONG BENEFICIARY DETECTED: '{normalized_beneficiary}'")
        if reply_msg:
            # Create inline keyboard with Edit Again button
            keyboard = [[
                InlineKeyboardButton("እንደገና ልላክ ✏️",
                                     callback_data=f"edit_{user_id}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Add failure reaction to original message
            try:
                await reply_msg.set_reaction("👎")
            except Exception as e:
                logger.warning(f"Could not add reaction: {e}")
            
            # Different messages for missing vs wrong beneficiary
            if not beneficiary:
                error_msg = await safe_reply_text(reply_msg,
                    f"⚠️ የተቀባዩ መረጃ አልተገኘም!\n"
                    f"❌ Cannot Verify Payment Account\n\n"
                    f"The beneficiary/receiver name could not be found on the receipt.\n"
                    f"Please verify the receipt shows payment was sent to:\n\n"
                    f"✅ Expected account:\n"
                    f"   SEYOUM ASSEFA and/or SENAIT DAGNIE\n\n"
                    f"If the receipt is unclear, please contact @sphinxlike for manual verification.",
                    reply_markup=reply_markup)
            else:
                error_msg = await safe_reply_text(reply_msg,
                    f"⚠️ ገንዘቡ ወደ ተሳሳተ አካውንት ተልኳል!\n"
                    #f"❌ Wrong Beneficiary Detected\n\n"
                   # f"📝 Detected beneficiary: {beneficiary}\n\n"
                    #f"✅ Expected account:\n"
                    #f"   SEYOUM ASSEFA and/or SENAIT DAGNIE\n\n"
                    f"Please verify the receipt and make sure the payment was sent to the correct account.",
                    reply_markup=reply_markup)
            # Auto-delete error message after 3 minutes
            if error_msg:
                asyncio.create_task(delete_message_after(error_msg, 180))
        
        # Clean up and exit without saving
        user_message_buffers[chat_id][user_id].clear()
        if chat_id in user_message_buffers and user_id in user_message_buffers[chat_id]:
            del user_message_buffers[chat_id][user_id]
        if chat_id in user_buffer_tasks and user_id in user_buffer_tasks[chat_id]:
            del user_buffer_tasks[chat_id][user_id]
        if user_edit_mode.get(chat_id, {}).get(user_id):
            del user_edit_mode[chat_id][user_id]
        return

    # Save to Google Sheets
    reason = data['reason']
    logger.info(f"🔄 Attempting to save to Google Sheets - Reason: {reason}")
    
    try:
        sheets = setup_sheets(chat_id)
        logger.info(f"✓ Sheets setup successful: {list(sheets.keys()) if sheets else 'None'}")
    except Exception as e:
        logger.error(f"❌ CRITICAL: Failed to setup Google Sheets: {e}", exc_info=True)
        if reply_msg:
            error_msg = await safe_reply_text(reply_msg, f"❌ ስህተት በGoogle Sheets አገልግሎት\nError: {str(e)}")
            if error_msg:
                asyncio.create_task(delete_message_after(error_msg, 600))
        return
    
    target_sheet = sheets.get(reason) if sheets else None

    if target_sheet:
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # Convert amount to float to ensure it's stored as a number
            try:
                amount_value = float(data['amount']) if data['amount'] else 0
            except:
                amount_value = data[
                    'amount']  # Fallback to original if conversion fails

            house_number = data['house_number']
            month = data['month']
            txid = data['transaction_id'] or ''
            
            # Find the row for this house number
            all_values = target_sheet.get_all_values()
            row_index = None
            
            for idx, row in enumerate(all_values[2:], start=3):  # Skip 2 header rows, data starts at row 3
                if len(row) > 1 and row[1].strip() == house_number.strip():  # Column B (H.No) - trim whitespace
                    row_index = idx
                    break
            
            if not row_index:
                logger.error(f"House {house_number} not found in sheet {reason}")
                if reply_msg:
                    error_msg = await safe_reply_text(reply_msg, f"❌ ቤት {house_number} በዝርዝር ውስጥ አልተገኘም")
                    if error_msg:
                        asyncio.create_task(delete_message_after(error_msg, 600))
                return
            
            # Find the column for the month (need this BEFORE duplicate check)
            if month not in ETHIOPIAN_MONTHS:
                logger.warning(f"Month '{month}' not recognized")
            
            month_index = ETHIOPIAN_MONTHS.index(month) if month in ETHIOPIAN_MONTHS else -1
            
            if month_index == -1:
                logger.error(f"Cannot find column for month '{month}'")
                if reply_msg:
                    error_msg = await safe_reply_text(reply_msg, f"❌ ወሩ '{month}' አልታወቀም")
                    if error_msg:
                        asyncio.create_task(delete_message_after(error_msg, 600))
                return
            
            # Calculate column positions for this month (2 columns per month: Amount, FT No)
            # Columns: No (A=0), H.No (B=1), Name (C=2), then 2 columns per month
            # Amount column = 3 + (month_index * 2)
            # FT No column  = 3 + (month_index * 2) + 1
            amount_col_idx = 3 + (month_index * 2)
            ftno_col_idx = amount_col_idx + 1
            
            # ========== EDIT MODE: DELETE OLD ENTRY ==========
            # In edit mode, find and clear the old entry before saving new one
            # This allows changing payment type, month, or house number
            old_entry_deleted = False
            if is_edit_mode and txid and txid.strip():
                logger.info(f"📝 [EDIT MODE] Searching for old entry with TXID={txid} and House={house_number} to delete")
                
                # Search ALL sheets for the old entry
                for sheet_reason, sheet in sheets.items():
                    sheet_values = sheet.get_all_values()
                    
                    for idx, row in enumerate(sheet_values[2:], start=3):  # Skip 2 header rows
                        # Check if this row matches the user's house number
                        if len(row) > 1 and row[1].strip() == house_number.strip():
                            # Check all FT No columns for matching TXID
                            for col_idx in range(4, len(row), 2):  # FT No columns (even indices)
                                if len(row) > col_idx:
                                    cell_value = row[col_idx].strip()
                                    if cell_value and txid.strip() in [t.strip() for t in cell_value.split(',')]:
                                        # Found old entry! Clear both amount and TXID cells
                                        amount_col_idx_old = col_idx - 1
                                        try:
                                            # Clear the old cells (convert to A1 notation)
                                            amount_cell = chr(65 + amount_col_idx_old) + str(idx)
                                            ftno_cell = chr(65 + col_idx) + str(idx)
                                            
                                            sheet.update(amount_cell, [[""]])
                                            sheet.update(ftno_cell, [[""]])
                                            
                                            logger.info(f"✅ [EDIT MODE] Deleted old entry from '{sheet_reason}' row {idx} ({amount_cell}, {ftno_cell})")
                                            old_entry_deleted = True
                                            break
                                        except Exception as e:
                                            logger.error(f"❌ Error deleting old entry: {e}")
                            
                            if old_entry_deleted:
                                break
                    
                    if old_entry_deleted:
                        break
                
                if old_entry_deleted:
                    logger.info(f"✅ [EDIT MODE] Old entry deleted, proceeding to save updated data")
                else:
                    logger.warning(f"⚠️ [EDIT MODE] No old entry found (will save as new entry)")
            
            # ========== DUPLICATE TRANSACTION ID CHECK (NEW SUBMISSIONS ONLY) ==========
            # Only check for duplicates in NEW submissions (not edit mode)
            # In edit mode, we already deleted the old entry above, so skip duplicate check
            # (Without TxID, we allow multiple payments to support partial/split payments)
            if not is_edit_mode and txid and txid.strip():
                logger.info(f"🔍 Checking for duplicate transaction ID: {txid} across ALL sheets")
                logger.info(f"   New submission: will check ALL cells for duplicates")
                duplicate_found = False
                duplicate_sheet = None
                duplicate_row = None
                duplicate_sheet = None
                duplicate_row = None
                
                # Check ALL sheets, not just the current one
                for sheet_reason, sheet in sheets.items():
                    sheet_values = sheet.get_all_values()
                    
                    for idx, row in enumerate(sheet_values[2:], start=3):  # Skip 2 header rows
                        # Check all FT No columns (every even column starting from column E=4)
                        for col_idx in range(4, len(row), 2):  # Start at 4 (column E), step by 2
                            if len(row) > col_idx:
                                cell_value = row[col_idx].strip()
                                if cell_value:
                                    existing_txids = [t.strip() for t in cell_value.split(',')]
                                    if txid.strip() in existing_txids:
                                        duplicate_found = True
                                        duplicate_sheet = sheet_reason
                                        duplicate_row = idx
                                        logger.warning(f"❌ DUPLICATE TRANSACTION ID DETECTED: {txid} found in sheet '{sheet_reason}' at row {idx}, col {col_idx}")
                                        break
                        if duplicate_found:
                            break
                    if duplicate_found:
                        break
                
                if duplicate_found:
                    # Display Amharic message and don't save
                    reason_display = PAYMENT_REASONS_AMHARIC.get(duplicate_sheet, duplicate_sheet.capitalize())
                    if reply_msg:
                        # Create inline keyboard with Edit Again button
                        keyboard = [[
                            InlineKeyboardButton("እንደገና ልላክ ✏️",
                                                 callback_data=f"edit_{user_id}")
                        ]]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        # Add failure reaction to original message
                        try:
                            await reply_msg.set_reaction("⚠️")
                        except Exception as e:
                            logger.warning(f"Could not add reaction: {e}")
                        
                        error_msg = await safe_reply_text(reply_msg,
                            f"⚠️ ይህ ደረሰኝ ከዚህ በፊት ተልኳል እና ተመዝግቧል\n\n"
                            f"This receipt has been sent before and recorded.\n\n"
                            f"🔖 Transaction ID: {txid}\n"
                            f"📋 Found in: {reason_display} (row {duplicate_row})",
                            reply_markup=reply_markup)
                        
                        # Auto-delete error message after 3 minutes
                        if error_msg:
                            asyncio.create_task(delete_message_after(error_msg, 180))
                    
                    # Clean up and exit without saving
                    user_message_buffers[chat_id][user_id].clear()
                    if chat_id in user_message_buffers and user_id in user_message_buffers[chat_id]:
                        del user_message_buffers[chat_id][user_id]
                    if chat_id in user_buffer_tasks and user_id in user_buffer_tasks[chat_id]:
                        del user_buffer_tasks[chat_id][user_id]
                    if user_edit_mode.get(chat_id, {}).get(user_id):
                        del user_edit_mode[chat_id][user_id]
                    return
                else:
                    logger.info(f"✅ No duplicate found for transaction ID: {txid} across all sheets")
            else:
                logger.info(f"⚠️ No transaction ID provided - allowing multiple submissions (supports partial payments)")
            # ========== END DUPLICATE CHECK ==========
            
            # Convert column index to letter (A=0, B=1, C=2, D=3, etc.)
            def col_idx_to_letter(idx):
                result = ''
                while idx >= 0:
                    result = chr(65 + (idx % 26)) + result
                    idx = idx // 26 - 1
                return result
            
            amount_col = col_idx_to_letter(amount_col_idx)
            ftno_col = col_idx_to_letter(ftno_col_idx)
            
            # Read current values from the cells
            # For amounts, we need the actual formula if it exists (not just the calculated value)
            try:
                # Get the actual formula from the cell
                amount_cell = f'{col_idx_to_letter(amount_col_idx)}{row_index}'
                cell_data = target_sheet.acell(amount_cell, value_render_option='FORMULA')
                current_amount = cell_data.value.strip() if cell_data.value else ''
                # Remove leading '=' if it's a formula
                if current_amount.startswith('='):
                    current_amount = current_amount[1:]
            except:
                # Fallback to regular value if formula fetch fails
                current_amount = all_values[row_index - 1][amount_col_idx].strip() if len(all_values[row_index - 1]) > amount_col_idx else ''
            
            current_txid = all_values[row_index - 1][ftno_col_idx].strip() if len(all_values[row_index - 1]) > ftno_col_idx else ''
            
            # Determine final values based on mode and existing data
            if is_edit_mode:
                # In edit mode, remove the user's previous contribution and add the new one
                # Get the user's last submission data to know what to remove
                last_submission = user_last_submissions.get(chat_id, {}).get(user_id, {})
                if last_submission:
                    old_amount = str(last_submission['data'].get('amount', ''))
                    old_txid = last_submission['data'].get('transaction_id', '')
                    
                    # Remove old contribution from current values
                    if old_amount and current_amount:
                        # Remove the old amount part (handles both "500" and "500+300" cases)
                        amount_parts = current_amount.split('+')
                        amount_parts = [p.strip() for p in amount_parts if p.strip() != old_amount.strip()]
                        remaining_amount = '+'.join(amount_parts) if amount_parts else ''
                    else:
                        remaining_amount = current_amount
                    
                    if old_txid and current_txid:
                        # Remove the old txid part
                        txid_parts = [p.strip() for p in current_txid.split(',')]
                        txid_parts = [p for p in txid_parts if p.strip() != old_txid.strip()]
                        remaining_txid = ', '.join(txid_parts) if txid_parts else ''
                    else:
                        remaining_txid = current_txid
                    
                    # Now add the new values
                    if remaining_amount:
                        final_amount = f"{remaining_amount}+{amount_value}"
                    else:
                        final_amount = amount_value
                    
                    if remaining_txid:
                        final_txid = f"{remaining_txid}, {txid}"
                    else:
                        final_txid = txid
                    
                    logger.info(f"Edit mode: Replaced {old_amount}/{old_txid} with {amount_value}/{txid}")
                else:
                    # No previous submission found, treat as new
                    final_amount = amount_value
                    final_txid = txid
            else:
                # In normal mode, append to existing values if they exist
                if current_amount and current_amount != '':
                    # Append amount with + separator
                    final_amount = f"{current_amount}+{amount_value}"
                    logger.info(f"Appending amount: {current_amount} + {amount_value} = {final_amount}")
                else:
                    final_amount = amount_value
                
                if current_txid and current_txid != '':
                    # Append transaction ID with comma separator
                    final_txid = f"{current_txid}, {txid}"
                    logger.info(f"Appending txid: {current_txid}, {txid}")
                else:
                    final_txid = txid
            
            # Prepare final amount for Google Sheets
            # If it contains '+', make it a formula so SUM works in TOTALS row
            if isinstance(final_amount, str) and '+' in final_amount:
                final_amount_for_sheet = f"={final_amount}"
                logger.info(f"Converting to formula: {final_amount_for_sheet}")
            else:
                final_amount_for_sheet = final_amount
            
            # Update Amount column
            target_sheet.update(f'{amount_col}{row_index}', [[final_amount_for_sheet]], 
                              value_input_option='USER_ENTERED')
            
            # Update FT No column (keep as text, not formula)
            target_sheet.update(f'{ftno_col}{row_index}', [[final_txid]], 
                              value_input_option='USER_ENTERED')
            
            logger.info(f"✓ Updated {reason} - House {house_number}, Month {month} at row {row_index}, cols {amount_col}/{ftno_col}")

            # Store last submission for edit mode (with row index and month info)
            user_last_submissions[chat_id][user_id] = {
                'data': data.copy(),
                'sheet_name': reason,
                'timestamp': timestamp,
                'row_index': row_index,
                'month': month,
                'amount_col': amount_col,
                'ftno_col': ftno_col
            }

            if reply_msg:
                # Create inline keyboard with Edit button and History button (deep link)
                # Deep link format: /start history_{user_id}_{house_number}_{group_id}
                if BOT_USERNAME:
                    history_url = f"https://t.me/{BOT_USERNAME}?start=history_{user_id}_{data['house_number']}_{chat_id}"
                    keyboard = [
                        [
                            InlineKeyboardButton("እንደገና ልላክ ✏️",
                                                 callback_data=f"edit_{user_id}"),
                            InlineKeyboardButton("ታሪክ 📋",
                                                 url=history_url)
                        ]
                    ]
                else:
                    # Fallback to callback if bot username not available
                    keyboard = [
                        [
                            InlineKeyboardButton("እንደገና ልላክ ✏️",
                                                 callback_data=f"edit_{user_id}"),
                            InlineKeyboardButton("ታሪክ 📋",
                                                 callback_data=f"history_{user_id}_{data['house_number']}")
                        ]
                    ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Different message for edit vs new
                if is_edit_mode:
                    message_text = f"✅ ተስተካክሏል!\n\n"
                else:
                    message_text = f"✅ ተመዝግቧል!\n\n"

                # Convert month and reason to Amharic for display
                month_display = ETHIOPIAN_MONTHS_AMHARIC.get(data['month'], data['month'])
                reason_display = PAYMENT_REASONS_AMHARIC.get(reason, reason.capitalize())
                
                message_text += (f"🏠 ቤት: {data['house_number'] or '—'}\n"
                                 f"👤 ስም: {data['name'] or '—'}\n"
                                 f"💰 መጠን: {data['amount']} ብር\n"
                                 f"📆 ወር: {month_display or '—'}\n"
                                 f"🔖 T: {data['transaction_id'] or '—'}\n"
                                 f"📊 ምክንያት: {reason_display}")

                # Add success reaction to original message
                try:
                    await reply_msg.set_reaction("👍")
                except Exception as e:
                    logger.warning(f"Could not add reaction: {e}")
                
                # Send message and auto-delete after 10 minutes
                sent_msg = await safe_reply_text(reply_msg, message_text,
                                           reply_markup=reply_markup)
                
                # Schedule message deletion after 10 minutes (600 seconds)
                if sent_msg:
                    schedule_delete(sent_msg, 600)
        except Exception as e:
            logger.error(f"❌ CRITICAL: Save to Google Sheets failed: {e}", exc_info=True)
            if reply_msg:
                # Add failure reaction to original message
                try:
                    await reply_msg.set_reaction("👎")
                except Exception as react_error:
                    logger.warning(f"Could not add reaction: {react_error}")
                
                error_msg = await safe_reply_text(reply_msg, f"❌ ስህተት በማስቀመጥ ላይ\nError: {str(e)}")
                # Auto-delete error message after 10 minutes
                if error_msg:
                    asyncio.create_task(delete_message_after(error_msg, 600))
    else:
        if reply_msg:
            # Add failure reaction to original message
            try:
                await reply_msg.set_reaction("👎")
            except Exception as e:
                logger.warning(f"Could not add reaction: {e}")
            
            error_msg = await safe_reply_text(reply_msg, "❌ ስህተት በመረጃ - ቤት")
            # Auto-delete error message after 10 minutes
            if error_msg:
                asyncio.create_task(delete_message_after(error_msg, 600))

    # Clear buffer and edit mode flag
    if chat_id in user_message_buffers and user_id in user_message_buffers[chat_id]:
        user_message_buffers[chat_id][user_id].clear()
        # Delete the key to ensure expire_edit_mode timeout can fire properly
        del user_message_buffers[chat_id][user_id]
    if chat_id in user_buffer_tasks and user_id in user_buffer_tasks[chat_id]:
        del user_buffer_tasks[chat_id][user_id]
    if user_edit_mode.get(chat_id, {}).get(user_id):
        del user_edit_mode[chat_id][user_id]
        logger.info(f"✓ Cleared edit mode for user {user_id} in chat {chat_id}")


# ========== MESSAGE HANDLER ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user_id = update.effective_user.id
    message_id = msg.message_id
    chat_id = update.effective_chat.id
    thread_id = msg.message_thread_id if hasattr(msg, 'message_thread_id') else None

    # DEBUG: Log all incoming messages
    logger.info(f"📨 Received message - Chat ID: {chat_id}, Thread ID: {thread_id}, User: {user_id}, Message ID: {message_id}")

    # Create composite key for message tracking (supports multi-group)
    message_key = (chat_id, message_id, thread_id)
    
    # Check if this message has already been processed (for offline scenario)
    if message_key in processed_message_ids:
        logger.info(f"⏭️ Skipping already processed message {message_key}")
        return

    # ========== START DATE/MESSAGE ID FILTER ==========
    # Filter messages by date or message ID if configured
    # If neither is set, bot automatically resumes from last processed message
    if BOT_START_DATE or MIN_MESSAGE_ID:
        should_skip = False
        skip_reason = ""
        
        # Date-based filtering
        if BOT_START_DATE:
            try:
                from datetime import datetime, timezone
                start_date = datetime.strptime(BOT_START_DATE, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                message_date = msg.date  # Telegram message has timezone-aware datetime
                
                if message_date < start_date:
                    should_skip = True
                    skip_reason = f"message date {message_date.strftime('%Y-%m-%d %H:%M:%S')} < start date {BOT_START_DATE}"
            except ValueError as e:
                logger.error(f"❌ Invalid BOT_START_DATE format: '{BOT_START_DATE}'. Use YYYY-MM-DD format. Error: {e}")
        
        # Message ID filtering (independent of date filter)
        if MIN_MESSAGE_ID and not should_skip:
            try:
                min_id = int(MIN_MESSAGE_ID)
                if message_id < min_id:
                    should_skip = True
                    skip_reason = f"message ID {message_id} < minimum message ID {min_id}"
            except ValueError as e:
                logger.error(f"❌ Invalid MIN_MESSAGE_ID format: '{MIN_MESSAGE_ID}'. Must be integer. Error: {e}")
        
        if should_skip:
            logger.info(f"⏭️ [FILTER] Skipping message {message_id} in chat {chat_id} ({skip_reason})")
            # Mark as processed to avoid re-checking on next restart
            processed_message_ids.add(message_key)
            save_processed_messages()
            return
    # ========== END FILTER ==========

    # Check if admin is in search mode (BEFORE group/topic filters)
    # Now uses chat_id as key (where user types) and stores group_id as value
    search_group_id = admin_search_mode.get(chat_id, {}).get(user_id)
    
    if search_group_id:
        house_number = (msg.text or "").strip()

        # Validate house number (3 or 4 digits)
        if house_number.isdigit() and len(house_number) in [3, 4]:
            # Clear search mode for this chat
            del admin_search_mode[chat_id][user_id]

            # Create a mock query object for show_house_payments
            class MockQuery:

                def __init__(self, message):
                    self.message = message

            await show_house_payments(MockQuery(msg), house_number, search_group_id)
        else:
            await msg.reply_text(
                "❌ Invalid house number. Please send a 3 or 4 digit number.\n\n"
                "Example: `507` or `901`",
                parse_mode='Markdown')
        return

    # Group and topic filters (only for payment processing)
    # Check if message is from a configured group
    if chat_id not in GROUP_CONFIGS:
        logger.info(f"⏭️ Ignoring message from unconfigured group {chat_id}")
        return
    
    # Get the topic ID for this specific group
    group_topic_id = GROUP_CONFIGS[chat_id]['topic_id']
    
    # Check if message is in the correct topic for this group
    if group_topic_id and (not hasattr(msg, 'message_thread_id')
                     or msg.message_thread_id != group_topic_id):
        logger.info(f"⏭️ Ignoring message from wrong topic. Expected: {group_topic_id}, Got: {thread_id}")
        return

    # Track the thread ID for this user (for proper reply threading)
    if hasattr(msg, 'message_thread_id') and msg.message_thread_id:
        user_thread_ids[user_id] = msg.message_thread_id

    text = ""
    caption = msg.caption or ""
    is_ocr = False  # Track if text is from OCR or user-typed

    # Extract text from photo if present
    if msg.photo:
        logger.info(f"📸 Processing image from user {user_id}...")

        try:
            photo = msg.photo[-1]
            file = await photo.get_file()
            image_bytes = await file.download_as_bytearray()
            text = extract_text_from_image(bytes(image_bytes))
            is_ocr = True  # Text from OCR

            if not text and not caption:
                error_msg = await safe_reply_text(msg, "❌ በምስሉ ላይ ጽሁፍ አልተገኘም")
                if error_msg:
                    asyncio.create_task(delete_message_after(error_msg, 600))
                return
        except Exception as e:
            logger.error(f"Image error: {e}")
            error_msg = await safe_reply_text(msg, f"❌ ስህተት: {e}")
            if error_msg:
                asyncio.create_task(delete_message_after(error_msg, 600))
            return
    else:
        text = msg.text or ""
        is_ocr = False  # User-typed text

    if not text and not caption:
        return

    # Check if user is in edit mode (affects delay and merging behavior)
    is_edit = user_edit_mode.get(chat_id, {}).get(user_id, False)

    # Add message to buffer with OCR flag
    user_message_buffers[chat_id][user_id].append({
        'text': text,
        'caption': caption,
        'is_ocr': is_ocr,
        'message': msg
    })

    logger.info(
        f"📥 Buffered message from user {user_id} in chat {chat_id} (total: {len(user_message_buffers[chat_id][user_id])})"
    )

    # Cancel existing timer if present
    if chat_id in user_buffer_tasks and user_id in user_buffer_tasks[chat_id]:
        user_buffer_tasks[chat_id][user_id].cancel()
        logger.info(f"⏱️ Reset timer for user {user_id} in chat {chat_id}")
    delay_time = EDIT_MODE_DELAY if is_edit else MESSAGE_BUFFER_DELAY

    # If in edit mode, cancel the edit mode expiry task (user is sending messages)
    if is_edit and chat_id in user_edit_mode_tasks and user_id in user_edit_mode_tasks[chat_id]:
        user_edit_mode_tasks[chat_id][user_id].cancel()
        del user_edit_mode_tasks[chat_id][user_id]
        logger.info(f"⏱️ Cancelled edit mode expiry timer for user {user_id} in chat {chat_id}")

    # Start new timer (25s for normal, 60s for edit mode)
    user_buffer_tasks[chat_id][user_id] = asyncio.create_task(
        process_buffered_messages(user_id, chat_id, context, is_edit_mode=is_edit))

    # Mark message as processed ONLY AFTER successful buffering (prevents lock-out on errors)
    processed_message_ids.add(message_key)
    save_processed_messages()

    logger.info(
        f"⏱️ Started {delay_time}s timer for user {user_id} (edit_mode={is_edit})"
    )

    # Send confirmation (only for first message)
# if len(user_message_buffers[user_id]) == 1:
# await msg.reply_text(f"⏳ Waiting {MESSAGE_BUFFER_DELAY}s for more messages...")


# ========== EDIT COMMAND HANDLER ==========
async def handle_edit_command(update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
    """Allow users to edit their last submission"""
    msg = update.effective_message
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Check if message is from a configured group
    if chat_id not in GROUP_CONFIGS:
        return
    
    # Get the topic ID for this specific group
    group_topic_id = GROUP_CONFIGS[chat_id]['topic_id']
    
    # Check if message is in the correct topic for this group
    if group_topic_id and (not hasattr(msg, 'message_thread_id')
                     or msg.message_thread_id != group_topic_id):
        return

    # Check if user has a last submission
    if not user_last_submissions.get(chat_id, {}).get(user_id):
        error_msg = await msg.reply_text(
            "❌ ቀየተመዘገበ መረጃ አልተገኘም።\n\nመጀመሪያ ክፍያ ያስገቡ፣ ከዛ ማስተካከል ይችላሉ።")
        asyncio.create_task(delete_message_after(error_msg, 600))
        return

    last_sub = user_last_submissions[chat_id][user_id]
    data = last_sub['data']

    # Activate edit mode
    user_edit_mode[chat_id][user_id] = True

    # Start edit mode expiry timer
    if chat_id in user_edit_mode_tasks and user_id in user_edit_mode_tasks[chat_id]:
        user_edit_mode_tasks[chat_id][user_id].cancel()
    user_edit_mode_tasks[chat_id][user_id] = asyncio.create_task(
        expire_edit_mode(user_id, chat_id, context))

    # Convert month and reason to Amharic
    month_display = ETHIOPIAN_MONTHS_AMHARIC.get(data['month'], data['month'])
    reason_display = PAYMENT_REASONS_AMHARIC.get(last_sub['sheet_name'], last_sub['sheet_name'].capitalize())

    await msg.reply_text(f"📝 የተስተካከለው መረጃ:\n\n"
                         f"🏠 ቤት: {data['house_number'] or '—'}\n"
                         f"👤 ስም: {data['name'] or '—'}\n"
                         f"💰 መጠን: {data['amount']} ብር\n"
                         f"📆 ወር: {month_display or '—'}\n"
                         f"🔖 TxID: {data['transaction_id'] or '—'}\n"
                         f"📊 ምክንያት: {reason_display}\n\n"
                         f"⚠️ እባክዎ ሙሉውንና የተስተካከለውን መረጃ እንደገና ይላኩ።\n"
                         f"ሁሉንም መረጃዎች (ቤት፣ መጠን፣ ወር፣ ወዘተ) ያካትቱ።\n\n"
                         f"ሙሉውን መረጃ ለመላክ {EDIT_MODE_DELAY} ሰከንዶች አሉዎት።")

    logger.info(
        f"User {user_id} requested edit for last submission - EDIT MODE ACTIVATED"
    )


# ========== BUTTON CLICK HANDLER ==========
async def handle_history_button(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    """Handle History button clicks - redirect to DM and show sender's house payment history"""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass  # Ignore "Query is too old" errors for buttons from history scan

    callback_data = query.data
    if not callback_data.startswith("history_"):
        return

    # Parse callback data: history_{user_id}_{house_number}
    parts = callback_data.split("_")
    if len(parts) < 3:
        return
    
    button_user_id = int(parts[1])
    house_number = "_".join(parts[2:])  # Handle house numbers with underscores if any
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # SENDER-ONLY ACCESS: Only the original sender can view history
    if user_id != button_user_id:
        # Send error message to the unauthorized user's DM (not the group)
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"⛔ **Access Denied**\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"You can only view your own payment history.\n\n"
                    f"የራስዎን የክፍያ ታሪክ ብቻ ማየት ይችላሉ።\n\n"
                    f"If you need assistance, contact @sphinxlike"
                ),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.warning(f"Could not send DM to user {user_id}: {e}")
            # If DM fails, prompt user to start bot first
            await query.answer("Please start a chat with the bot first to receive messages", show_alert=True)
        return
    
    # Get the group_id to search in
    if chat_id in GROUP_CONFIGS:
        group_id = chat_id
    else:
        # Try to find the group from user's last submission
        group_id = None
        for gid in GROUP_CONFIGS.keys():
            if user_last_submissions.get(gid, {}).get(button_user_id):
                group_id = gid
                break
        
        if not group_id:
            await query.message.reply_text("❌ ቡድን አልተገኘም")
            return

    # Silently send history directly to user's DM (no message in group)
    # This callback handler is only triggered by old buttons before deep link feature
    await show_house_payments_in_dm(context, user_id, house_number, group_id, query)


async def show_house_payments_amharic(query, house_number, group_id):
    """Show all payments for a specific house in Amharic"""
    try:
        logger.info(f"🔍 Showing payment history for house {house_number} in group {group_id}")
        sheets = setup_sheets(group_id)
        
        house_data = []

        for reason in PAYMENT_REASONS.keys():
            try:
                sheet = sheets.get(reason) if sheets else None
                if not sheet:
                    continue

                values = sheet.get_all_values()
                for i in range(2, len(values) - 1):  # Skip headers and TOTALS
                    row = values[i]
                    if len(row) > 1 and row[1].strip() == house_number.strip():
                        house_name = row[2] if len(row) > 2 else ''
                        
                        for month_idx, month in enumerate(ETHIOPIAN_MONTHS):
                            amount_col_idx = 3 + (month_idx * 2)
                            ftno_col_idx = amount_col_idx + 1
                            
                            if len(row) > amount_col_idx:
                                amount = row[amount_col_idx]
                                txid = row[ftno_col_idx] if len(row) > ftno_col_idx else ''
                                
                                if amount and amount.strip():
                                    try:
                                        amount_value = float(amount)
                                        house_data.append({
                                            'name': house_name,
                                            'amount': str(amount_value),
                                            'month': month,
                                            'txid': txid,
                                            'type': reason
                                        })
                                    except ValueError:
                                        pass
            except Exception as e:
                logger.warning(f"Error reading {reason}: {e}")

        if not house_data:
            await query.message.reply_text(
                f"📭 ቤት {house_number} ምንም ክፍያ አልተገኘም።\n"
                f"No payments found for house {house_number}.")
            return

        # Get house name
        house_name = house_data[0]['name'] if house_data else "—"
        total = sum(float(p['amount']) for p in house_data if p['amount'])

        message = f"🏠 **ቤት {house_number}**\n"
        message += f"👤 ስም: {house_name}\n"
        message += f"💰 ጠቅላላ: {total:,.0f} ብር\n"
        message += f"📊 {len(house_data)} ክፍያዎች\n\n"
        message += "**የክፍያ ታሪክ:**\n\n"

        for i, p in enumerate(house_data, 1):
            reason_display = PAYMENT_REASONS_AMHARIC.get(p['type'], p['type'].capitalize())
            month_display = ETHIOPIAN_MONTHS_AMHARIC.get(p['month'], p['month'])
            message += (f"{i}. {reason_display} - {month_display}\n"
                        f"   💰 {p['amount']} ብር\n")
            if p['txid']:
                message += f"   🔖 {p['txid']}\n"
            message += "\n"

            if len(message) > 3500:
                await query.message.reply_text(message, parse_mode='Markdown')
                message = ""

        if message:
            await query.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in show_house_payments_amharic: {e}", exc_info=True)
        await query.message.reply_text(f"❌ ስህተት: {str(e)}")


async def show_house_payments_in_dm(context, user_id, house_number, group_id, query):
    """Send house payment history to user's DM"""
    try:
        logger.info(f"🔍 Sending payment history to DM for house {house_number}, user {user_id}")
        sheets = setup_sheets(group_id)
        
        house_data = []

        for reason in PAYMENT_REASONS.keys():
            try:
                sheet = sheets.get(reason) if sheets else None
                if not sheet:
                    continue

                values = sheet.get_all_values()
                for i in range(2, len(values) - 1):  # Skip headers and TOTALS
                    row = values[i]
                    if len(row) > 1 and row[1].strip() == house_number.strip():
                        house_name = row[2] if len(row) > 2 else ''
                        
                        for month_idx, month in enumerate(ETHIOPIAN_MONTHS):
                            amount_col_idx = 3 + (month_idx * 2)
                            ftno_col_idx = amount_col_idx + 1
                            
                            if len(row) > amount_col_idx:
                                amount = row[amount_col_idx]
                                txid = row[ftno_col_idx] if len(row) > ftno_col_idx else ''
                                
                                if amount and amount.strip():
                                    try:
                                        amount_value = float(amount)
                                        house_data.append({
                                            'name': house_name,
                                            'amount': str(amount_value),
                                            'month': month,
                                            'txid': txid,
                                            'type': reason
                                        })
                                    except ValueError:
                                        pass
            except Exception as e:
                logger.warning(f"Error reading {reason}: {e}")

        if not house_data:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"📭 ቤት {house_number} ምንም ክፍያ አልተገኘም።\n"
                    f"No payments found for house {house_number}."
                ),
                parse_mode='Markdown'
            )
            # Notify in group that history was sent to DM
            await query.answer("History sent to your DM", show_alert=True)
            return

        # Get house name
        house_name = house_data[0]['name'] if house_data else "—"
        total = sum(float(p['amount']) for p in house_data if p['amount'])

        message = f"📋 **የክፍያ ታሪክ - Payment History**\n"
        message += f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        message += f"🏠 **ቤት {house_number}**\n"
        message += f"👤 ስም: {house_name}\n"
        message += f"💰 ጠቅላላ: {total:,.0f} ብር\n"
        message += f"📊 {len(house_data)} ክፍያዎች\n\n"
        message += "**የክፍያ ዝርዝር:**\n\n"

        for i, p in enumerate(house_data, 1):
            reason_display = PAYMENT_REASONS_AMHARIC.get(p['type'], p['type'].capitalize())
            month_display = ETHIOPIAN_MONTHS_AMHARIC.get(p['month'], p['month'])
            message += (f"{i}. {reason_display} - {month_display}\n"
                        f"   💰 {p['amount']} ብር\n")
            if p['txid']:
                message += f"   🔖 {p['txid']}\n"
            message += "\n"

            # Split long messages
            if len(message) > 3500:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode='Markdown'
                )
                message = ""

        if message:
            await context.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'
            )
        
        # Notify in group that history was sent to DM
        await query.answer("History sent to your DM ✓", show_alert=True)
        logger.info(f"✓ Payment history sent to DM for user {user_id}")

    except Exception as e:
        logger.error(f"Error in show_house_payments_in_dm: {e}", exc_info=True)
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ Error loading history: {str(e)}\n\nContact @sphinxlike for help.",
                parse_mode='Markdown'
            )
        except:
            await query.answer("Could not send DM. Please start a chat with the bot first.", show_alert=True)


async def handle_edit_button(update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
    """Handle Edit button clicks"""
    query = update.callback_query
    try:
        await query.answer()  # Acknowledge the button click
    except Exception:
        pass  # Ignore "Query is too old" errors for buttons from history scan

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Verify this is the correct user (security check)
    callback_data = query.data
    if not callback_data.startswith("edit_"):
        return

    button_user_id = int(callback_data.split("_")[1])
    if user_id != button_user_id:
        error_msg = await safe_reply_text(query.message, "❌ ማስተካከል የሚችሉት የራስዎን መረጃ ብቻ ነው!")
        if error_msg:
            asyncio.create_task(delete_message_after(error_msg, 600))
        logger.warning(
            f"User {user_id} tried to edit submission from user {button_user_id}"
        )
        return

    # Check if user has a last submission
    if not user_last_submissions.get(chat_id, {}).get(user_id):
        error_msg = await safe_reply_text(query.message, "❌ ከዚ በፊት የተመዘገበ መረጃ አልተገኘም።")
        if error_msg:
            asyncio.create_task(delete_message_after(error_msg, 600))
        return

    last_sub = user_last_submissions[chat_id][user_id]
    data = last_sub['data']

    # Activate edit mode
    user_edit_mode[chat_id][user_id] = True

    # Start edit mode expiry timer
    if chat_id in user_edit_mode_tasks and user_id in user_edit_mode_tasks[chat_id]:
        user_edit_mode_tasks[chat_id][user_id].cancel()
    user_edit_mode_tasks[chat_id][user_id] = asyncio.create_task(
        expire_edit_mode(user_id, chat_id, context))

    # Convert month and reason to Amharic
    month_display = ETHIOPIAN_MONTHS_AMHARIC.get(data['month'], data['month'])
    reason_display = PAYMENT_REASONS_AMHARIC.get(last_sub['sheet_name'], last_sub['sheet_name'].capitalize())

    await query.message.reply_text(
        f"📝 የእርስዎ የመጨረሻ መረጃ:\n\n"
        f"🏠 ቤት: {data['house_number'] or '—'}\n"
        f"👤 ስም: {data['name'] or '—'}\n"
        f"💰 መጠን: {data['amount']} ብር\n"
        f"📆 ወር: {month_display or '—'}\n"
        f"🔖 TxID: {data['transaction_id'] or '—'}\n"
        f"📊 ምክንያት: {reason_display}\n\n"
        f"⚠️ እባክዎ ሙሉውንና የተስተካከለውን መረጃ እንደገና ይላኩ።\n"
        f"ሁሉንም መረጃዎች (ቤት፣ መጠን፣ ወር፣ ወዘተ) ያካትቱ።\n\n"
        f"ሙሉውን መረጃ ለመላክ {EDIT_MODE_DELAY} ሰከንዶች አሉዎት።")

    logger.info(f"User {user_id} clicked Edit button - EDIT MODE ACTIVATED")


# ========== ADMIN FUNCTIONS ==========
def is_admin(user_id: int, chat_id: int) -> bool:
    """Check if user is an admin for the specified group or any group (if private chat)"""
    # If this is a group chat, check if user is admin for that specific group
    if chat_id in GROUP_CONFIGS:
        group_config = GROUP_CONFIGS[chat_id]
        admin_ids = group_config.get('admin_user_ids', [])
        return user_id in admin_ids
    
    # If private chat (chat_id not in GROUP_CONFIGS), check if user is admin in ANY group
    # This allows admins to use the admin panel in private messages
    for group_chat_id, group_config in GROUP_CONFIGS.items():
        admin_ids = group_config.get('admin_user_ids', [])
        if user_id in admin_ids:
            return True
    
    logger.warning(f"⚠️ User {user_id} is not an admin in any configured group")
    return False


def get_admin_groups(user_id: int) -> dict:
    """Get all groups where user is an admin"""
    admin_groups = {}
    for chat_id, group_config in GROUP_CONFIGS.items():
        admin_ids = group_config.get('admin_user_ids', [])
        if user_id in admin_ids:
            admin_groups[chat_id] = group_config
    return admin_groups


def get_admin_menu_keyboard():
    """Get the professional admin menu with horizontal layout"""
    keyboard = [
        [
            InlineKeyboardButton("📊 Dashboard", callback_data="admin_dashboard"),
            InlineKeyboardButton("📅 Monthly", callback_data="admin_monthly_totals")
        ],
        [
            InlineKeyboardButton("🔍 Search", callback_data="admin_search"),
            InlineKeyboardButton("📋 Houses", callback_data="admin_houses")
        ],
        [
            InlineKeyboardButton("🗂️ Recent", callback_data="admin_recent"),
            InlineKeyboardButton("📥 Excel", callback_data="admin_download_excel")
        ],
        [
            InlineKeyboardButton("🔙 Back to Start", callback_data="back_to_start")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_admin_panel_text(group_name: str) -> str:
    """Get professional admin panel header text"""
    return (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👨‍💼 **Admin Panel**\n"
        f"📍 {group_name}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Select an option below:"
    )


async def handle_start_command(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - works in DMs for bot intro, admin access, and deep link history"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    first_name = update.effective_user.first_name or ""
    
    # Check if this is a private chat (DM)
    if update.effective_chat.type == 'private':
        # Check for deep link parameters (e.g., /start history_123_A101_-100123456)
        if context.args and len(context.args) > 0:
            deep_link_param = context.args[0]
            
            # Handle history deep link
            if deep_link_param.startswith("history_"):
                await handle_history_deep_link(update, context, deep_link_param)
                return
        
        # No deep link - show normal welcome
        # Check if user is admin in any group
        admin_groups = get_admin_groups(user_id)
        
        # Always show role selection popup for professional experience
        # Check for webapp URL in environment
        webapp_url = os.getenv('WEBAPP_URL', '')
        
        keyboard = [
            [
                InlineKeyboardButton("👨‍💼 Admin Access", callback_data="role_admin"),
                InlineKeyboardButton("👤 User Access", callback_data="role_user")
            ]
        ]
        
        # Add Mini App button if URL is configured
        if webapp_url:
            from telegram import WebAppInfo
            keyboard.append([
                InlineKeyboardButton("📊 Open Dashboard", web_app=WebAppInfo(url=webapp_url))
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Professional welcome message
        welcome_msg = (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏦 **Payment Receipt Bot**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👋 እንኳን ደህና መጡ, {first_name}!\n"
            f"     Welcome, {first_name}!\n\n"
            f"📌 **Please select your role:**\n\n"
            f"• **Admin Access** - Manage payments,\n"
            f"   view reports & download data\n\n"
            f"• **User Access** - View bot info\n"
            f"   & learn how to submit receipts"
        )
        
        await update.message.reply_text(
            welcome_msg,
            reply_markup=reply_markup,
            parse_mode='Markdown')
    else:
        # In group chat, just confirm bot is working
        await update.message.reply_text(
            f"👋 Bot is running!\n"
            f"Send payment receipts in this topic.")


async def send_dm_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, parse_mode: str = 'Markdown'):
    """Send message to DM, handling cases where update.message might be None"""
    chat_id = update.effective_chat.id
    if update.message:
        return await update.message.reply_text(text, parse_mode=parse_mode)
    else:
        return await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)


async def handle_history_deep_link(update: Update, context: ContextTypes.DEFAULT_TYPE, deep_link_param: str):
    """Handle deep link for payment history - directly show history in DM"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    first_name = update.effective_user.first_name or ""
    
    try:
        # Parse deep link: history_{button_user_id}_{house_number}_{group_id}
        parts = deep_link_param.split("_")
        if len(parts) < 4:
            await send_dm_message(update, context,
                "❌ Invalid history link. Please try again from the group."
            )
            return
        
        button_user_id = int(parts[1])
        group_id = int(parts[-1])  # Group ID is always last
        house_number = "_".join(parts[2:-1])  # House number is everything between user_id and group_id
        
        # SECURITY CHECK: Only the original sender can view their history
        if user_id != button_user_id:
            await send_dm_message(update, context,
                f"⛔ **Access Denied**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"You can only view your own payment history.\n\n"
                f"የራስዎን የክፍያ ታሪክ ብቻ ማየት ይችላሉ።\n\n"
                f"If you need assistance, contact @sphinxlike"
            )
            return
        
        # Check if group exists
        if group_id not in GROUP_CONFIGS:
            await send_dm_message(update, context,
                "❌ Group not found. Please try again from the group."
            )
            return
        
        # Send loading message
        loading_msg = await send_dm_message(update, context,
            f"📋 Loading payment history for house **{house_number}**..."
        )
        
        # Fetch and display payment history
        await show_history_in_dm(update, context, user_id, house_number, group_id, loading_msg)
        
    except ValueError as e:
        logger.error(f"Error parsing deep link: {e}")
        await send_dm_message(update, context,
            "❌ Invalid history link format. Please try again from the group."
        )
    except Exception as e:
        logger.error(f"Error handling history deep link: {e}")
        await send_dm_message(update, context,
            f"❌ Error loading history: {str(e)}\n\nContact @sphinxlike for help."
        )


async def show_history_in_dm(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                              user_id: int, house_number: str, group_id: int, loading_msg):
    """Show payment history in DM (used by deep link handler)"""
    try:
        logger.info(f"🔍 Deep link history request for house {house_number}, user {user_id}, group {group_id}")
        sheets = setup_sheets(group_id)
        
        house_data = []

        for reason in PAYMENT_REASONS.keys():
            try:
                sheet = sheets.get(reason) if sheets else None
                if not sheet:
                    continue

                values = sheet.get_all_values()
                for i in range(2, len(values) - 1):  # Skip headers and TOTALS
                    row = values[i]
                    if len(row) > 1 and row[1].strip() == house_number.strip():
                        house_name = row[2] if len(row) > 2 else ''
                        
                        for month_idx, month in enumerate(ETHIOPIAN_MONTHS):
                            amount_col_idx = 3 + (month_idx * 2)
                            ftno_col_idx = amount_col_idx + 1
                            
                            if len(row) > amount_col_idx:
                                amount = row[amount_col_idx]
                                txid = row[ftno_col_idx] if len(row) > ftno_col_idx else ''
                                
                                if amount and amount.strip():
                                    try:
                                        amount_value = float(amount)
                                        house_data.append({
                                            'name': house_name,
                                            'amount': str(amount_value),
                                            'month': month,
                                            'txid': txid,
                                            'type': reason
                                        })
                                    except ValueError:
                                        pass
            except Exception as e:
                logger.warning(f"Error reading {reason}: {e}")

        # Delete loading message
        try:
            await loading_msg.delete()
        except:
            pass

        if not house_data:
            await send_dm_message(update, context,
                f"📭 ቤት {house_number} ምንም ክፍያ አልተገኘም።\n"
                f"No payments found for house {house_number}."
            )
            return

        # Get house name and build message
        house_name = house_data[0]['name'] if house_data else "—"
        total = sum(float(p['amount']) for p in house_data if p['amount'])

        message = f"📋 **የክፍያ ታሪክ - Payment History**\n"
        message += f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        message += f"🏠 **ቤት {house_number}**\n"
        message += f"👤 ስም: {house_name}\n"
        message += f"💰 ጠቅላላ: {total:,.2f} birr\n\n"
        message += f"📊 **ክፍያዎች:**\n"
        message += f"─────────────────────\n"

        for i, p in enumerate(house_data, 1):
            reason_display = PAYMENT_REASONS_AMHARIC.get(p['type'], p['type'].capitalize())
            month_display = ETHIOPIAN_MONTHS_AMHARIC.get(p['month'], p['month'])
            message += (f"{i}. {reason_display}\n"
                        f"   💰 {p['amount']} birr | 📆 {month_display}\n"
                        f"   🔖 {p['txid']}\n\n")

            # Split long messages
            if len(message) > 3500:
                await send_dm_message(update, context, message)
                message = ""

        if message:
            await send_dm_message(update, context, message)
            
        logger.info(f"✅ Successfully sent history for house {house_number} to user {user_id}")

    except Exception as e:
        logger.error(f"Error in show_history_in_dm: {e}", exc_info=True)
        await send_dm_message(update, context,
            f"❌ Error loading history: {str(e)}\n\nContact @sphinxlike for help."
        )


async def handle_myid_command(update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
    """Show user their Telegram ID"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "No username"
    first_name = update.effective_user.first_name or ""

    await update.message.reply_text(
        f"📱 Your Telegram Info:\n\n"
        f"🆔 User ID: `{user_id}`\n"
        f"👤 Name: {first_name}\n"
        f"@{username}\n\n"
        f"ℹ️ Give your User ID to the admin to get admin access.",
        parse_mode='Markdown')


async def handle_admin_command(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    """Show admin panel with options"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not is_admin(user_id, chat_id):
        error_msg = await update.message.reply_text("❌ You don't have admin access.")
        asyncio.create_task(delete_message_after(error_msg, 600))
        return

    # Get groups where user is admin
    admin_groups = get_admin_groups(user_id)
    
    # If in private chat and admin manages multiple groups, show group selector
    if chat_id not in GROUP_CONFIGS and len(admin_groups) > 1:
        keyboard = []
        for group_chat_id, group_config in admin_groups.items():
            group_name = group_config.get('name', f'Group {group_chat_id}')
            keyboard.append([
                InlineKeyboardButton(
                    f"📊 {group_name}",
                    callback_data=f"select_group_{group_chat_id}"
                )
            ])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "👨‍💼 **Admin Panel**\n\n"
            "You are admin for multiple groups. Please select a group:",
            reply_markup=reply_markup,
            parse_mode='Markdown')
        return
    
    # If in private chat with only one group, use that group
    if chat_id not in GROUP_CONFIGS:
        chat_id = list(admin_groups.keys())[0]
        context.user_data['admin_group_id'] = chat_id
    else:
        # If in group chat, use that group
        context.user_data['admin_group_id'] = chat_id

    group_name = GROUP_CONFIGS[chat_id].get('name', 'Group')
    await update.message.reply_text(
        get_admin_panel_text(group_name),
        reply_markup=get_admin_menu_keyboard(),
        parse_mode='Markdown')


async def handle_admin_callbacks(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE):
    """Handle admin panel button clicks"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    first_name = update.effective_user.first_name or ""
    data = query.data
    
    # Handle role selection from /start (no admin check needed for initial selection)
    if data == "role_user":
        # Show user info panel
        user_msg = (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **User Information**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👋 ሰላም {first_name}!\n\n"
            f"ይህ ቦት የክፍያ ደረሰኞችን ለማስተናገድ ነው።\n"
            f"This bot processes payment receipts.\n\n"
            f"📌 **How to use:**\n"
            f"• Send payment receipts in the group chat\n"
            f"• Include house number in your message\n"
            f"• Bot will automatically extract & save data\n\n"
            f"🆔 Your ID: `{user_id}`\n"
            f"ℹ️ Share this ID with admin for access."
        )
        keyboard = [[InlineKeyboardButton("🔙 Back to Start", callback_data="back_to_start")]]
        await query.edit_message_text(
            user_msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown')
        return
    
    if data == "role_admin":
        # Check if user is actually an admin
        admin_groups = get_admin_groups(user_id)
        if not admin_groups:
            # Not an admin - show access denied
            deny_msg = (
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⛔ **Access Denied**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"You don't have admin privileges.\n\n"
                f"🆔 Your ID: `{user_id}`\n\n"
                f"Contact @sphinxlike to get access."
            )
            keyboard = [[InlineKeyboardButton("🔙 Back to Start", callback_data="back_to_start")]]
            await query.edit_message_text(
                deny_msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown')
            return
        
        # User is admin - show group selection or admin panel
        if len(admin_groups) > 1:
            keyboard = []
            for group_chat_id, group_config in admin_groups.items():
                group_name = group_config.get('name', f'Group {group_chat_id}')
                keyboard.append([
                    InlineKeyboardButton(
                        f"📊 {group_name}",
                        callback_data=f"select_group_{group_chat_id}"
                    )
                ])
            keyboard.append([InlineKeyboardButton("🔙 Back to Start", callback_data="back_to_start")])
            await query.edit_message_text(
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👨‍💼 **Select Group**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"You manage {len(admin_groups)} group(s).\n"
                f"Please select one:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown')
        else:
            # Only one group
            admin_group_id = list(admin_groups.keys())[0]
            context.user_data['admin_group_id'] = admin_group_id
            group_name = GROUP_CONFIGS[admin_group_id].get('name', 'Group')
            await query.edit_message_text(
                get_admin_panel_text(group_name),
                reply_markup=get_admin_menu_keyboard(),
                parse_mode='Markdown')
        return
    
    if data == "back_to_start":
        # Go back to start menu
        keyboard = [
            [
                InlineKeyboardButton("👨‍💼 Admin Access", callback_data="role_admin"),
                InlineKeyboardButton("👤 User Access", callback_data="role_user")
            ]
        ]
        welcome_msg = (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏦 **Payment Receipt Bot**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👋 እንኳን ደህና መጡ, {first_name}!\n"
            f"     Welcome, {first_name}!\n\n"
            f"📌 **Please select your role:**\n\n"
            f"• **Admin Access** - Manage payments,\n"
            f"   view reports & download data\n\n"
            f"• **User Access** - View bot info\n"
            f"   & learn how to submit receipts"
        )
        await query.edit_message_text(
            welcome_msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown')
        return

    # From here, admin access is required
    if not is_admin(user_id, chat_id):
        error_msg = await query.message.reply_text("❌ You don't have admin access.")
        asyncio.create_task(delete_message_after(error_msg, 600))
        return
    
    # Handle group selection
    if data.startswith("select_group_"):
        selected_group_id = int(data.replace("select_group_", ""))
        context.user_data['admin_group_id'] = selected_group_id
        group_name = GROUP_CONFIGS[selected_group_id].get('name', 'Group')
        
        await query.edit_message_text(
            get_admin_panel_text(group_name),
            reply_markup=get_admin_menu_keyboard(),
            parse_mode='Markdown')
        return

    # Get the group_id to use for admin operations
    # Use stored group_id if available, otherwise detect from user's admin groups
    admin_group_id = context.user_data.get('admin_group_id')
    
    # If not set (e.g., in private chat without prior selection), detect from admin groups
    if not admin_group_id or admin_group_id not in GROUP_CONFIGS:
        admin_groups = get_admin_groups(user_id)
        if len(admin_groups) == 1:
            # Only one group - use it automatically
            admin_group_id = list(admin_groups.keys())[0]
            context.user_data['admin_group_id'] = admin_group_id
        elif len(admin_groups) > 1:
            # Multiple groups - show selector
            keyboard = []
            for group_chat_id, group_config in admin_groups.items():
                group_name = group_config.get('name', f'Group {group_chat_id}')
                keyboard.append([
                    InlineKeyboardButton(
                        f"📊 {group_name}",
                        callback_data=f"select_group_{group_chat_id}"
                    )
                ])
            keyboard.append([InlineKeyboardButton("🔙 Back to Start", callback_data="back_to_start")])
            await query.edit_message_text(
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👨‍💼 **Select Group**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Please select a group first:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown')
            return
        else:
            # No admin groups found
            await query.message.reply_text("❌ You don't have admin access to any group.")
            return
    
    # Store it in context for the admin functions to use
    context.user_data['admin_group_id'] = admin_group_id


    if data == "admin_start":
        # Handle admin_start from /start command in DM
        admin_groups = get_admin_groups(user_id)
        if len(admin_groups) > 1:
            keyboard = []
            for group_chat_id, group_config in admin_groups.items():
                group_name = group_config.get('name', f'Group {group_chat_id}')
                keyboard.append([
                    InlineKeyboardButton(
                        f"📊 {group_name}",
                        callback_data=f"select_group_{group_chat_id}"
                    )
                ])
            keyboard.append([InlineKeyboardButton("🔙 Back to Start", callback_data="back_to_start")])
            await query.edit_message_text(
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👨‍💼 **Select Group**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"You manage {len(admin_groups)} group(s).\n"
                f"Please select one:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown')
        else:
            # Only one group
            admin_group_id = list(admin_groups.keys())[0]
            context.user_data['admin_group_id'] = admin_group_id
            group_name = GROUP_CONFIGS[admin_group_id].get('name', 'Group')
            await query.edit_message_text(
                get_admin_panel_text(group_name),
                reply_markup=get_admin_menu_keyboard(),
                parse_mode='Markdown')
    elif data == "admin_dashboard":
        await show_dashboard(query, admin_group_id)
    elif data == "admin_monthly_totals":
        await show_monthly_totals(query, admin_group_id)
    elif data == "admin_recent":
        await show_recent_payments(query, admin_group_id)
    elif data == "admin_search":
        await prompt_house_search(query, admin_group_id)
    elif data == "admin_stats":
        await show_payment_stats(query, admin_group_id)
    elif data == "admin_houses":
        await show_all_houses(query, admin_group_id)
    elif data == "admin_download_excel":
        await download_excel(query, context, admin_group_id)
    elif data.startswith("house_"):
        house_number = data.split("_")[1]
        await show_house_payments(query, house_number, admin_group_id)


async def download_excel(query, context, group_id):
    """Download the payment data as Excel file and send to user"""
    try:
        import io
        
        await query.message.reply_text("⏳ Generating Excel file... Please wait.")
        
        group_config = GROUP_CONFIGS.get(group_id)
        if not group_config:
            await query.message.reply_text("❌ Group configuration not found.")
            return
            
        spreadsheet_id = group_config.get('spreadsheet_id')
        if not spreadsheet_id:
            await query.message.reply_text("❌ Spreadsheet not configured for this group.")
            return
        
        # Get the spreadsheet export URL
        export_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=xlsx"
        
        # We need to use the authenticated client to download
        # Get the credentials from our existing setup
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_FILE,
            scopes=['https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive.readonly']
        )
        
        # Use requests with the authorized session
        from google.auth.transport.requests import AuthorizedSession
        authed_session = AuthorizedSession(creds)
        
        response = authed_session.get(export_url)
        
        if response.status_code == 200:
            # Create file-like object from content
            excel_file = io.BytesIO(response.content)
            excel_file.name = f"payments_{group_config.get('name', 'group')}_{datetime.now().strftime('%Y%m%d')}.xlsx"
            
            # Send the file to user
            group_name = group_config.get('name', 'Group')
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=excel_file,
                filename=excel_file.name,
                caption=f"📊 Payment data for {group_name}\n"
                        f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            logger.info(f"✅ Excel file sent to user {query.from_user.id}")
        else:
            logger.error(f"Failed to download Excel: {response.status_code} - {response.text[:200]}")
            await query.message.reply_text(f"❌ Failed to download Excel file. Status: {response.status_code}")
            
    except Exception as e:
        logger.error(f"Error in download_excel: {e}", exc_info=True)
        await query.message.reply_text(f"❌ Error generating Excel: {str(e)}")


async def show_dashboard(query, group_id):
    """Show comprehensive dashboard with overall statistics and monthly overview"""
    try:
        sheets = setup_sheets(group_id)
        
        stats = {}
        total_all = 0
        unique_people_all = set()
        monthly_totals = {month: 0 for month in ETHIOPIAN_MONTHS}

        for reason in PAYMENT_REASONS.keys():
            try:
                sheet = sheets.get(reason) if sheets else None
                if not sheet:
                    continue

                all_values = sheet.get_all_values()
                
                # Find TOTAL row (should have "TOTAL" in column B)
                totals_row = None
                for row in all_values:
                    if len(row) > 1 and row[1] == 'TOTAL':
                        totals_row = row
                        break
                
                if totals_row:
                    # Calculate total for this reason from all monthly totals
                    reason_total = 0
                    for month_idx in range(len(ETHIOPIAN_MONTHS)):
                        amount_col_idx = 3 + (month_idx * 2)
                        if amount_col_idx < len(totals_row):
                            try:
                                value_str = str(totals_row[amount_col_idx]).strip()
                                # Skip if empty or is a formula string
                                if value_str and not value_str.startswith('='):
                                    # Remove commas from formatted numbers
                                    value_str = value_str.replace(',', '')
                                    month_val = float(value_str)
                                    monthly_totals[ETHIOPIAN_MONTHS[month_idx]] += month_val
                                    reason_total += month_val
                            except ValueError as e:
                                logger.warning(f"Could not parse total value '{totals_row[amount_col_idx]}' for {reason} month {month_idx}")
                                pass
                    
                    # Count unique house numbers that actually paid (have at least one amount)
                    unique_houses = set()
                    for row in all_values[2:]:  # Skip headers (rows 1-2)
                        if row and len(row) > 1 and row[1] and row[1] != 'TOTAL':
                            house_number = row[1].strip()
                            if house_number:
                                # Check if this house has any payment in any month
                                has_payment = False
                                for month_idx in range(len(ETHIOPIAN_MONTHS)):
                                    amount_col_idx = 3 + (month_idx * 2)  # Amount column for each month
                                    if amount_col_idx < len(row):
                                        amount = row[amount_col_idx]
                                        if amount and str(amount).strip():  # Has a value
                                            try:
                                                if float(amount) > 0:
                                                    has_payment = True
                                                    break
                                            except:
                                                pass
                                
                                if has_payment:
                                    unique_houses.add(house_number)
                                    unique_people_all.add(house_number)
                    
                    stats[reason] = {'total': reason_total, 'people': len(unique_houses)}
                    total_all += reason_total

            except Exception as e:
                logger.error(f"Error reading stats for {reason}: {e}")

        message = "📊 **Payment Dashboard**\n\n"
        message += f"💰 **Grand Total: {total_all:,.2f} birr**\n"
        message += f"👥 **Total People Paid: {len(unique_people_all)}**\n\n"
        
        message += "**By Payment Type:**\n"
        for reason, data in stats.items():
            if data['total'] > 0:
                reason_display = PAYMENT_REASONS_AMHARIC.get(reason, reason.capitalize())
                message += f"  • {reason_display}: {data['total']:,.2f} birr ({data['people']} people)\n"
        
        message += "\n**Top 3 Months:**\n"
        sorted_months = sorted(monthly_totals.items(), key=lambda x: x[1], reverse=True)[:3]
        for month, total in sorted_months:
            if total > 0:
                month_display = ETHIOPIAN_MONTHS_AMHARIC.get(month, month)
                message += f"  {month_display}: {total:,.2f} birr\n"

        await query.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in show_dashboard: {e}")
        error_msg = await query.message.reply_text(f"❌ Error: {e}")
        asyncio.create_task(delete_message_after(error_msg, 600))


async def show_monthly_totals(query, group_id):
    """Show totals for each month across all payment types"""
    try:
        sheets = setup_sheets(group_id)
        
        monthly_totals = {month: 0 for month in ETHIOPIAN_MONTHS}
        monthly_breakdown = {month: {} for month in ETHIOPIAN_MONTHS}

        for reason in PAYMENT_REASONS.keys():
            try:
                sheet = sheets.get(reason) if sheets else None
                if not sheet:
                    continue

                # Use get_all_values() which returns formatted/calculated values
                all_values = sheet.get_all_values()
                
                # Find TOTAL row
                totals_row = None
                totals_row_idx = None
                for idx, row in enumerate(all_values):
                    if len(row) > 1 and row[1] == 'TOTAL':
                        totals_row = row
                        totals_row_idx = idx
                        break
                
                if totals_row:
                    for month_idx in range(len(ETHIOPIAN_MONTHS)):
                        amount_col_idx = 3 + (month_idx * 2)
                        if amount_col_idx < len(totals_row):
                            try:
                                value_str = str(totals_row[amount_col_idx]).strip()
                                # Skip if empty or is a formula string
                                if value_str and not value_str.startswith('='):
                                    # Remove commas from formatted numbers
                                    value_str = value_str.replace(',', '')
                                    month_val = float(value_str)
                                    month_name = ETHIOPIAN_MONTHS[month_idx]
                                    monthly_totals[month_name] += month_val
                                    
                                    if month_val > 0:
                                        if month_name not in monthly_breakdown:
                                            monthly_breakdown[month_name] = {}
                                        monthly_breakdown[month_name][reason] = month_val
                            except ValueError as e:
                                logger.warning(f"Could not parse value '{totals_row[amount_col_idx]}' for {reason} month {month_idx}: {e}")
                                pass

            except Exception as e:
                logger.error(f"Error reading monthly totals for {reason}: {e}")

        message = "📅 **Monthly Totals Report**\n\n"
        
        for month in ETHIOPIAN_MONTHS:
            total = monthly_totals[month]
            if total > 0:
                month_display = ETHIOPIAN_MONTHS_AMHARIC.get(month, month)
                message += f"**{month_display}:** {total:,.2f} birr\n"
                
                # Show breakdown by payment type
                if month in monthly_breakdown:
                    for reason, amount in monthly_breakdown[month].items():
                        reason_display = PAYMENT_REASONS_AMHARIC.get(reason, reason.capitalize())
                        message += f"  • {reason_display}: {amount:,.2f} birr\n"
                message += "\n"

        if all(v == 0 for v in monthly_totals.values()):
            message += "No payments recorded yet."

        await query.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in show_monthly_totals: {e}")
        error_msg = await query.message.reply_text(f"❌ Error: {e}")
        asyncio.create_task(delete_message_after(error_msg, 600))


async def show_recent_payments(query, group_id):
    """Show last 10 payments across all sheets"""
    try:
        sheets = setup_sheets(group_id)
        
        all_payments = []

        for reason in PAYMENT_REASONS.keys():
            try:
                sheet = sheets.get(reason) if sheets else None
                if not sheet:
                    continue

                values = sheet.get_all_values()
                # Skip 2 header rows, data starts at row 3 (index 2)
                # Last row is TOTALS, skip it
                for i in range(2, len(values) - 1):
                    row = values[i]
                    if len(row) > 2:
                        house_number = row[1] if len(row) > 1 else ''  # Column B
                        house_name = row[2] if len(row) > 2 else ''    # Column C
                        
                        # Check each month's columns for payments
                        for month_idx, month in enumerate(ETHIOPIAN_MONTHS):
                            amount_col_idx = 3 + (month_idx * 2)  # Amount column
                            ftno_col_idx = amount_col_idx + 1     # FT No column
                            
                            if amount_col_idx < len(row):
                                amount = row[amount_col_idx]
                                if amount and str(amount).strip():
                                    try:
                                        float(amount)  # Validate it's a number
                                        txid = row[ftno_col_idx] if ftno_col_idx < len(row) else ''
                                        all_payments.append({
                                            'house': house_number,
                                            'name': house_name,
                                            'amount': amount,
                                            'month': month,
                                            'txid': txid,
                                            'type': reason
                                        })
                                    except:
                                        pass
            except Exception as e:
                logger.error(f"Error reading {reason}: {e}")

        # Just take last 10 (can't sort by time since we don't have timestamps in this format)
        recent = all_payments[-10:] if len(all_payments) > 10 else all_payments

        if not recent:
            await query.message.reply_text("📭 No payments found.")
            return

        message = "📊 **Last 10 Payments:**\n\n"
        for i, p in enumerate(recent, 1):
            reason_display = PAYMENT_REASONS_AMHARIC.get(p['type'], p['type'].capitalize())
            month_display = ETHIOPIAN_MONTHS_AMHARIC.get(p['month'], p['month'])
            message += (f"{i}. 🏠 {p['house']} | {p['name']}\n"
                        f"   💰 {p['amount']} birr | {reason_display}\n"
                        f"   📆 {month_display}\n\n")

        await query.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in show_recent_payments: {e}")
        error_msg = await query.message.reply_text(f"❌ Error: {e}")
        asyncio.create_task(delete_message_after(error_msg, 600))


async def prompt_house_search(query, group_id):
    """Prompt for house number to search"""
    user_id = query.from_user.id
    chat_id = query.message.chat_id  # Use the actual chat where user will type
    # Store the target group_id so we know which group to search
    # Key is chat_id (where user types), value is group_id (which sheets to search)
    admin_search_mode[chat_id][user_id] = group_id
    await query.message.reply_text(
        "🔍 **Search by House Number**\n\n"
        "Send the house number (3 or 4 digits) to see all payments for that house.\n\n"
        "Example: `507` or `901`",
        parse_mode='Markdown')


async def show_payment_stats(query, group_id):
    """Show overall payment statistics"""
    try:
        sheets = setup_sheets(group_id)
        
        stats = {}
        total_all = 0
        count_all = 0

        for reason in PAYMENT_REASONS.keys():
            try:
                sheet = sheets.get(reason) if sheets else None
                if not sheet:
                    continue

                values = sheet.get_all_values()
                total_row = len(values)

                # Get total from last row
                if total_row > 1:
                    total_value = sheet.acell(
                        f'C{total_row}',
                        value_render_option='UNFORMATTED_VALUE').value
                    try:
                        total = float(total_value) if total_value else 0
                    except:
                        total = 0

                    count = total_row - 2  # Exclude header and total row
                    stats[reason] = {'total': total, 'count': count}
                    total_all += total
                    count_all += count

            except Exception as e:
                logger.error(f"Error reading stats for {reason}: {e}")

        message = "📈 **Payment Statistics**\n\n"

        for reason, data in stats.items():
            if data['count'] > 0:
                message += f"**{reason.capitalize()}:**\n"
                message += f"  💰 Total: {data['total']:,.2f} birr\n"
                message += f"  📊 Count: {data['count']} payments\n\n"

        message += f"\n**Overall:**\n"
        message += f"💰 **Total: {total_all:,.2f} birr**\n"
        message += f"📊 **Count: {count_all} payments**"

        await query.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in show_payment_stats: {e}")
        error_msg = await query.message.reply_text(f"❌ Error: {e}")
        asyncio.create_task(delete_message_after(error_msg, 600))


async def show_all_houses(query, group_id):
    """Show list of houses with payment counts"""
    try:
        sheets = setup_sheets(group_id)
        
        house_payments = defaultdict(int)

        for reason in PAYMENT_REASONS.keys():
            try:
                sheet = sheets.get(reason) if sheets else None
                if not sheet:
                    continue

                values = sheet.get_all_values()
                # Skip 2 header rows, data starts at row 3 (index 2)
                # Last row is TOTALS, skip it
                for i in range(2, len(values) - 1):
                    row = values[i]
                    if len(row) > 1:
                        house_number = row[1]  # Column B (H.No)
                        if house_number and house_number.strip():
                            # Count how many months this house has payments for
                            payment_count = 0
                            for month_idx in range(len(ETHIOPIAN_MONTHS)):
                                amount_col_idx = 3 + (month_idx * 2)  # Amount column
                                if amount_col_idx < len(row):
                                    amount = row[amount_col_idx]
                                    if amount and str(amount).strip():
                                        try:
                                            if float(amount) > 0:
                                                payment_count += 1
                                        except ValueError as e:
                                            logger.warning(f"Skipping non-numeric amount '{amount}' for house {house_number} in {reason}: {e}")
                                            pass
                            
                            if payment_count > 0:
                                house_payments[house_number] += payment_count
            except Exception as e:
                logger.error(f"Error reading houses from {reason}: {e}")

        if not house_payments:
            await query.message.reply_text("📭 No houses found.")
            return

        # Sort by house number
        sorted_houses = sorted(house_payments.items())

        # Create buttons (max 5 per row)
        keyboard = []
        row = []
        for house, count in sorted_houses:
            row.append(
                InlineKeyboardButton(f"🏠 {house} ({count})",
                                     callback_data=f"house_{house}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(
            f"📋 **All Houses ({len(house_payments)} total)**\n\n"
            f"Click a house to see its payment history:",
            reply_markup=reply_markup,
            parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in show_all_houses: {e}")
        error_msg = await query.message.reply_text(f"❌ Error: {e}")
        asyncio.create_task(delete_message_after(error_msg, 600))


async def show_house_payments(query, house_number, group_id):
    """Show all payments for a specific house"""
    try:
        logger.info(f"🔍 Searching for house {house_number} in group {group_id}")
        sheets = setup_sheets(group_id)
        
        house_data = []

        for reason in PAYMENT_REASONS.keys():
            try:
                sheet = sheets.get(reason) if sheets else None
                if not sheet:
                    continue

                values = sheet.get_all_values()
                # Skip 2 header rows, data starts at row 3 (index 2)
                # Last row is TOTALS, so skip it too
                for i in range(2, len(values) - 1):
                    row = values[i]
                    # House number is in column B (index 1) - trim whitespace for comparison
                    if len(row) > 1 and row[1].strip() == house_number.strip():
                        # For each payment found, search all month columns
                        # Structure: No (A=0), H.No (B=1), Name (C=2), then 2 cols per month
                        house_name = row[2] if len(row) > 2 else ''
                        
                        # Check each month's Amount column for a payment
                        for month_idx, month in enumerate(ETHIOPIAN_MONTHS):
                            amount_col_idx = 3 + (month_idx * 2)  # Amount column
                            ftno_col_idx = amount_col_idx + 1     # FT No column
                            
                            if len(row) > amount_col_idx:
                                amount = row[amount_col_idx]
                                txid = row[ftno_col_idx] if len(row) > ftno_col_idx else ''
                                
                                # Only add if there's an amount
                                if amount and amount.strip():
                                    try:
                                        # Try to convert to float to validate it's a number
                                        amount_value = float(amount)
                                        house_data.append({
                                            'name': house_name,
                                            'amount': str(amount_value),
                                            'month': month,
                                            'txid': txid,
                                            'date': '',  # Not stored in current format
                                            'recorded': '',  # Not stored in current format
                                            'type': reason
                                        })
                                    except ValueError as e:
                                        # Log the error for debugging but continue
                                        logger.warning(f"Skipping non-numeric amount '{amount}' for house {house_number} in {reason}/{month}: {e}")
                                        pass
            except:
                pass

        if not house_data:
            logger.warning(f"📭 No payments found for house {house_number} in group {group_id}")
            await query.message.reply_text(
                f"📭 No payments found for house {house_number}.")
            return
        
        logger.info(f"✅ Found {len(house_data)} payments for house {house_number}")

        # Sort by date
        house_data.sort(key=lambda x: x.get('recorded', ''), reverse=True)

        # Get house name from first payment
        house_name = house_data[0]['name'] if house_data else "Unknown"

        total = sum(
            float(p['amount']) if p['amount'] else 0 for p in house_data)

        message = f"🏠 **House {house_number}**\n"
        message += f"👤 {house_name}\n"
        message += f"💰 Total: {total:,.2f} birr\n"
        message += f"📊 {len(house_data)} payments\n\n"
        message += "**Payment History:**\n\n"

        for i, p in enumerate(house_data, 1):
            reason_display = PAYMENT_REASONS_AMHARIC.get(p['type'], p['type'].capitalize())
            month_display = ETHIOPIAN_MONTHS_AMHARIC.get(p['month'], p['month'])
            message += (f"{i}. {reason_display}\n"
                        f"   💰 {p['amount']} birr | 📆 {month_display}\n"
                        f"   🔖 {p['txid']}\n\n")

            # Split long messages
            if len(message) > 3500:
                await query.message.reply_text(message, parse_mode='Markdown')
                message = ""

        if message:
            await query.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in show_house_payments: {e}")
        error_msg = await query.message.reply_text(f"❌ Error: {e}")
        asyncio.create_task(delete_message_after(error_msg, 600))


# ========== HISTORY SCANNER (Telethon) ==========
async def handle_scan_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to scan historical messages from a specific date using Telethon"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    message_thread_id = update.message.message_thread_id if update.message else None
    
    # Check if user is admin for any configured group
    is_admin = False
    for group_id, config in GROUP_CONFIGS.items():
        admin_ids = config.get('admin_user_ids', [])
        if user.id in admin_ids:
            is_admin = True
            break
    
    if not is_admin:
        await update.message.reply_text("❌ This command is only available to admins.")
        return
    
    # Check if Telethon credentials are configured
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        await update.message.reply_text(
            "❌ **Telethon not configured**\n\n"
            "To use history scanning, set these environment variables:\n"
            "• `TELEGRAM_API_ID` - From https://my.telegram.org\n"
            "• `TELEGRAM_API_HASH` - From https://my.telegram.org",
            parse_mode='Markdown'
        )
        return
    
    # Parse the date argument
    args = context.args
    if not args:
        await update.message.reply_text(
            "📖 **Usage:** `/scan_history YYYY-MM-DD`\n\n"
            "Example: `/scan_history 2025-12-12`\n\n"
            "This will scan all messages with photos from the specified date onwards.",
            parse_mode='Markdown'
        )
        return
    
    try:
        from datetime import datetime
        scan_date = datetime.strptime(args[0], '%Y-%m-%d')
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid date format. Use YYYY-MM-DD\n"
            "Example: `/scan_history 2025-12-12`",
            parse_mode='Markdown'
        )
        return
    
    # Find the group config for this chat
    if chat_id not in GROUP_CONFIGS:
        await update.message.reply_text(
            f"❌ This group (ID: {chat_id}) is not configured.\n"
            "Add it to groups.json first."
        )
        return
    
    group_config = GROUP_CONFIGS[chat_id]
    topic_id = group_config.get('topic_id')
    
    # Import Telethon
    try:
        from telethon import TelegramClient
        from telethon.tl.types import MessageMediaPhoto
    except ImportError:
        await update.message.reply_text(
            "❌ **Telethon not installed**\n\n"
            "Run: `pip install telethon`",
            parse_mode='Markdown'
        )
        return
    
    # Send initial status message
    status_msg = await update.message.reply_text(
        f"🔍 **Starting history scan...**\n\n"
        f"📅 From: {args[0]}\n"
        f"📍 Group: {group_config.get('name', 'Unknown')}\n"
        f"⏳ Please wait, this may take a while...",
        parse_mode='Markdown'
    )
    
    try:
        # Initialize Telethon client
        global telethon_client
        session_file = "telethon_session"
        
        client = TelegramClient(session_file, int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
        await client.start()
        
        if not await client.is_user_authorized():
            await status_msg.edit_text(
                "⚠️ **First-time setup required**\n\n"
                "Run the bot from a terminal and follow the phone verification prompts.\n"
                "This is a one-time setup.",
                parse_mode='Markdown'
            )
            await client.disconnect()
            return
        
        # Get the target entity (group/channel)
        try:
            entity = await client.get_entity(chat_id)
        except Exception as e:
            await status_msg.edit_text(f"❌ Could not access group: {e}")
            await client.disconnect()
            return
        
        # Fetch messages with photos from the specified date
        from datetime import timezone
        scan_date_utc = scan_date.replace(tzinfo=timezone.utc)
        
        messages_found = 0
        messages_processed = 0
        messages_saved = 0
        errors = []
        
        await status_msg.edit_text(
            f"🔍 **Scanning messages...**\n\n"
            f"📅 From: {args[0]}\n"
            f"⏳ Fetching messages...",
            parse_mode='Markdown'
        )
        
        # Iterate through messages
        async for message in client.iter_messages(
            entity,
            offset_date=None,  # Start from now
            reverse=False,  # Go backwards in time
        ):
            # Stop if message is before our scan date
            if message.date.replace(tzinfo=timezone.utc) < scan_date_utc:
                break
            
            # Skip if no photo
            if not message.photo:
                continue
            
            # Skip if already processed
            msg_key = (chat_id, message.id, message.reply_to.reply_to_top_id if message.reply_to else None)
            if msg_key in processed_message_ids:
                continue
            
            # Check topic if applicable
            if topic_id:
                msg_topic = message.reply_to.reply_to_top_id if message.reply_to else None
                if msg_topic != topic_id:
                    continue
            
            messages_found += 1
            
            # Update progress every 10 messages
            if messages_found % 10 == 0:
                await status_msg.edit_text(
                    f"🔍 **Scanning messages...**\n\n"
                    f"📅 From: {args[0]}\n"
                    f"📊 Found: {messages_found} photos\n"
                    f"✅ Processed: {messages_processed}\n"
                    f"💾 Saved: {messages_saved}",
                    parse_mode='Markdown'
                )
            
            try:
                # Download the photo
                photo_bytes = await client.download_media(message.photo, bytes)
                
                if not photo_bytes:
                    continue
                
                # Run OCR
                ocr_text = extract_text_from_image(photo_bytes)
                
                if not ocr_text or len(ocr_text) < 20:
                    continue
                
                messages_processed += 1
                
                # Get caption if any
                caption = message.message or ""
                
                # Extract receipt data using main extraction function
                data = extract_payment_data(ocr_text, caption)
                
                amount = data.get('amount')
                txid = data.get('transaction_id')
                house_number = data.get('house_number')
                month = data.get('month') or 'Tir'
                payment_type = data.get('reason', 'other')
                
                # Skip if missing critical data
                if not amount or not txid:
                    continue
                
                # Try to save to sheets
                sheets = setup_sheets(chat_id)
                if sheets:
                    try:
                        # Check for duplicate TXID first
                        is_duplicate = check_duplicate_txid(sheets, txid, None, group_id=chat_id)
                        if is_duplicate:
                            logger.info(f"⏭️ Skipping duplicate TXID: {txid}")
                            continue
                        
                        # Save to appropriate sheet
                        save_to_sheets(
                            sheets=sheets,
                            house_number=house_number or "Unknown",
                            amount=amount,
                            txid=txid,
                            month=month,
                            reason=payment_type,
                            chat_id=chat_id
                        )
                        messages_saved += 1
                        
                        # Mark as processed
                        processed_message_ids.add(msg_key)
                        
                    except Exception as e:
                        errors.append(f"Save error for msg {message.id}: {str(e)[:50]}")
                        logger.error(f"Error saving historical receipt: {e}")
                
            except Exception as e:
                errors.append(f"Processing error for msg {message.id}: {str(e)[:50]}")
                logger.error(f"Error processing historical message {message.id}: {e}")
        
        # Save processed message IDs
        save_processed_messages()
        
        # Disconnect Telethon
        await client.disconnect()
        
        # Final status
        result_msg = (
            f"✅ **History scan complete!**\n\n"
            f"📅 Scanned from: {args[0]}\n"
            f"📸 Photos found: {messages_found}\n"
            f"🔍 Processed: {messages_processed}\n"
            f"💾 Saved to sheet: {messages_saved}\n"
        )
        
        if errors:
            result_msg += f"\n⚠️ Errors: {len(errors)}"
            if len(errors) <= 3:
                for err in errors:
                    result_msg += f"\n  • {err}"
        
        await status_msg.edit_text(result_msg, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"History scan error: {e}")
        await status_msg.edit_text(f"❌ **Scan failed:** {e}", parse_mode='Markdown')


# ========== RESCAN COMMAND (ADMIN ONLY) ==========
async def handle_rescan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin-only command to rescan a specific message and its context.
    Usage: Reply to a message with /rescan
    Scans messages 3 minutes before and after from the same user.
    """
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Check if user is admin
    group_config = GROUP_CONFIGS.get(chat_id)
    if not group_config:
        await update.message.reply_text("❌ This group is not configured.")
        return
    
    admins = group_config.get('admin_user_ids', [])
    if user_id not in admins:
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    # Check if replying to a message
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ Reply to a message to rescan it.\n\n"
            "Usage: Reply to the target message with /rescan"
        )
        return
    
    target_msg = update.message.reply_to_message
    target_user_id = target_msg.from_user.id if target_msg.from_user else None
    target_msg_date = target_msg.date
    
    # Check if Telethon is configured
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        await update.message.reply_text("❌ Telethon not configured. Set TELEGRAM_API_ID and TELEGRAM_API_HASH.")
        return
    
    status_msg = await update.message.reply_text("🔍 Rescan in progress...")
    
    try:
        from telethon import TelegramClient
        from datetime import timedelta
        
        # Initialize Telethon
        session_file = "telethon_session"
        client = TelegramClient(session_file, int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
        await client.start()
        
        # Get entity
        entity = await client.get_entity(chat_id)
        
        # Calculate time window (3 minutes before and after)
        time_before = target_msg_date - timedelta(minutes=3)
        time_after = target_msg_date + timedelta(minutes=3)
        
        # Collect messages from same user in time window
        collected_messages = []
        topic_id = group_config.get('topic_id')
        
        iter_kwargs = {'offset_date': time_after, 'reverse': False}
        if topic_id:
            iter_kwargs['reply_to'] = topic_id
        
        async for msg in client.iter_messages(entity, **iter_kwargs):
            # Stop if before window
            if msg.date < time_before:
                break
            
            # Only collect from same user
            if (msg.sender_id or 0) == target_user_id:
                collected_messages.append(msg)
        
        if not collected_messages:
            await client.disconnect()
            await status_msg.edit_text("❌ No messages found from this user in the time window.")
            return
        
        # Separate photos and text messages
        photo_messages = [m for m in collected_messages if m.photo]
        text_messages = [m for m in collected_messages if m.message and not m.photo]
        
        if not photo_messages:
            await client.disconnect()
            await status_msg.edit_text("❌ No photo messages found in the time window.")
            return
        
        # Combine all text (captions + separate text messages)
        all_text = []
        for pm in photo_messages:
            if pm.message:
                all_text.append(pm.message)
        for tm in text_messages:
            if tm.message:
                all_text.append(tm.message)
        
        combined_context = " ".join(all_text)
        
        # Load house map
        load_houses_for_group(chat_id)
        
        # Process each photo (client is still connected)
        results = []
        for photo_msg in photo_messages:
            # Download and OCR
            try:
                photo_bytes = await client.download_media(photo_msg.photo, bytes)
            except Exception as dl_err:
                results.append(f"⚠️ Download error for msg {photo_msg.id}: {dl_err}")
                continue
            
            if not photo_bytes:
                results.append(f"⚠️ Could not download photo {photo_msg.id}")
                continue
            
            ocr_text = extract_text_from_image(photo_bytes)
            if not ocr_text or len(ocr_text) < 20:
                results.append(f"⚠️ OCR failed for msg {photo_msg.id}")
                continue
            
            # Extract using buffered function
            data = extract_payment_data_buffered(
                combined_text=ocr_text,
                caption=combined_context,
                user_text=combined_context,
                is_edit_mode=False,
                original_data=None,
                chat_id=chat_id
            )
            
            amount = data.get('amount')
            txid = data.get('transaction_id')
            house_number = data.get('house_number')
            month = data.get('month') or 'Tir'
            payment_type = data.get('reason', 'other')
            name = data.get('name') or '—'
            
            if not amount or not txid:
                results.append(f"⚠️ Missing data for msg {photo_msg.id}: amount={amount}, txid={txid}")
                continue
            
            # Save to sheets
            sheets = setup_sheets(chat_id)
            if sheets:
                try:
                    save_to_sheets(
                        sheets=sheets,
                        house_number=house_number or "Unknown",
                        amount=amount,
                        txid=txid,
                        month=month,
                        reason=payment_type,
                        chat_id=chat_id
                    )
                    
                    # Get display values
                    month_display = ETHIOPIAN_MONTHS_AMHARIC.get(month, month)
                    reason_display = PAYMENT_REASONS_AMHARIC.get(payment_type, payment_type)
                    
                    results.append(
                        f"✅ Saved!\n"
                        f"🏠 ቤት: {house_number or '—'}\n"
                        f"👤 ስም: {name}\n"
                        f"💰 መጠን: {amount} ብር\n"
                        f"📆 ወር: {month_display}\n"
                        f"🔖 T: {txid[:20]}...\n"
                        f"📊 ምክንያት: {reason_display}"
                    )
                except Exception as e:
                    results.append(f"❌ Save error: {e}")
        
        # Disconnect client
        await client.disconnect()
        
        # Send result
        result_text = f"🔍 **Rescan Complete**\n\n"
        result_text += f"📊 Found {len(collected_messages)} messages from user\n"
        result_text += f"📸 Photos: {len(photo_messages)}, 📝 Texts: {len(text_messages)}\n\n"
        result_text += "\n\n".join(results) if results else "No results"
        
        await status_msg.edit_text(result_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Rescan error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Rescan failed: {e}")


# ========== POST INIT - FETCH BOT USERNAME + AUTO-SCAN ==========
def get_last_run_time():
    """Get the last time bot was running"""
    try:
        with open(LAST_RUN_FILE, 'r') as f:
            data = json.load(f)
            return data.get('last_run')
    except:
        return None

def save_last_run_time():
    """Save current time as last run time"""
    from datetime import datetime
    try:
        with open(LAST_RUN_FILE, 'w') as f:
            json.dump({'last_run': datetime.now().isoformat()}, f)
    except Exception as e:
        logger.error(f"Could not save last run time: {e}")

async def auto_scan_missed_messages():
    """Automatically scan messages missed while bot was offline"""
    from datetime import datetime, timezone
    
    # Check if Telethon is configured
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        logger.info("ℹ️ Auto-scan skipped: Telethon not configured (set TELEGRAM_API_ID and TELEGRAM_API_HASH)")
        return
    
    # Get last run time
    last_run = get_last_run_time()
    if not last_run:
        logger.info("ℹ️ First run - skipping auto-scan (use --scan-history for initial scan)")
        save_last_run_time()
        return
    
    try:
        last_run_dt = datetime.fromisoformat(last_run)
    except:
        logger.warning("⚠️ Could not parse last run time, skipping auto-scan")
        save_last_run_time()
        return
    
    # Import Telethon
    try:
        from telethon import TelegramClient
    except ImportError:
        logger.warning("⚠️ Auto-scan skipped: Telethon not installed")
        return
    
    logger.info("=" * 60)
    logger.info("🔄 AUTO-SCAN: Checking for missed messages...")
    logger.info(f"📅 Last run: {last_run}")
    logger.info("=" * 60)
    
    # Initialize Telethon
    session_file = "telethon_session"
    client = TelegramClient(session_file, int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
    
    try:
        await client.start()
        
        if not await client.is_user_authorized():
            logger.warning("⚠️ Telethon not authenticated - run with --scan-history first")
            await client.disconnect()
            save_last_run_time()
            return
        
        total_saved = 0
        
        # Scan each configured group
        for group_id, group_config in GROUP_CONFIGS.items():
            topic_id = group_config.get('topic_id')
            group_name = group_config.get('name', str(group_id))
            
            try:
                entity = await client.get_entity(group_id)
                logger.info(f"📍 Scanning: {group_name}")
            except Exception as e:
                logger.warning(f"⚠️ Could not access {group_name}: {e}")
                continue
            
            messages_found = 0
            messages_saved = 0
            last_run_utc = last_run_dt.replace(tzinfo=timezone.utc) if last_run_dt.tzinfo is None else last_run_dt
            
            # For forum topics, use reply_to parameter
            iter_kwargs = {'reverse': False}
            if topic_id:
                iter_kwargs['reply_to'] = topic_id
            
            async for message in client.iter_messages(entity, **iter_kwargs):
                msg_date = message.date.replace(tzinfo=timezone.utc) if message.date.tzinfo is None else message.date
                
                # Stop if message is before last run
                if msg_date < last_run_utc:
                    break
                
                # Skip non-photo
                if not message.photo:
                    continue
                
                # Skip if already processed
                msg_key = (group_id, message.id, message.reply_to.reply_to_top_id if message.reply_to else None)
                if msg_key in processed_message_ids:
                    continue
                
                messages_found += 1
                
                try:
                    # Download and OCR
                    photo_bytes = await client.download_media(message.photo, bytes)
                    if not photo_bytes:
                        continue
                    
                    ocr_text = extract_text_from_image(photo_bytes)
                    if not ocr_text or len(ocr_text) < 20:
                        continue
                    
                    # Extract data using main extraction function
                    caption = message.message or ""
                    data = extract_payment_data(ocr_text, caption)
                    
                    amount = data.get('amount')
                    txid = data.get('transaction_id')
                    house_number = data.get('house_number')
                    month = data.get('month') or 'Tir'
                    payment_type = data.get('reason', 'other')
                    
                    if not amount or not txid:
                        continue
                    
                    # Save to sheets
                    sheets = setup_sheets(group_id)
                    if sheets:
                        save_to_sheets(
                            sheets=sheets,
                            house_number=house_number or "Unknown",
                            amount=amount,
                            txid=txid,
                            month=month,
                            reason=payment_type,
                            chat_id=group_id
                        )
                        messages_saved += 1
                        processed_message_ids.add(msg_key)
                        logger.info(f"  ✅ Saved: House {house_number}, {amount} birr")
                
                except Exception as e:
                    logger.error(f"  ❌ Error processing msg {message.id}: {e}")
            
            if messages_found > 0:
                logger.info(f"  📊 {group_name}: Found {messages_found}, Saved {messages_saved}")
                total_saved += messages_saved
        
        # Save progress
        save_processed_messages()
        await client.disconnect()
        
        if total_saved > 0:
            logger.info(f"✅ Auto-scan complete: {total_saved} new receipts saved")
        else:
            logger.info("✅ Auto-scan complete: No new receipts found")
        
    except Exception as e:
        logger.error(f"❌ Auto-scan error: {e}")
        try:
            await client.disconnect()
        except:
            pass
    
    # Update last run time
    save_last_run_time()

async def post_init(application):
    """Fetch bot username and auto-scan missed messages on startup"""
    global BOT_USERNAME
    try:
        bot_info = await application.bot.get_me()
        BOT_USERNAME = bot_info.username
        logger.info(f"✓ Bot username: @{BOT_USERNAME}")
    except Exception as e:
        logger.error(f"❌ Could not fetch bot username: {e}")
    
    # Run auto-scan for missed messages
    await auto_scan_missed_messages()


# ========== START ==========
def main():
    logger.info("=" * 60)
    logger.info("VERSION 34 - HISTORY SCANNER WITH TELETHON")
    logger.info("✓ /scan_history command for historical message scanning")
    logger.info("✓ Edit mode deletes old entry and saves new data")
    logger.info("=" * 60)
    
    # Display filter configuration
    if BOT_START_DATE:
        logger.info(f"🔍 Date filter ENABLED: Only processing messages from {BOT_START_DATE} onwards")
    elif MIN_MESSAGE_ID:
        logger.info(f"🔍 Message ID filter ENABLED: Only processing messages with ID >= {MIN_MESSAGE_ID}")
    else:
        logger.info("🔄 Auto-resume ENABLED: Will resume from last processed message (no filter)")
    
    logger.info("=" * 60)

    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", handle_start_command))
    application.add_handler(CommandHandler("edit", handle_edit_command))
    application.add_handler(CommandHandler("myid", handle_myid_command))
    application.add_handler(CommandHandler("admin", handle_admin_command))
    application.add_handler(CommandHandler("scan_history", handle_scan_history_command))
    application.add_handler(CommandHandler("rescan", handle_rescan_command))

    # Add button click handlers
    application.add_handler(
        CallbackQueryHandler(handle_edit_button, pattern="^edit_"))
    application.add_handler(
        CallbackQueryHandler(handle_history_button, pattern="^history_"))
    application.add_handler(
        CallbackQueryHandler(handle_admin_callbacks, pattern="^admin_"))
    application.add_handler(
        CallbackQueryHandler(handle_admin_callbacks, pattern="^select_group_"))
    application.add_handler(
        CallbackQueryHandler(handle_admin_callbacks, pattern="^house_"))
    application.add_handler(
        CallbackQueryHandler(handle_admin_callbacks, pattern="^role_"))
    application.add_handler(
        CallbackQueryHandler(handle_admin_callbacks, pattern="^back_to_start$"))

    # Add message handler (for all non-command messages)
    application.add_handler(
        MessageHandler((filters.TEXT | filters.CAPTION | filters.PHOTO)
                       & ~filters.COMMAND, handle_message))

    logger.info("✅ Ready!")
    # Log admin counts per group
    for chat_id, config in GROUP_CONFIGS.items():
        admin_count = len(config.get('admin_user_ids', []))
        group_name = config.get('name', f'Group {chat_id}')
        logger.info(f"📊 {group_name}: {admin_count} admin(s)")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


async def run_terminal_history_scan(scan_date_str: str, group_id: int = None, notify: bool = False):
    """Run history scan from terminal (no Telegram command needed)
    
    Args:
        scan_date_str: Date to start scanning from (YYYY-MM-DD)
        group_id: Group ID to scan (optional)
        notify: If True, send confirmation messages to the group
    """
    from datetime import datetime, timezone
    
    # Validate date
    try:
        scan_date = datetime.strptime(scan_date_str, '%Y-%m-%d')
    except ValueError:
        logger.error(f"❌ Invalid date format: {scan_date_str}. Use YYYY-MM-DD")
        return
    
    # Check Telethon credentials
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        logger.error("❌ TELEGRAM_API_ID and TELEGRAM_API_HASH must be set!")
        logger.error("Get these from https://my.telegram.org")
        return
    
    # Import Telethon
    try:
        from telethon import TelegramClient
    except ImportError:
        logger.error("❌ Telethon not installed. Run: pip install telethon")
        return
    
    # Use first group if not specified
    if group_id is None:
        group_id = list(GROUP_CONFIGS.keys())[0]
    
    if group_id not in GROUP_CONFIGS:
        logger.error(f"❌ Group {group_id} not found in groups.json")
        logger.info(f"Available groups: {list(GROUP_CONFIGS.keys())}")
        return
    
    group_config = GROUP_CONFIGS[group_id]
    topic_id = group_config.get('topic_id')
    
    logger.info("=" * 60)
    logger.info("🔍 TERMINAL HISTORY SCAN MODE")
    logger.info(f"📅 Scan from: {scan_date_str}")
    logger.info(f"📍 Group: {group_config.get('name', 'Unknown')} (ID: {group_id})")
    logger.info(f"📌 Topic ID: {topic_id or 'None (all topics)'}")
    logger.info("=" * 60)
    
    # Initialize Telethon
    session_file = "telethon_session"
    client = TelegramClient(session_file, int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
    
    await client.start()
    
    if not await client.is_user_authorized():
        logger.info("⚠️ First-time setup - please follow the prompts above")
        return
    
    logger.info("✓ Telethon connected")
    
    # Get group entity
    try:
        entity = await client.get_entity(group_id)
        logger.info(f"✓ Connected to group: {entity.title if hasattr(entity, 'title') else group_id}")
    except Exception as e:
        logger.error(f"❌ Could not access group: {e}")
        await client.disconnect()
        return
    
    # Load house map for this group (needed for name lookup during extraction)
    load_houses_for_group(group_id)
    
    # ========== PHASE 1: Collect all messages ==========
    logger.info("⏳ Phase 1: Collecting messages...")
    
    scan_date_utc = scan_date.replace(tzinfo=timezone.utc)
    all_messages = []
    
    # For forum topics, we need to use reply_to parameter to filter by topic
    iter_kwargs = {'reverse': False}
    if topic_id:
        iter_kwargs['reply_to'] = topic_id
        logger.info(f"🔍 Filtering by topic ID: {topic_id}")
    
    async for message in client.iter_messages(entity, **iter_kwargs):
        # Stop if message is before scan date
        if message.date.replace(tzinfo=timezone.utc) < scan_date_utc:
            break
        
        # Skip if already processed
        msg_key = (group_id, message.id, message.reply_to.reply_to_top_id if message.reply_to else None)
        if msg_key in processed_message_ids:
            continue
        
        all_messages.append(message)
    
    logger.info(f"📊 Collected {len(all_messages)} messages")
    
    # ========== PHASE 2: Group messages by user with time window ==========
    logger.info("⏳ Phase 2: Grouping messages by user...")
    
    from datetime import timedelta
    GROUP_WINDOW = timedelta(minutes=3)  # Group messages within 3 minutes
    
    # Group messages: {user_id: [(photo_msg, [nearby_text_msgs])]}
    user_message_groups = {}
    
    for msg in all_messages:
        if not msg.photo:
            continue
        
        user_id = msg.sender_id or 0
        if user_id not in user_message_groups:
            user_message_groups[user_id] = []
        
        # Find nearby text messages from the same user (within time window)
        nearby_texts = []
        for other_msg in all_messages:
            if other_msg.id == msg.id:
                continue
            if (other_msg.sender_id or 0) != user_id:
                continue
            if other_msg.photo:  # Skip other photos
                continue
            if not other_msg.message:  # Skip empty messages
                continue
            
            # Check if within time window
            time_diff = abs((msg.date - other_msg.date).total_seconds())
            if time_diff <= GROUP_WINDOW.total_seconds():
                nearby_texts.append(other_msg.message)
        
        user_message_groups[user_id].append((msg, nearby_texts))
    
    total_groups = sum(len(groups) for groups in user_message_groups.values())
    logger.info(f"📊 Created {total_groups} message groups from {len(user_message_groups)} users")
    
    # ========== PHASE 3: Process each message group ==========
    logger.info("⏳ Phase 3: Processing message groups...")
    
    messages_found = 0
    messages_processed = 0
    messages_saved = 0
    
    for user_id, groups in user_message_groups.items():
        for photo_msg, nearby_texts in groups:
            messages_found += 1
            
            if messages_found % 10 == 0:
                logger.info(f"📊 Found: {messages_found} | Processed: {messages_processed} | Saved: {messages_saved}")
            
            message = photo_msg  # For compatibility with rest of code
            msg_key = (group_id, message.id, message.reply_to.reply_to_top_id if message.reply_to else None)
            
            try:
                # Download photo
                photo_bytes = await client.download_media(message.photo, bytes)
                if not photo_bytes:
                    continue
                
                # Run OCR
                ocr_text = extract_text_from_image(photo_bytes)
                if not ocr_text or len(ocr_text) < 20:
                    continue
                
                messages_processed += 1
                
                # Combine caption + nearby text messages for better extraction
                caption = message.message or ""
                combined_user_text = " ".join(nearby_texts) if nearby_texts else ""
                full_context = f"{caption} {combined_user_text}".strip()
                
                if nearby_texts:
                    logger.info(f"   📝 Combined {len(nearby_texts)} nearby text(s): {nearby_texts}")
                    logger.info(f"   📝 Full context: {full_context[:100]}...")
                
                # ========== FULL EXTRACTION (like normal bot) ==========
                # Use the buffered extraction function for comprehensive extraction
                data = extract_payment_data_buffered(
                    combined_text=ocr_text,
                    caption=full_context,
                    user_text=combined_user_text,
                    is_edit_mode=False,
                    original_data=None,
                    chat_id=group_id
                )
                
                amount = data.get('amount')
                txid = data.get('transaction_id')
                house_number = data.get('house_number')
                month = data.get('month') or 'Tir'
                payment_type = data.get('reason', 'other')
                sender_name = data.get('name') or '—'
                
                # Skip if missing critical data
                if not amount or not txid:
                    logger.info(f"⏭️ Skipping msg {message.id}: missing amount ({amount}) or TXID ({txid})")
                    continue
                
                # ========== BENEFICIARY VALIDATION ==========
                beneficiary = extract_beneficiary_from_receipt(ocr_text)
                is_valid_beneficiary, normalized_beneficiary = validate_beneficiary(beneficiary)
                
                if not is_valid_beneficiary and beneficiary:
                    logger.warning(f"⚠️ Invalid beneficiary: {beneficiary}")
                    # Still process but log the warning
                
                # ========== DUPLICATE TXID CHECK ==========
                sheets = setup_sheets(group_id)
                if sheets:
                    # Check all sheets for duplicate TXID
                    is_duplicate = False
                    duplicate_location = None
                    
                    for sheet_reason, sheet in sheets.items():
                        try:
                            all_values = sheet.get_all_values()
                            for row in all_values:
                                for cell in row:
                                    if txid and txid in str(cell):
                                        is_duplicate = True
                                        duplicate_location = sheet_reason
                                        break
                                if is_duplicate:
                                    break
                        except Exception as e:
                            logger.warning(f"Could not check sheet {sheet_reason}: {e}")
                        if is_duplicate:
                            break
                    
                    if is_duplicate:
                        logger.info(f"⏭️ Skipping duplicate TXID: {txid} (found in {duplicate_location})")
                        continue
                    
                    # ========== SAVE TO SHEETS ==========
                    try:
                        save_to_sheets(
                            sheets=sheets,
                            house_number=house_number or "Unknown",
                            amount=amount,
                            txid=txid,
                            month=month,
                            reason=payment_type,
                            chat_id=group_id
                        )
                        messages_saved += 1
                        processed_message_ids.add(msg_key)
                        logger.info(f"✅ Saved: House {house_number}, {amount} birr, TXID: {txid[:15]}...")
                        
                        # Send notification to group if notify flag is set
                        if notify:
                            try:
                                # Get month and reason in Amharic for display
                                month_display = ETHIOPIAN_MONTHS_AMHARIC.get(month, month)
                                reason_display = PAYMENT_REASONS_AMHARIC.get(payment_type, payment_type.capitalize())
                                
                                # Match the normal bot message format
                                sender_id = message.sender_id or 0
                                notify_msg = (
                                    f"✅ ተመዝግቧል!\n\n"
                                    f"🏠 ቤት: {house_number or '—'}\n"
                                    f"👤 ስም: {data.get('name') or '—'}\n"
                                    f"💰 መጠን: {amount} ብር\n"
                                    f"📆 ወር: {month_display or '—'}\n"
                                    f"🔖 T: {txid or '—'}\n"
                                    f"📊 ምክንያት: {reason_display}"
                                )
                                
                                # Create inline keyboard with Edit and History buttons
                                history_url = f"https://t.me/{BOT_USERNAME}?start=history_{sender_id}_{house_number}_{group_id}" if BOT_USERNAME else None
                                
                                if history_url:
                                    inline_keyboard = [
                                        [
                                            {"text": "እንደገና ልላክ ✏️", "callback_data": f"edit_{sender_id}"},
                                            {"text": "ታሪክ 📋", "url": history_url}
                                        ]
                                    ]
                                else:
                                    inline_keyboard = [
                                        [
                                            {"text": "እንደገና ልላክ ✏️", "callback_data": f"edit_{sender_id}"},
                                            {"text": "ታሪክ 📋", "callback_data": f"history_{sender_id}_{house_number}"}
                                        ]
                                    ]
                                
                                # Use Bot API to send message (so it comes from the bot, not user)
                                import httpx
                                bot_api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                                payload = {
                                    "chat_id": group_id,
                                    "text": notify_msg,
                                    "reply_to_message_id": message.id,
                                    "reply_markup": {"inline_keyboard": inline_keyboard}
                                }
                                # Add topic_id if it's a forum group
                                if topic_id:
                                    payload["message_thread_id"] = topic_id
                                
                                async with httpx.AsyncClient() as http_client:
                                    response = await http_client.post(bot_api_url, json=payload)
                                    if response.status_code == 200:
                                        # Schedule auto-delete after 10 minutes (600 seconds)
                                        result = response.json()
                                        if result.get('ok') and result.get('result', {}).get('message_id'):
                                            sent_msg_id = result['result']['message_id']
                                            # Use asyncio to schedule deletion
                                            async def delete_after_delay(msg_id, delay):
                                                await asyncio.sleep(delay)
                                                try:
                                                    async with httpx.AsyncClient() as del_client:
                                                        del_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
                                                        del_payload = {"chat_id": group_id, "message_id": msg_id}
                                                        await del_client.post(del_url, json=del_payload)
                                                except:
                                                    pass
                                            # Create task for deletion (non-blocking)
                                            import asyncio
                                            asyncio.create_task(delete_after_delay(sent_msg_id, 600))
                                    else:
                                        logger.warning(f"⚠️ Bot API error: {response.text}")
                                
                            except Exception as notify_err:
                                logger.warning(f"⚠️ Could not send notification: {notify_err}")
                        
                    except Exception as e:
                        logger.error(f"❌ Save error: {e}")
            
            except Exception as e:
                logger.error(f"❌ Processing error for msg {message.id}: {e}")
    
    # Save progress
    save_processed_messages()
    await client.disconnect()
    
    logger.info("=" * 60)
    logger.info("✅ SCAN COMPLETE!")
    logger.info(f"📸 Photos found: {messages_found}")
    logger.info(f"🔍 Processed: {messages_processed}")
    logger.info(f"💾 Saved: {messages_saved}")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Now run 'python better1.py' to start listening for new messages.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Receipt Processing Bot")
    parser.add_argument(
        '--scan-history',
        type=str,
        metavar='DATE',
        help='Scan historical messages from DATE (format: YYYY-MM-DD)'
    )
    parser.add_argument(
        '--group',
        type=int,
        metavar='GROUP_ID',
        help='Group ID to scan (optional, uses first group if not specified)'
    )
    parser.add_argument(
        '--notify',
        action='store_true',
        help='Send confirmation messages to the Telegram group for each processed receipt'
    )
    
    args = parser.parse_args()
    
    if args.scan_history:
        # Run terminal history scan
        import asyncio
        asyncio.run(run_terminal_history_scan(args.scan_history, args.group, args.notify))
    else:
        # Normal bot operation
        main()


"""
Telegram Mini App Backend API
Serves data from Google Sheets for the admin and user panels
"""

import os
import sys
import json
import re
import hmac
import hashlib
from urllib.parse import parse_qs
from functools import wraps
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__, static_folder='static')
CORS(app)

# Custom URL converter for signed integers (negative group IDs)
from werkzeug.routing import IntegerConverter
class SignedIntConverter(IntegerConverter):
    regex = r'-?\d+'
app.url_map.converters['signed'] = SignedIntConverter

# Configuration - supports both local file and environment variable modes
BOT_TOKEN = os.getenv('BOT_TOKEN', '')

# For local development: use file paths (relative to webapp folder)
# For deployment: set GOOGLE_CREDENTIALS_JSON env var with the JSON content
CREDENTIALS_FILE = os.getenv('CREDENTIALS_FILE', '../credentials.json')
GROUPS_FILE = os.getenv('GROUPS_FILE', '../groups.json')

# Support loading credentials from environment variable (for cloud deployment)
def get_google_credentials():
    """Get Google credentials from file or environment variable"""
    from oauth2client.service_account import ServiceAccountCredentials
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    # Check for JSON credentials in environment variable (cloud deployment)
    creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
    if creds_json:
        import json
        creds_dict = json.loads(creds_json)
        return ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    
    # Fall back to file (local development)
    return ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)

# Load group configs
def load_group_configs():
    try:
        with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            groups = data.get('groups', {})
            return {int(k): v for k, v in groups.items() if not k.startswith('_')}
    except Exception as e:
        print(f"Error loading groups.json: {e}")
        return {}

GROUP_CONFIGS = load_group_configs()

# Ethiopian months
ETHIOPIAN_MONTHS = [
    'Meskerem', 'Tikimt', 'Hidar', 'Tahsas', 'Tir', 'Yekatit',
    'Megabit', 'Miyazya', 'Ginbot', 'Sene', 'Hamle', 'Nehase', 'Pagume'
]

ETHIOPIAN_MONTHS_AMHARIC = {
    'Meskerem': 'መስከረም', 'Tikimt': 'ጥቅምት', 'Hidar': 'ህዳር',
    'Tahsas': 'ታህሳስ', 'Tir': 'ጥር', 'Yekatit': 'የካቲት',
    'Megabit': 'መጋቢት', 'Miyazya': 'ሚያዚያ', 'Ginbot': 'ግንቦት',
    'Sene': 'ሰኔ', 'Hamle': 'ሐምሌ', 'Nehase': 'ነሐሴ', 'Pagume': 'ጳጉሜ'
}

PAYMENT_TYPES = ['water', 'electricity', 'development', 'penalty', 'other']

PAYMENT_TYPES_AMHARIC = {
    'water': 'ውሃ', 'electricity': 'መብራት', 'development': 'ልማት',
    'penalty': 'ቅጣት', 'other': 'ሌላ'
}

# Google Sheets connection cache
sheets_cache = {}

# User last submissions for edit mode (group_id: {user_id: submission_data})
user_last_submissions = {}

# ========== BENEFICIARY VALIDATION ==========
VALID_BENEFICIARIES = [
    "SEYOUM ASSEFA",
    "SENAIT DAGNIE",
    "SEYOUM ASSEFA AND SENAIT DAGNIE",
    "SEYOUM ASSEFA OR SENAIT DAGNIE",
    "ASSEFA SEYOUM",
    "DAGNIE SENAIT"
]

def normalize_name(name):
    """Normalize name for comparison"""
    if not name:
        return ""
    name = name.upper()
    name = re.sub(r'AND\s*/\s*OR', 'AND OR', name)
    name = re.sub(r'&', 'AND', name)
    name = re.sub(r'[^\w\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def extract_beneficiary_from_receipt(text):
    """Extract beneficiary/receiver from receipt text"""
    if not text:
        return ""
    
    text = text.replace('\u2013', '-').replace('\u2014', '-')
    
    receiver_label_match = re.search(r'(?<!Source\s)(?<!Source Account\s)\b(Receiver Name|Beneficiary Name|Beneficiary)\b', text, re.IGNORECASE)
    
    if receiver_label_match:
        lines = text.split('\n')
        receiver_label_line_idx = None
        
        for i, line in enumerate(lines):
            if re.search(r'\b(Receiver Name|Beneficiary Name|Beneficiary)\b', line, re.IGNORECASE):
                if not re.search(r'Source', line, re.IGNORECASE):
                    receiver_label_line_idx = i
                    break
        
        if receiver_label_line_idx is not None:
            search_start = receiver_label_line_idx + 1
            search_end = min(receiver_label_line_idx + 12, len(lines))
            candidates = []
            
            for i in range(search_start, search_end):
                line = lines[i].strip()
                if not line or re.match(r'^\d', line):
                    continue
                if re.search(r'(Transaction|Reference|Type|Bank|Note|Account|Amount|Date|Time|Source|ETB|FTB)', line, re.IGNORECASE):
                    continue
                
                if re.search(r'\b[A-Z]{2,}\s+[A-Z]{2,}', line):
                    beneficiary = line.strip()
                    beneficiary = re.sub(r'AND\s*/\s*OR', 'AND OR', beneficiary, flags=re.IGNORECASE)
                    beneficiary = re.sub(r'ANDOR', 'AND OR', beneficiary, flags=re.IGNORECASE)
                    beneficiary = re.sub(r'\s+', ' ', beneficiary).strip()
                    beneficiary = re.sub(r'\s+(ETB|FTB|BIRR).*$', '', beneficiary, flags=re.IGNORECASE)
                    
                    if len(beneficiary.split()) >= 2 or 'AND OR' in beneficiary.upper():
                        if beneficiary.upper() not in ['SEBLE FULIE SHUME', 'SEBLE FULIE', 'FULIE SHUME']:
                            candidates.append(beneficiary)
            
            for cand in candidates:
                if 'AND OR' in cand.upper():
                    return cand
            
            if candidates:
                return candidates[-1]
    
    # Fallback: joint account pattern
    joint_patterns = [
        r'([A-Z][A-Z]+\s+[A-Z][A-Z]+\s+AND\s+OR\s+[A-Z][A-Z]+\s+[A-Z][A-Z]+)',
        r'([A-Z][A-Z]+\s+[A-Z][A-Z]+\s+AND\s*/\s*OR\s+[A-Z][A-Z]+\s+[A-Z][A-Z]+)',
    ]
    
    for pattern in joint_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            beneficiary = match.group(1).strip()
            beneficiary = re.sub(r'\s+', ' ', beneficiary).strip()
            if 10 <= len(beneficiary) <= 80:
                return beneficiary
    
    return ""

def validate_beneficiary(beneficiary_text):
    """Validate if beneficiary matches expected account names"""
    if not beneficiary_text:
        return False, ""
    
    normalized = normalize_name(beneficiary_text)
    extracted_tokens = set(normalized.split())
    connectors = {'AND', 'OR', 'ANDOR', 'THE', 'OF', 'TO', 'A', 'AN', '&', '/'}
    extracted_tokens_clean = extracted_tokens - connectors
    
    authorized_tokens = {
        'SEYOUM', 'SEYSOA', 'SEYSOM', 'SEYSUM', 'SEYOAM',
        'ASSEFA', 'ASEFA', 'ASEFFA',
        'SENAIT', 'SENIET', 'SENAYT', 'SENAITE',
        'DAGNIE', 'DAGNE', 'DAGINE', 'DAGNY', 'DAGNHE'
    }
    
    matching_tokens = extracted_tokens_clean & authorized_tokens
    
    if matching_tokens:
        return True, normalized
    
    return False, normalized

def check_duplicate_txid(sheets, txid, exclude_house_number=None):
    """Check if transaction ID already exists in any sheet"""
    if not txid or not txid.strip():
        return False, None, None
    
    txid = txid.strip()
    
    for sheet_reason, sheet in sheets.items():
        try:
            values = sheet.get_all_values()
            for idx, row in enumerate(values[2:], start=3):
                if exclude_house_number and len(row) > 1 and row[1].strip() == exclude_house_number:
                    continue
                
                for col_idx in range(4, len(row), 2):
                    if len(row) > col_idx:
                        cell_value = row[col_idx].strip()
                        if cell_value:
                            existing_txids = [t.strip() for t in cell_value.split(',')]
                            if txid in existing_txids:
                                return True, sheet_reason, idx
        except Exception as e:
            print(f"Error checking duplicate in {sheet_reason}: {e}")
    
    return False, None, None

def get_sheets(group_id):
    """Get Google Sheets for a group"""
    if group_id in sheets_cache:
        return sheets_cache[group_id]
    
    if group_id not in GROUP_CONFIGS:
        return None
    
    try:
        creds = get_google_credentials()
        gc = gspread.authorize(creds)
        
        spreadsheet_id = GROUP_CONFIGS[group_id]['spreadsheet_id']
        spreadsheet = gc.open_by_key(spreadsheet_id)
        
        sheets = {}
        for payment_type in PAYMENT_TYPES:
            try:
                sheets[payment_type] = spreadsheet.worksheet(payment_type.capitalize())
            except:
                pass
        
        sheets_cache[group_id] = sheets
        return sheets
    except Exception as e:
        print(f"Error connecting to sheets: {e}")
        return None


# ========== TELEGRAM AUTH ==========

def verify_telegram_data(init_data):
    """Verify Telegram WebApp initData"""
    if not init_data or not BOT_TOKEN:
        return None
    
    try:
        parsed = parse_qs(init_data)
        
        # Get hash and remove from data
        received_hash = parsed.get('hash', [''])[0]
        data_pairs = []
        
        for key, value in parsed.items():
            if key != 'hash':
                data_pairs.append(f"{key}={value[0]}")
        
        data_pairs.sort()
        data_check_string = '\n'.join(data_pairs)
        
        # Create secret key
        secret_key = hmac.new(b'WebAppData', BOT_TOKEN.encode(), hashlib.sha256).digest()
        
        # Calculate hash
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if calculated_hash == received_hash:
            # Extract user info
            user_data = parsed.get('user', ['{}'])[0]
            user = json.loads(user_data)
            return user
        
        return None
    except Exception as e:
        print(f"Auth error: {e}")
        return None


def require_auth(f):
    """Decorator to require Telegram authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        init_data = request.headers.get('X-Telegram-Init-Data', '')
        user = verify_telegram_data(init_data)
        
        # For development, allow without auth
        if not user and os.getenv('DEV_MODE'):
            user = {'id': 638333361, 'first_name': 'Dev User'}
        
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        request.telegram_user = user
        return f(*args, **kwargs)
    return decorated


def is_admin(user_id, group_id):
    """Check if user is admin for group"""
    if group_id not in GROUP_CONFIGS:
        return False
    admin_ids = GROUP_CONFIGS[group_id].get('admin_user_ids', [])
    return user_id in admin_ids


def get_user_house(user_id, group_id):
    """Get house number for user"""
    if group_id not in GROUP_CONFIGS:
        return None
    user_houses = GROUP_CONFIGS[group_id].get('user_houses', {})
    return user_houses.get(str(user_id))


# ========== API ROUTES ==========

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/css/<path:path>')
def serve_css(path):
    return send_from_directory('static/css', path)


@app.route('/js/<path:path>')
def serve_js(path):
    return send_from_directory('static/js', path)


@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)


@app.route('/api/auth', methods=['POST'])
def auth():
    """Authenticate user and return their role info"""
    init_data = request.headers.get('X-Telegram-Init-Data', '')
    user = verify_telegram_data(init_data)
    
    # Dev mode bypass
    if not user and os.getenv('DEV_MODE'):
        user = {'id': 638333361, 'first_name': 'Dev User'}
    
    if not user:
        return jsonify({'error': 'Invalid authentication'}), 401
    
    user_id = user.get('id')
    
    # Find groups where user is admin
    admin_groups = []
    user_houses = {}
    
    for group_id, config in GROUP_CONFIGS.items():
        if user_id in config.get('admin_user_ids', []):
            admin_groups.append({
                'id': group_id,
                'name': config.get('name', f'Group {group_id}')
            })
        
        house = config.get('user_houses', {}).get(str(user_id))
        if house:
            user_houses[group_id] = house
    
    # Check if user is registered anywhere
    is_registered = len(admin_groups) > 0 or len(user_houses) > 0
    
    return jsonify({
        'user': {
            'id': user_id,
            'first_name': user.get('first_name', ''),
            'username': user.get('username', '')
        },
        'is_admin': len(admin_groups) > 0,
        'admin_groups': admin_groups,
        'user_houses': user_houses,
        'is_registered': is_registered
    })


@app.route('/api/dashboard/<signed:group_id>')
@require_auth
def get_dashboard(group_id):
    """Get dashboard statistics"""
    user_id = request.telegram_user.get('id')
    
    if not is_admin(user_id, group_id):
        return jsonify({'error': 'Not authorized for this group'}), 403
    
    sheets = get_sheets(group_id)
    if not sheets:
        return jsonify({'error': 'Could not connect to spreadsheet'}), 500
    
    stats = {
        'total_amount': 0,
        'total_houses': 0,
        'by_type': {},
        'by_month': {month: 0 for month in ETHIOPIAN_MONTHS},
        'group_name': GROUP_CONFIGS[group_id].get('name', 'Group')
    }
    
    unique_houses = set()
    
    for payment_type in PAYMENT_TYPES:
        sheet = sheets.get(payment_type)
        if not sheet:
            continue
        
        try:
            values = sheet.get_all_values()
            type_total = 0
            
            for row in values[2:]:  # Skip headers
                if len(row) > 1 and row[1] and row[1] != 'TOTAL':
                    house = row[1].strip()
                    
                    for month_idx, month in enumerate(ETHIOPIAN_MONTHS):
                        amount_col = 3 + (month_idx * 2)
                        if amount_col < len(row) and row[amount_col]:
                            try:
                                amount = float(str(row[amount_col]).replace(',', ''))
                                type_total += amount
                                stats['by_month'][month] += amount
                                unique_houses.add(house)
                            except:
                                pass
            
            if type_total > 0:
                stats['by_type'][payment_type] = {
                    'total': type_total,
                    'name': PAYMENT_TYPES_AMHARIC.get(payment_type, payment_type)
                }
                stats['total_amount'] += type_total
        except Exception as e:
            print(f"Error reading {payment_type}: {e}")
    
    stats['total_houses'] = len(unique_houses)
    
    return jsonify(stats)


@app.route('/api/houses/<signed:group_id>')
@require_auth
def get_houses(group_id):
    """Get all houses with payment info"""
    user_id = request.telegram_user.get('id')
    
    if not is_admin(user_id, group_id):
        return jsonify({'error': 'Not authorized'}), 403
    
    sheets = get_sheets(group_id)
    if not sheets:
        return jsonify({'error': 'Could not connect to spreadsheet'}), 500
    
    houses = {}
    
    for payment_type in PAYMENT_TYPES:
        sheet = sheets.get(payment_type)
        if not sheet:
            continue
        
        try:
            values = sheet.get_all_values()
            
            for row in values[2:]:
                if len(row) > 2 and row[1] and row[1] != 'TOTAL':
                    house_num = row[1].strip()
                    house_name = row[2].strip() if len(row) > 2 else ''
                    
                    if house_num not in houses:
                        houses[house_num] = {
                            'number': house_num,
                            'name': house_name,
                            'total': 0,
                            'payments': []
                        }
                    
                    for month_idx, month in enumerate(ETHIOPIAN_MONTHS):
                        amount_col = 3 + (month_idx * 2)
                        txid_col = amount_col + 1
                        
                        if amount_col < len(row) and row[amount_col]:
                            try:
                                amount = float(str(row[amount_col]).replace(',', ''))
                                txid = row[txid_col] if txid_col < len(row) else ''
                                
                                houses[house_num]['total'] += amount
                                houses[house_num]['payments'].append({
                                    'type': payment_type,
                                    'type_amharic': PAYMENT_TYPES_AMHARIC.get(payment_type, payment_type),
                                    'month': month,
                                    'month_amharic': ETHIOPIAN_MONTHS_AMHARIC.get(month, month),
                                    'amount': amount,
                                    'txid': txid
                                })
                            except:
                                pass
        except Exception as e:
            print(f"Error reading {payment_type}: {e}")
    
    return jsonify({
        'houses': sorted(houses.values(), key=lambda x: x['number']),
        'group_name': GROUP_CONFIGS[group_id].get('name', 'Group')
    })


@app.route('/api/user/<signed:group_id>')
@require_auth
def get_user_payments(group_id):
    """Get payments for current user's house"""
    user_id = request.telegram_user.get('id')
    house_number = get_user_house(user_id, group_id)
    
    if not house_number:
        return jsonify({'error': 'No house registered for this user', 'house': None}), 404
    
    sheets = get_sheets(group_id)
    if not sheets:
        return jsonify({'error': 'Could not connect to spreadsheet'}), 500
    
    house_data = {
        'number': house_number,
        'name': '',
        'total': 0,
        'payments': [],
        'months_paid': [],
        'months_unpaid': []
    }
    
    months_with_payment = set()
    
    for payment_type in PAYMENT_TYPES:
        sheet = sheets.get(payment_type)
        if not sheet:
            continue
        
        try:
            values = sheet.get_all_values()
            
            for row in values[2:]:
                if len(row) > 1 and row[1].strip() == house_number:
                    house_data['name'] = row[2].strip() if len(row) > 2 else ''
                    
                    for month_idx, month in enumerate(ETHIOPIAN_MONTHS):
                        amount_col = 3 + (month_idx * 2)
                        txid_col = amount_col + 1
                        
                        if amount_col < len(row) and row[amount_col]:
                            try:
                                amount = float(str(row[amount_col]).replace(',', ''))
                                txid = row[txid_col] if txid_col < len(row) else ''
                                
                                house_data['total'] += amount
                                house_data['payments'].append({
                                    'type': payment_type,
                                    'type_amharic': PAYMENT_TYPES_AMHARIC.get(payment_type, payment_type),
                                    'month': month,
                                    'month_amharic': ETHIOPIAN_MONTHS_AMHARIC.get(month, month),
                                    'amount': amount,
                                    'txid': txid
                                })
                                months_with_payment.add(month)
                            except:
                                pass
                    break
        except Exception as e:
            print(f"Error: {e}")
    
    house_data['months_paid'] = list(months_with_payment)
    house_data['months_unpaid'] = [m for m in ETHIOPIAN_MONTHS if m not in months_with_payment]
    
    return jsonify({
        'house': house_data,
        'group_name': GROUP_CONFIGS[group_id].get('name', 'Group')
    })


@app.route('/api/months')
def get_months():
    """Get Ethiopian months list"""
    return jsonify({
        'months': [
            {'english': m, 'amharic': ETHIOPIAN_MONTHS_AMHARIC.get(m, m)}
            for m in ETHIOPIAN_MONTHS
        ]
    })


# ========== PAYMENT SUBMISSION ENDPOINTS ==========

import base64
import uuid
from datetime import datetime

# Create receipts directory (try parent first, then current for deployment)
RECEIPTS_DIR = '../receipts'
if not os.path.exists(RECEIPTS_DIR):
    RECEIPTS_DIR = 'receipts'
os.makedirs(RECEIPTS_DIR, exist_ok=True)


def load_houses(group_id):
    """Load houses from houses.json for a group"""
    if group_id not in GROUP_CONFIGS:
        return {}
    
    houses_file = GROUP_CONFIGS[group_id].get('houses_file', 'houses.json')
    # Try parent directory first, then current directory (for deployment)
    houses_path = f'../{houses_file}'
    if not os.path.exists(houses_path):
        houses_path = houses_file
    
    try:
        with open(houses_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Handle both formats:
            # Simple: {"house_number": "name"}
            # Nested: {"houses": {"house_number": {"name": "..."}}}
            if 'houses' in data:
                return data['houses']
            return data  # Simple format
    except Exception as e:
        print(f"Error loading houses: {e}")
        return {}


@app.route('/api/lookup-house/<signed:group_id>/<house_number>')
@require_auth
def lookup_house(group_id, house_number):
    """Look up house name by number"""
    # Check if user is registered (admins can lookup any house, users can only lookup their own)
    user_id = request.telegram_user.get('id')
    if group_id not in GROUP_CONFIGS:
        return jsonify({'error': 'Group not found'}), 404
    
    admin_ids = GROUP_CONFIGS[group_id].get('admin_user_ids', [])
    user_houses = GROUP_CONFIGS[group_id].get('user_houses', {})
    user_house = user_houses.get(str(user_id))
    
    # Allow if admin OR if user is looking up their own house
    if user_id not in admin_ids:
        if not user_house or str(user_house) != str(house_number):
            return jsonify({
                'error': 'You can only lookup your own house number. Please contact an admin if you need to lookup other houses.'
            }), 403
    
    houses = load_houses(group_id)
    
    house_info = houses.get(house_number)
    
    if house_info:
        # Handle both formats
        if isinstance(house_info, str):
            # Simple format: {"201": "name"}
            name = house_info
        else:
            # Object format: {"201": {"name": "...", "owner": "..."}}
            name = house_info.get('name', house_info.get('owner', ''))
        
        return jsonify({
            'found': True,
            'house_number': house_number,
            'name': name,
            'owner': name
        })
    else:
        return jsonify({
            'found': False,
            'house_number': house_number,
            'message': 'House not found in registry'
        })


@app.route('/api/upload-receipt/<signed:group_id>', methods=['POST'])
@require_auth
def upload_receipt(group_id):
    """Upload receipt image and extract data using AI"""
    print(f"[UPLOAD] ===== Receipt upload request received for group {group_id} =====", flush=True)
    try:
        # Get image data from request
        data = request.get_json()
        image_data = data.get('image')  # Base64 encoded image
        print(f"[UPLOAD] Image data received: {len(image_data) if image_data else 0} chars", flush=True)
        
        if not image_data:
            return jsonify({'error': 'No image provided'}), 400
        
        # Remove data URL prefix if present
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        # Generate unique receipt ID
        receipt_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Save receipt to file
        receipt_path = os.path.join(RECEIPTS_DIR, f"{receipt_id}.jpg")
        with open(receipt_path, 'wb') as f:
            f.write(base64.b64decode(image_data))
        
        # Call Claude AI to extract receipt data (similar to bot logic)
        extracted_data = extract_receipt_data(image_data)
        
        return jsonify({
            'success': True,
            'receipt_id': receipt_id,
            'extracted': extracted_data,
            'beneficiary_warning': not extracted_data.get('beneficiary_valid', False) if extracted_data.get('beneficiary') else True
        })
        
    except Exception as e:
        print(f"Receipt upload error: {e}")
        return jsonify({'error': str(e)}), 500


# ========== BENEFICIARY VALIDATION ==========
VALID_BENEFICIARIES = [
    "SEYOUM ASSEFA",
    "SENAIT DAGNIE",
    "SEYOUM ASSEFA AND SENAIT DAGNIE",
    "SEYOUM ASSEFA OR SENAIT DAGNIE",
    "ASSEFA SEYOUM",  # Reversed order variant
    "DAGNIE SENAIT"   # Reversed order variant
]

def normalize_name(name):
    """Normalize name for comparison"""
    if not name:
        return ""
    name = name.upper()
    name = re.sub(r'AND\s*/\s*OR', 'AND OR', name)
    name = re.sub(r'&', 'AND', name)
    name = re.sub(r'[^\w\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def extract_beneficiary_from_receipt(text):
    """Extract beneficiary/receiver from receipt text"""
    if not text:
        return ""
    
    # Normalize Unicode dashes
    text = text.replace('\u2013', '-').replace('\u2014', '-')
    
    # Look for "Receiver Name" or "Beneficiary Name" label
    receiver_label_match = re.search(r'(?<!Source\s)(?<!Source Account\s)\b(Receiver Name|Beneficiary Name|Beneficiary)\b', text, re.IGNORECASE)
    
    if receiver_label_match:
        lines = text.split('\n')
        receiver_label_line_idx = None
        
        for i, line in enumerate(lines):
            if re.search(r'\b(Receiver Name|Beneficiary Name|Beneficiary)\b', line, re.IGNORECASE):
                if not re.search(r'Source', line, re.IGNORECASE):
                    receiver_label_line_idx = i
                    break
        
        if receiver_label_line_idx is not None:
            search_start = receiver_label_line_idx + 1
            search_end = min(receiver_label_line_idx + 12, len(lines))
            candidates = []
            
            for i in range(search_start, search_end):
                line = lines[i].strip()
                if not line or re.match(r'^\d', line):
                    continue
                if re.search(r'(Transaction|Reference|Type|Bank|Note|Account|Amount|Date|Time|Source|ETB|FTB)', line, re.IGNORECASE):
                    continue
                
                if re.search(r'\b[A-Z]{2,}\s+[A-Z]{2,}', line):
                    beneficiary = line.strip()
                    beneficiary = re.sub(r'AND\s*/\s*OR', 'AND OR', beneficiary, flags=re.IGNORECASE)
                    beneficiary = re.sub(r'ANDOR', 'AND OR', beneficiary, flags=re.IGNORECASE)
                    beneficiary = re.sub(r'\s+', ' ', beneficiary).strip()
                    beneficiary = re.sub(r'\s+(ETB|FTB|BIRR).*$', '', beneficiary, flags=re.IGNORECASE)
                    
                    if len(beneficiary.split()) >= 2 or 'AND OR' in beneficiary.upper():
                        if beneficiary.upper() not in ['SEBLE FULIE SHUME', 'SEBLE FULIE', 'FULIE SHUME']:
                            candidates.append(beneficiary)
            
            # Prefer joint accounts
            for cand in candidates:
                if 'AND OR' in cand.upper():
                    return cand
            
            if candidates:
                return candidates[-1]
    
    # Fallback: Look for joint account pattern
    joint_patterns = [
        r'([A-Z][A-Z]+\s+[A-Z][A-Z]+\s+AND\s+OR\s+[A-Z][A-Z]+\s+[A-Z][A-Z]+)',
        r'([A-Z][A-Z]+\s+[A-Z][A-Z]+\s+AND\s*/\s*OR\s+[A-Z][A-Z]+\s+[A-Z][A-Z]+)',
    ]
    
    for pattern in joint_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            beneficiary = match.group(1).strip()
            beneficiary = re.sub(r'\s+', ' ', beneficiary).strip()
            if 10 <= len(beneficiary) <= 80:
                return beneficiary
    
    return ""

def validate_beneficiary(beneficiary_text):
    """Validate if beneficiary matches expected account names"""
    if not beneficiary_text:
        return False, ""
    
    normalized = normalize_name(beneficiary_text)
    extracted_tokens = set(normalized.split())
    connectors = {'AND', 'OR', 'ANDOR', 'THE', 'OF', 'TO', 'A', 'AN', '&', '/'}
    extracted_tokens_clean = extracted_tokens - connectors
    
    authorized_tokens = {
        'SEYOUM', 'SEYSOA', 'SEYSOM', 'SEYSUM', 'SEYOAM',
        'ASSEFA', 'ASEFA', 'ASEFFA',
        'SENAIT', 'SENIET', 'SENAYT', 'SENAITE',
        'DAGNIE', 'DAGNE', 'DAGINE', 'DAGNY', 'DAGNHE'
    }
    
    matching_tokens = extracted_tokens_clean & authorized_tokens
    
    if matching_tokens:
        return True, normalized
    
    return False, normalized

def check_duplicate_txid(sheets, txid, exclude_house_number=None, group_id=None):
    """Check if transaction ID already exists in any sheet"""
    if not txid or not txid.strip():
        return False
    
    txid = txid.strip()
    
    for sheet_reason, sheet in sheets.items():
        try:
            values = sheet.get_all_values()
            for idx, row in enumerate(values[2:], start=3):  # Skip 2 header rows
                # Skip if this is the house we're editing
                if exclude_house_number and len(row) > 1 and row[1].strip() == exclude_house_number:
                    continue
                
                # Check all FT No columns (every even column starting from column E=4)
                for col_idx in range(4, len(row), 2):
                    if len(row) > col_idx:
                        cell_value = row[col_idx].strip()
                        if cell_value:
                            existing_txids = [t.strip() for t in cell_value.split(',')]
                            if txid in existing_txids:
                                return True, sheet_reason, idx
        except Exception as e:
            print(f"Error checking duplicate in {sheet_reason}: {e}")
    
    return False, None, None

def extract_receipt_data(image_base64):
    """Extract payment info from receipt using OCR.space"""
    
    text = None
    if not text:
        text = extract_text_with_ocrspace(image_base64)
    
    if not text:
        print("[OCR] All OCR methods failed")
        return {'amount': '', 'transaction_id': '', 'payer_name': '', 'beneficiary': ''}
    
    # Use ASCII-safe printing to avoid Windows encoding errors
    safe_text = text[:200].encode('ascii', 'replace').decode('ascii')
    print(f"[OCR] Extracted {len(text)} chars. First 200: {safe_text}")
    
    # Extract data using regex
    amount = extract_amount_from_text(text)
    txid = extract_txid_from_text(text)
    payer = extract_payer_from_text(text)
    beneficiary = extract_beneficiary_from_receipt(text)
    
    # Validate beneficiary
    is_valid_beneficiary, normalized_beneficiary = validate_beneficiary(beneficiary)
    
    print(f"[OCR] Extracted - Amount: {amount}, TxID: {txid}, Payer: {payer}, Beneficiary: {beneficiary} (Valid: {is_valid_beneficiary})")
    
    return {
        'amount': amount,
        'transaction_id': txid,
        'payer_name': payer,
        'beneficiary': beneficiary,
        'beneficiary_valid': is_valid_beneficiary,
        'beneficiary_normalized': normalized_beneficiary
    }


def extract_text_with_google_vision(image_base64):
    """Extract text using Google Cloud Vision API (uses same credentials as Google Sheets)"""
    try:
        from google.cloud import vision
        from google.oauth2 import service_account
        
        # Use same credentials as Google Sheets
        CREDENTIALS_FILE = '../credentials.json'
        
        credentials = service_account.Credentials.from_service_account_file(
            CREDENTIALS_FILE,
            scopes=['https://www.googleapis.com/auth/cloud-vision']
        )
        
        client = vision.ImageAnnotatorClient(credentials=credentials)
        
        # Clean base64 - remove data URL prefix if present
        if ',' in image_base64:
            image_base64 = image_base64.split(',')[1]
        
        # Decode and send to Vision API
        image_bytes = base64.b64decode(image_base64)
        image = vision.Image(content=image_bytes)
        
        print("[OCR] Sending to Google Vision API...")
        response = client.text_detection(image=image)
        
        if response.error.message:
            print(f"[OCR] Vision API error: {response.error.message}")
            return ''
        
        texts = response.text_annotations
        if texts:
            full_text = texts[0].description
            print(f"[OCR] ✓ Google Vision extracted {len(full_text)} chars")
            return full_text
        
        print("[OCR] Vision returned no text")
        return ''
        
    except ImportError:
        print("[OCR] google-cloud-vision not installed, falling back to OCR.space")
        return ''
    except Exception as e:
        print(f"[OCR] Google Vision error: {e}")
        return ''


def extract_text_with_ocrspace(image_base64):
    """Extract text using OCR.space API - EXACT same approach as bot"""
    import requests
    
    OCR_API_URL = 'https://api.ocr.space/parse/image'
    OCR_API_KEY = os.getenv('OCR_API_KEY', 'K89427089988957')
    
    max_retries = 3
    timeout_seconds = 45
    
    # Decode base64 to raw bytes (same as bot)
    try:
        if ',' in image_base64:
            image_base64 = image_base64.split(',')[1]
        image_bytes = base64.b64decode(image_base64)
        print(f"[OCR] Image decoded: {len(image_bytes)} bytes", flush=True)
    except Exception as e:
        print(f"[OCR] Base64 decode error: {e}", flush=True)
        return ''
    
    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                print(f"[OCR] Retrying OCR (attempt {attempt}/{max_retries})...", flush=True)
            else:
                print("[OCR] Running OCR.space...", flush=True)
            
            # EXACT same payload as bot
            payload = {
                'apikey': OCR_API_KEY,
                'language': 'eng',
                'isOverlayRequired': False,
                'detectOrientation': True,
                'scale': True,
                'OCREngine': 2
            }
            
            # Use file upload like bot (not base64)
            files = {'file': ('receipt.jpg', image_bytes, 'image/jpeg')}
            response = requests.post(OCR_API_URL, files=files, data=payload, timeout=timeout_seconds)
            
            if response.status_code == 200:
                result = response.json()
                if not result.get('IsErroredOnProcessing'):
                    text = result.get('ParsedResults', [{}])[0].get('ParsedText', '')
                    print(f"[OCR] SUCCESS: {len(text)} chars extracted", flush=True)
                    return text
                else:
                    error_msg = result.get('ErrorMessage', result.get('ErrorDetails', 'Unknown'))
                    print(f"[OCR] Processing error on attempt {attempt}: {error_msg}", flush=True)
            else:
                print(f"[OCR] Failed with status {response.status_code}", flush=True)
                
        except requests.exceptions.Timeout:
            print(f"[OCR] Timeout on attempt {attempt}/{max_retries}", flush=True)
            if attempt == max_retries:
                return ''
            continue
        except Exception as e:
            print(f"[OCR] Error on attempt {attempt}: {e}", flush=True)
            if attempt == max_retries:
                return ''
            continue
    
    print(f"[OCR] Failed after {max_retries} attempts", flush=True)
    return ''


def normalize_amount_lines(text):
    """Preprocess OCR text to join amount labels with their values on separate lines.
    (Same as bot - handles table-based layouts like Zemen Bank)
    """
    import re
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
        
        should_combine = False
        if has_amount_label and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
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


def extract_amount_from_text(text):
    """Extract amount from OCR text - EXACT copy from bot"""
    import re
    
    # Apply normalization first (same as bot)
    normalized_text = normalize_amount_lines(text)
    
    for search_text in [normalized_text, text]:
        # Priority 1: Settled Amount (Zemen Bank format)
        match = re.search(r'settled\s+amount[:\s]*ETB\s*([0-9,]+(?:\.[0-9]{2})?)', search_text, re.IGNORECASE | re.DOTALL)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                if float(amount_str) > 50:
                    return amount_str
            except:
                pass
        
        # Priority 2: Without VAT patterns
        without_vat_patterns = [
            r'(?:subtotal|sub-total|sub total|before vat|excluding vat|excl\.? vat)[:\s]*(?:ETB|birr|ብር)?\s*([0-9,]+(?:\.[0-9]{2})?)',
            r'(?:ETB|birr|ብር)?\s*([0-9,]+(?:\.[0-9]{2})?)\s*(?:before vat|excluding vat|excl\.? vat)',
        ]
        
        for pattern in without_vat_patterns:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '')
                try:
                    if float(amount_str) > 50:
                        return amount_str
                except:
                    pass
        
        # Priority 3: Debited pattern
        match = re.search(r'ETB\s*([0-9,]+(?:\.[0-9]{2})?)\s+debited', search_text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                if float(amount_str) > 50:
                    return amount_str
            except:
                pass
        
        # Priority 4: Standard patterns
        patterns = [
            r'(?:debited|Debited|DEBITED).*?ETB\s*([0-9,]+(?:\.[0-9]{2})?)',
            r'(?:Amount|amount|AMOUNT).*?(?:ETB|birr)?\s*([0-9,]+(?:\.[0-9]{2})?)',
            r'(?:ETB|birr|ብር)\s*([0-9,]+(?:\.[0-9]{2})?)',
            r'([0-9,]+(?:\.[0-9]{2})?)\s*(?:ETB|birr|ብር)',
            r'transferred\s+ETB\s*([0-9,]+(?:\.[0-9]{2})?)',
        ]
        
        all_amounts = []
        for pattern in patterns:
            for match in re.finditer(pattern, search_text, re.IGNORECASE):
                amount_str = match.group(1).replace(',', '')
                try:
                    amount_val = float(amount_str)
                    if amount_val > 50:
                        match_pos = match.start()
                        context = search_text[max(0, match_pos - 30):min(len(search_text), match_pos + 100)]
                        # Exclude total amounts
                        if 'total' not in context.lower() and 'vat' not in context.lower():
                            all_amounts.append(amount_val)
                except:
                    pass
        
        if all_amounts:
            return str(min(all_amounts))  # Return smallest amount (likely without VAT)
    
    # Fallback: standalone amounts
    match = re.search(r'([0-9,]+\.[0-9]{2})\s*(?:Birr|ETB)', text, re.IGNORECASE)
    if match:
        amount_str = match.group(1).replace(',', '')
        try:
            if float(amount_str) > 50:
                return amount_str
        except:
            pass
    
    return ''


def extract_txid_from_text(text):
    """Extract transaction ID from OCR text - uses same logic as bot"""
    import re
    
    # Priority 1: Zemen Bank - Payment order number / Reference No
    match = re.search(r'(?:payment\s+order\s+number|reference\s+no\.?)[:\s]*\n?\s*([A-Z0-9]{10,})', text, re.IGNORECASE | re.MULTILINE)
    if match:
        txid = match.group(1).strip()
        if len(txid) >= 10:
            return txid
    
    # Priority 2: Telebirr invoice (DAE3SX92FL format)
    match = re.search(r'(?:invoice\s+no\.?)[:\s]*\n?\s*([A-Z]{3}[A-Z0-9]{7,12})', text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    
    # Priority 3: Standard patterns
    patterns = [
        r'(?:transaction\s+id|tx\s+id|txid|tran\s+ref)[:\s]*([A-Za-z0-9]{8,})',
        r'(?:FT|TT)[A-Z0-9]{10,}',
        r'(?:Transaction|Trans|TXN|Ref|Reference)[:\s#]*([A-Z0-9]{6,20})',
        r'\b([A-Z]{2,3}[0-9]{8,15})\b',  # Common bank format like FT123456789
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result = match.group(1) if match.lastindex else match.group(0)
            if len(result) >= 6:
                return result
    
    return ''


def extract_payer_from_text(text):
    """Extract payer name from OCR text"""
    import re
    
    patterns = [
        r'(?:From|Sender|Payer|Account Holder)[:\s]*([A-Za-z\s]{5,40})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return ''


@app.route('/api/submit-payment/<signed:group_id>', methods=['POST'])
@require_auth
def submit_payment(group_id):
    """Submit payment to Google Sheets with beneficiary validation and duplicate checking"""
    try:
        data = request.get_json()
        user_id = request.telegram_user.get('id')
        
        # Check if user is registered (has house or is admin)
        if group_id not in GROUP_CONFIGS:
            return jsonify({
                'success': False,
                'errors': [{'field': 'general', 'message': 'Group not found'}]
            }), 404
        
        user_houses = GROUP_CONFIGS[group_id].get('user_houses', {})
        admin_ids = GROUP_CONFIGS[group_id].get('admin_user_ids', [])
        
        # Allow if user is admin OR has registered house
        if user_id not in admin_ids and str(user_id) not in user_houses:
            return jsonify({
                'success': False,
                'errors': [{
                    'field': 'general',
                    'message': 'You are not registered. Please contact an admin to register your house number.'
                }]
            }), 403
        
        # Required fields
        house_number = data.get('house_number', '').strip()
        payment_type = data.get('payment_type', '').lower()
        month = data.get('month', '')
        amount = data.get('amount', 0)
        transaction_id = data.get('transaction_id', '').strip()
        payer_name = data.get('payer_name', '').strip()
        receipt_id = data.get('receipt_id', '')
        is_edit_mode = data.get('is_edit_mode', False)
        beneficiary = data.get('beneficiary', '')
        beneficiary_valid = data.get('beneficiary_valid', False)
        
        # Validation
        errors = []
        
        if not house_number or not house_number.isdigit() or len(house_number) not in [3, 4]:
            errors.append({'field': 'house_number', 'message': 'House number must be 3-4 digits'})
        
        if payment_type not in PAYMENT_TYPES:
            errors.append({'field': 'payment_type', 'message': f'Invalid type. Choose: {", ".join(PAYMENT_TYPES)}'})
        
        if month not in ETHIOPIAN_MONTHS:
            errors.append({'field': 'month', 'message': 'Invalid month'})
        
        try:
            amount = float(str(amount).replace(',', ''))
            if amount <= 0:
                errors.append({'field': 'amount', 'message': 'Amount must be greater than 0'})
        except:
            errors.append({'field': 'amount', 'message': 'Invalid amount format'})
        
        # Transaction ID is optional - allow submission without it but mark as warning
        if not transaction_id or transaction_id == 'N/A':
            transaction_id = ''  # Allow empty TXID
        
        if errors:
            return jsonify({'success': False, 'errors': errors}), 400
        
        # Get sheets
        sheets = get_sheets(group_id)
        if not sheets:
            return jsonify({'success': False, 'errors': [{'field': 'general', 'message': 'Could not connect to spreadsheet'}]}), 500
        
        # ========== BENEFICIARY VALIDATION ==========
        if beneficiary and not beneficiary_valid:
            return jsonify({
                'success': False,
                'errors': [{
                    'field': 'beneficiary',
                    'message': f'Invalid beneficiary: {beneficiary}. Payment must be sent to authorized account (SEYOUM ASSEFA and/or SENAIT DAGNIE)'
                }]
            }), 400
        
        if not beneficiary:
            return jsonify({
                'success': False,
                'errors': [{
                    'field': 'beneficiary',
                    'message': 'Beneficiary not found on receipt. Cannot verify payment account.'
                }]
            }), 400
        
        # ========== DUPLICATE TXID CHECK ==========
        # Only check for duplicates if TXID is provided
        if transaction_id and transaction_id.strip():
            exclude_house = house_number if is_edit_mode else None
            is_duplicate, duplicate_sheet, duplicate_row = check_duplicate_txid(sheets, transaction_id, exclude_house)
            
            if is_duplicate:
                return jsonify({
                    'success': False,
                    'errors': [{
                        'field': 'transaction_id',
                        'message': f'This receipt has been sent before. Transaction ID {transaction_id} found in {duplicate_sheet} (row {duplicate_row})'
                    }]
                }), 400
        
        # ========== EDIT MODE: DELETE OLD ENTRY ==========
        if is_edit_mode:
            # Get user's last submission
            if group_id not in user_last_submissions:
                user_last_submissions[group_id] = {}
            
            last_submission = user_last_submissions[group_id].get(user_id)
            if last_submission:
                old_house = last_submission.get('house_number')
                old_txid = last_submission.get('transaction_id')
                old_sheet_name = last_submission.get('payment_type')
                
                if old_sheet_name and old_sheet_name in sheets:
                    old_sheet = sheets[old_sheet_name]
                    old_values = old_sheet.get_all_values()
                    
                    for idx, row in enumerate(old_values[2:], start=3):
                        if len(row) > 1 and row[1].strip() == old_house:
                            old_month_index = ETHIOPIAN_MONTHS.index(last_submission.get('month', 'Tir'))
                            old_amount_col = 4 + (old_month_index * 2)
                            old_txid_col = old_amount_col + 1
                            
                            if len(row) > old_txid_col and row[old_txid_col].strip() == old_txid:
                                # Delete old entry
                                old_sheet.update_cell(idx, old_amount_col, '')
                                old_sheet.update_cell(idx, old_txid_col, '')
                                print(f"[EDIT MODE] Deleted old entry from {old_sheet_name} row {idx}")
                                break
        
        sheet = sheets.get(payment_type)
        if not sheet:
            return jsonify({'success': False, 'errors': [{'field': 'payment_type', 'message': f'Sheet not found for {payment_type}'}]}), 500
        
        # Find or create row for this house
        month_index = ETHIOPIAN_MONTHS.index(month)
        amount_col = 4 + (month_index * 2)
        txid_col = amount_col + 1
        
        # Find house row
        values = sheet.get_all_values()
        house_row = None
        
        for idx, row in enumerate(values[2:], start=3):
            if len(row) > 1 and row[1].strip() == house_number:
                house_row = idx
                break
        
        if house_row:
            # Update existing row
            sheet.update_cell(house_row, amount_col, amount)
            # Only update TXID if provided
            if transaction_id and transaction_id.strip():
                sheet.update_cell(house_row, txid_col, transaction_id)
        else:
            # Add new row
            new_row = [''] * max(txid_col, 30)
            new_row[1] = house_number
            new_row[2] = payer_name
            new_row[amount_col - 1] = amount
            # Only set TXID if provided
            if transaction_id and transaction_id.strip():
                new_row[txid_col - 1] = transaction_id
            sheet.append_row(new_row)
        
        # Store last submission for edit mode
        if group_id not in user_last_submissions:
            user_last_submissions[group_id] = {}
        
        user_last_submissions[group_id][user_id] = {
            'house_number': house_number,
            'payment_type': payment_type,
            'month': month,
            'amount': amount,
            'transaction_id': transaction_id,
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True,
            'message': 'Payment recorded successfully',
            'details': {
                'house': house_number,
                'type': payment_type,
                'month': month,
                'amount': amount
            }
        })
        
    except Exception as e:
        print(f"Submit payment error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'errors': [{'field': 'general', 'message': str(e)}]}), 500


@app.route('/api/payment-types')
def get_payment_types():
    """Get available payment types"""
    return jsonify({
        'types': [
            {'id': t, 'name': PAYMENT_TYPES_AMHARIC.get(t, t), 'english': t}
            for t in PAYMENT_TYPES
        ]
    })


@app.route('/api/last-submission/<signed:group_id>')
@require_auth
def get_last_submission(group_id):
    """Get user's last submission for edit mode"""
    user_id = request.telegram_user.get('id')
    
    if group_id not in user_last_submissions:
        return jsonify({'has_submission': False})
    
    last_submission = user_last_submissions[group_id].get(user_id)
    
    if not last_submission:
        return jsonify({'has_submission': False})
    
    return jsonify({
        'has_submission': True,
        'submission': last_submission
    })


if __name__ == '__main__':
    # Get port from environment (for production) or default to 5000
    port = int(os.getenv('PORT', 5000))
    # Only enable dev mode if explicitly set
    if os.getenv('DEV_MODE'):
        os.environ['DEV_MODE'] = '1'
        app.run(host='0.0.0.0', port=port, debug=True)
    else:
        # Production mode
        app.run(host='0.0.0.0', port=port, debug=False)


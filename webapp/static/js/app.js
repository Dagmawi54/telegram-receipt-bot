/**
 * Telegram Mini App - Payment Manager
 * Premium UI Version
 */

const API_BASE = window.location.origin;
const tg = window.Telegram?.WebApp;

// State
let currentUser = null;
let currentGroupId = null;
let dashboardData = null;
let housesData = null;
let currentFilterType = null;
let currentLang = localStorage.getItem('app_lang') || 'am'; // Default to Amharic

// ========== TRANSLATIONS ==========
const translations = {
    en: {
        // Welcome Screen
        hello: 'Hello',
        selectWorkspace: 'Select a workspace to continue',
        adminDashboard: 'Admin Dashboard',
        myResidence: 'My Residence',
        house: 'House',

        // Admin Panel
        adminPanel: 'Admin Panel',
        overview: 'Overview',
        houses: 'Houses',
        find: 'Find',
        totalCollected: 'Total Collected',
        housesPaid: 'Houses Paid',
        thisMonth: 'This Month',
        breakdown: 'Breakdown',
        monthlyTrends: 'Monthly Trends',
        searchHouse: 'Search house number...',
        paymentCategory: 'Payment Category',
        txns: 'txns',
        resident: 'Resident',

        // User Panel
        residentView: 'Resident View',
        lifetimePaid: 'Lifetime Paid',
        submitNewPayment: 'Submit New Payment',
        monthlyStatus: 'Monthly Status',
        paymentHistory: 'Payment History',
        noPaymentsYet: 'No payments yet',

        // Payment Submission
        submitPayment: 'Submit Payment',
        paymentDetails: 'Payment Details',
        step1Upload: 'Step 1: Upload Receipt',
        step2Confirm: 'Step 2: Confirm Information',
        uploadReceipt: 'Upload Receipt',
        tapToUpload: 'Tap to take photo or choose from gallery',
        continue: 'Continue',
        analyzingReceipt: 'Analyzing receipt...',
        amountDetected: 'Amount Detected',
        houseNumber: 'House Number',
        paymentType: 'Payment Type',
        month: 'Month',
        selectType: 'Select type...',
        selectMonth: 'Select month...',
        submit: 'Submit',
        paymentRecorded: 'Payment Recorded!',
        paymentSaved: 'Your payment has been saved.',
        done: 'Done',
        houseNotInRegistry: 'House not in registry (will be added)',
        required: 'required',

        // Errors
        houseNumberRequired: 'House number is required',
        paymentTypeRequired: 'Payment type is required',
        monthRequired: 'Month is required',
        networkError: 'Network error. Please try again.',

        // Detail View
        totalAmount: 'Total Amount',
        records: 'Records',

        // Language
        switchLanguage: 'አማርኛ'
    },
    am: {
        // Welcome Screen
        hello: 'ሰላም',
        selectWorkspace: 'ለመቀጠል ስራ ቦታ ይምረጡ',
        adminDashboard: 'አስተዳዳሪ ዳሽቦርድ',
        myResidence: 'የኔ ቤት',
        house: 'ቤት',

        // Admin Panel
        adminPanel: 'አስተዳዳሪ ፓነል',
        overview: 'አጠቃላይ',
        houses: 'ቤቶች',
        find: 'ፈልግ',
        totalCollected: 'ጠቅላላ ተሰብስቧል',
        housesPaid: 'የከፈሉ ቤቶች',
        thisMonth: 'በዚህ ወር',
        breakdown: 'ዝርዝር',
        monthlyTrends: 'ወርሃዊ አዝማሚያ',
        searchHouse: 'የቤት ቁጥር ፈልግ...',
        paymentCategory: 'የክፍያ ዓይነት',
        txns: 'ክፍያዎች',
        resident: 'ነዋሪ',

        // User Panel
        residentView: 'የነዋሪ እይታ',
        lifetimePaid: 'ጠቅላላ የተከፈለ',
        submitNewPayment: 'አዲስ ክፍያ አስገባ',
        monthlyStatus: 'ወርሃዊ ሁኔታ',
        paymentHistory: 'የክፍያ ታሪክ',
        noPaymentsYet: 'እስካሁን ክፍያ የለም',

        // Payment Submission
        submitPayment: 'ክፍያ አስገባ',
        paymentDetails: 'የክፍያ ዝርዝር',
        step1Upload: 'ደረጃ 1: ደረሰኝ ስቀል',
        step2Confirm: 'ደረጃ 2: መረጃውን አረጋግጥ',
        uploadReceipt: 'ደረሰኝ ስቀል',
        tapToUpload: 'ፎቶ ለማንሳት ወይም ከጋለሪ ለመምረጥ ይንኩ',
        continue: 'ቀጥል',
        analyzingReceipt: 'ደረሰኝ በመተንተን ላይ...',
        amountDetected: 'የተገኘ መጠን',
        houseNumber: 'የቤት ቁጥር',
        paymentType: 'የክፍያ ዓይነት',
        month: 'ወር',
        selectType: 'ዓይነት ይምረጡ...',
        selectMonth: 'ወር ይምረጡ...',
        submit: 'አስገባ',
        paymentRecorded: 'ክፍያ ተመዝግቧል!',
        paymentSaved: 'ክፍያዎ ተቀምጧል።',
        done: 'ተጠናቅቋል',
        houseNotInRegistry: 'ቤቱ በመዝገብ ውስጥ የለም (ይጨመራል)',
        required: 'ያስፈልጋል',

        // Errors
        houseNumberRequired: 'የቤት ቁጥር ያስፈልጋል',
        paymentTypeRequired: 'የክፍያ ዓይነት ያስፈልጋል',
        monthRequired: 'ወር ያስፈልጋል',
        networkError: 'የኔትወርክ ስህተት። እባክዎ እንደገና ይሞክሩ።',

        // Detail View
        totalAmount: 'ጠቅላላ መጠን',
        records: 'መዝገቦች',

        // Language
        switchLanguage: 'English'
    }
};

function t(key) {
    return translations[currentLang]?.[key] || translations['en'][key] || key;
}

function toggleLanguage() {
    currentLang = currentLang === 'en' ? 'am' : 'en';
    localStorage.setItem('app_lang', currentLang);
    updateAllTranslations();
}

function updateAllTranslations() {
    // Update all elements with data-i18n attribute
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        el.textContent = t(key);
    });

    // Update placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        el.placeholder = t(key);
    });

    // Update language toggle button
    const langBtn = document.getElementById('lang-toggle');
    if (langBtn) {
        langBtn.textContent = t('switchLanguage');
    }
}

// Init
document.addEventListener('DOMContentLoaded', async () => {
    if (tg) {
        tg.ready();
        tg.expand();
        // Force dark mode colors for consistency if needed, 
        // or let CSS handle it. CSS is set to dark theme by default.
        if (tg.headerColor) tg.headerColor = '#0f172a';
        if (tg.backgroundColor) tg.backgroundColor = '#0f172a';
    }

    // Initial Feather render
    feather.replace();

    // Apply translations
    updateAllTranslations();

    // Auth
    await authenticate();
});

// Navigation
function switchTab(tabId) {
    // Update Nav Buttons
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    const btn = document.querySelector(`.nav-item[onclick="switchTab('${tabId}')"]`);
    if (btn) btn.classList.add('active');

    // Update Views
    document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
    const content = document.getElementById(`tab-${tabId}`);
    if (content) content.style.display = 'block';

    // Load Data triggers
    if (tabId === 'houses' && !housesData) loadHouses();

    window.scrollTo(0, 0);
}

// Auth Logic
async function authenticate() {
    try {
        const initData = tg?.initData || '';
        const response = await fetch(`${API_BASE}/api/auth`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Telegram-Init-Data': initData }
        });

        if (!response.ok) throw new Error('Auth Failed');

        const data = await response.json();
        currentUser = data;

        document.getElementById('loading-screen').style.display = 'none';
        document.getElementById('app').style.display = 'block';

        updateWelcomeScreen();

    } catch (e) {
        console.error(e);
        const loadingScreen = document.getElementById('loading-screen');
        const loadingText = loadingScreen?.querySelector('p');
        if (loadingText) {
            loadingText.textContent = "Authentication Failed";
            loadingText.style.color = "var(--danger)";
        }
        showToast('Authentication failed. Please try again.', 'error');
    }
}

// Welcome Screen
function updateWelcomeScreen() {
    document.getElementById('welcome-name').textContent = currentUser.user.first_name;
    const grid = document.getElementById('role-buttons');
    grid.innerHTML = '';

    // Admin Button
    if (currentUser.is_admin && currentUser.admin_groups.length > 0) {
        const group = currentUser.admin_groups[0];
        grid.innerHTML += `
            <div class="role-card" onclick="showAdminPanel(${group.id})">
                <div class="role-icon-lg"><i data-feather="briefcase"></i></div>
                <div>
                    <h3 style="margin-bottom: 4px;">${t('adminDashboard')}</h3>
                    <p class="text-muted text-sm">${group.name}</p>
                </div>
                <i data-feather="chevron-right" style="margin-left: auto; color: var(--text-tertiary);"></i>
            </div>
        `;
        currentGroupId = group.id; // Default
    }

    // Resident Button
    const userHouses = Object.entries(currentUser.user_houses || {});
    if (userHouses.length > 0) {
        const [groupId, houseNum] = userHouses[0];
        grid.innerHTML += `
            <div class="role-card" onclick="showUserPanel(${groupId})">
                <div class="role-icon-lg" style="background: rgba(16, 185, 129, 0.15); color: #10b981;">
                    <i data-feather="home"></i>
                </div>
                <div>
                    <h3 style="margin-bottom: 4px;">${t('myResidence')}</h3>
                    <p class="text-muted text-sm">${t('house')} ${houseNum}</p>
                </div>
                <i data-feather="chevron-right" style="margin-left: auto; color: var(--text-tertiary);"></i>
            </div>
        `;
    }

    feather.replace();

    // Show registration screen if user is not registered
    if (!currentUser.is_admin && userHouses.length === 0) {
        showRegistrationScreen();
        return;
    }

    // Auto-redirect if single role
    if (grid.children.length === 1 && !currentUser.is_admin && userHouses.length > 0) {
        showUserPanel(parseInt(userHouses[0][0]));
    }
}

function showWelcome() {
    hideAllViews();
    document.getElementById('welcome-screen').style.display = 'block';
    window.scrollTo(0, 0);
}

function hideAllViews() {
    document.getElementById('welcome-screen').style.display = 'none';
    document.getElementById('registration-screen').style.display = 'none';
    document.getElementById('admin-panel').style.display = 'none';
    document.getElementById('user-panel').style.display = 'none';
    document.getElementById('detail-view').style.display = 'none';
}

// ========== ADMIN PANEL ==========

async function showAdminPanel(groupId) {
    hideAllViews();
    document.getElementById('admin-panel').style.display = 'block';
    currentGroupId = groupId;

    const group = currentUser.admin_groups.find(g => g.id === groupId);
    document.getElementById('admin-group-name').textContent = group?.name || 'Admin';

    switchTab('dashboard');
    await loadDashboard();
}

async function loadDashboard() {
    try {
        const res = await fetch(`${API_BASE}/api/dashboard/${currentGroupId}`, {
            headers: { 'X-Telegram-Init-Data': tg?.initData || '' }
        });
        dashboardData = await res.json();

        // Update values
        document.getElementById('stat-total').textContent = formatCurrency(dashboardData.total_amount);
        document.getElementById('stat-houses').textContent = dashboardData.total_houses;

        // Month calc
        const curMonth = getCurrentEthiopianMonth();
        document.getElementById('stat-month').textContent = formatCurrency(dashboardData.by_month[curMonth] || 0);

        // Render Type Breakdown
        const typeList = document.getElementById('type-breakdown');
        typeList.innerHTML = '';

        for (const [type, data] of Object.entries(dashboardData.by_type)) {
            typeList.innerHTML += `
                <div class="list-item type-${type}" onclick="showTypeHouses('${type}')">
                    <div class="item-icon">${getIconForType(type)}</div>
                    <div class="item-content">
                        <div class="item-title">${data.name}</div>
                        <div class="item-subtitle">Payment Category</div>
                    </div>
                    <div class="item-trailing">
                        <div class="item-value">${formatCurrency(data.total)}</div>
                    </div>
                </div>
            `;
        }

        // Render Monthly Trends
        const monthList = document.getElementById('monthly-breakdown');
        monthList.innerHTML = '';
        const sortedMonths = Object.entries(dashboardData.by_month)
            .filter(([_, v]) => v > 0)
            .sort((a, b) => b[1] - a[1]) // highest first
            .slice(0, 5);

        for (const [m, total] of sortedMonths) {
            monthList.innerHTML += `
                <div class="list-item">
                    <div class="item-icon" style="background: var(--bg-surface-elevated); color: var(--text-secondary);">
                        <i data-feather="calendar"></i>
                    </div>
                    <div class="item-content">
                        <div class="item-title">${m}</div>
                    </div>
                    <div class="item-trailing">
                        <div class="item-value">${formatCurrency(total)}</div>
                    </div>
                </div>
            `;
        }

        feather.replace();
    } catch (e) { console.error(e); }
}

async function loadHouses() {
    const list = document.getElementById('houses-list');
    list.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-secondary);">Loading directory...</div>';

    try {
        const res = await fetch(`${API_BASE}/api/houses/${currentGroupId}`, { headers: { 'X-Telegram-Init-Data': tg?.initData || '' } });
        const data = await res.json();

        // Numeric sort
        data.houses.sort((a, b) => (parseInt(a.number) || 0) - (parseInt(b.number) || 0));
        housesData = data;

        renderHouses(housesData.houses);

        // Setup Search Listener
        document.getElementById('house-search').addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase();
            const filtered = housesData.houses.filter(h => h.number.includes(term) || (h.name && h.name.toLowerCase().includes(term)));
            renderHouses(filtered);
        });

    } catch (e) {
        list.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--danger);">Failed to load houses</div>';
    }
}

function renderHouses(houses) {
    const list = document.getElementById('houses-list');
    list.innerHTML = '';

    if (houses.length === 0) {
        list.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-secondary);">No houses found</div>';
        return;
    }

    // Render in chunks for performance if needed, but simple loop fine for <1000 items
    let html = '';
    houses.forEach(h => {
        html += `
            <div class="list-item" onclick="showDetailView('${h.number}')">
                <div class="item-icon" style="background: rgba(59, 130, 246, 0.1); color: var(--primary);">
                    <span style="font-weight: 700; font-size: 14px;">${h.number}</span>
                </div>
                <div class="item-content">
                    <div class="item-title">House ${h.number}</div>
                    <div class="item-subtitle">${h.name || 'Resident'}</div>
                </div>
                <div class="item-trailing">
                    <div class="item-value">${formatCurrency(h.total)}</div>
                    <div class="item-subvalue">${h.payments.length} txns</div>
                </div>
            </div>
        `;
    });
    list.innerHTML = html;
}

// ========== USER PANEL ==========

let userHouseData = null; // Store user's house data for filtering

async function showUserPanel(groupId) {
    hideAllViews();
    document.getElementById('user-panel').style.display = 'block';
    currentGroupId = groupId;

    try {
        const res = await fetch(`${API_BASE}/api/user/${groupId}`, { headers: { 'X-Telegram-Init-Data': tg?.initData || '' } });
        const data = await res.json();

        if (data.house) {
            userHouseData = data.house;
            const h = data.house;

            document.getElementById('user-house-number').textContent = `House ${h.number}`;
            document.getElementById('user-total').textContent = formatCurrency(h.total);

            // Build payment type tabs
            renderUserTypeTabs(h.payments);

            // Render month grid for all types
            renderUserMonthGrid(h.payments, 'all');

            // Render payment history
            renderUserPaymentHistory(h.payments);

            // Check for last submission (edit mode)
            checkLastSubmission(groupId);

            feather.replace();
        }
    } catch (e) { console.error(e); }
}

async function checkLastSubmission(groupId) {
    try {
        const res = await fetch(`${API_BASE}/api/last-submission/${groupId}`, {
            headers: { 'X-Telegram-Init-Data': tg?.initData || '' }
        });
        const data = await res.json();

        const editBtn = document.getElementById('btn-edit-last');
        if (editBtn) {
            if (data.has_submission) {
                editBtn.style.display = 'flex';
            } else {
                editBtn.style.display = 'none';
            }
        }
    } catch (e) {
        console.error('Error checking last submission:', e);
    }
}

async function editLastPayment() {
    try {
        const res = await fetch(`${API_BASE}/api/last-submission/${currentGroupId}`, {
            headers: { 'X-Telegram-Init-Data': tg?.initData || '' }
        });
        const data = await res.json();

        if (!data.has_submission) {
            showToast('No previous submission found', 'error');
            return;
        }

        // Enable edit mode
        window.isEditMode = true;

        // Show payment view
        showPaymentView();

        // Pre-fill form with last submission data
        const submission = data.submission;
        document.getElementById('input-house').value = submission.house_number;
        document.getElementById('input-type').value = submission.payment_type;
        document.getElementById('input-month').value = submission.month;

        // Show edit mode indicator
        const editIndicator = document.getElementById('edit-mode-indicator');
        if (editIndicator) {
            editIndicator.style.display = 'block';
        }

        // Lookup house
        lookupHouse();

        showToast('Edit mode enabled. You can modify your last payment.', 'warning');
    } catch (e) {
        console.error('Error loading last submission:', e);
        showToast('Error loading last submission', 'error');
    }
}

function renderUserTypeTabs(payments) {
    const tabs = document.getElementById('user-type-tabs');

    // Get unique payment types from user's payments
    const types = [...new Set(payments.map(p => p.type))];

    // Type display names
    const typeNames = {
        water: 'ውሃ',
        electricity: 'መብራት',
        development: 'ልማት',
        penalty: 'ቅጣት',
        other: 'ሌላ'
    };

    tabs.innerHTML = `<button class="type-tab active" data-type="all" onclick="filterUserMonths('all')">All</button>`;

    types.forEach(type => {
        tabs.innerHTML += `<button class="type-tab" data-type="${type}" onclick="filterUserMonths('${type}')">${typeNames[type] || type}</button>`;
    });
}

function filterUserMonths(type) {
    // Update active tab
    document.querySelectorAll('.type-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.type-tab[data-type="${type}"]`)?.classList.add('active');

    // Re-render grid with filter
    if (userHouseData) {
        renderUserMonthGrid(userHouseData.payments, type);
        feather.replace();
    }
}

function renderUserMonthGrid(payments, typeFilter) {
    const grid = document.getElementById('user-months');
    grid.innerHTML = '';

    const allMonths = ['Meskerem', 'Tikimt', 'Hidar', 'Tahsas', 'Tir', 'Yekatit', 'Megabit', 'Miyazya', 'Ginbot', 'Sene', 'Hamle', 'Nehase'];

    // Filter payments by type if not 'all'
    const filteredPayments = typeFilter === 'all'
        ? payments
        : payments.filter(p => p.type === typeFilter);

    // Get months that have payments (for this type)
    const paidMonths = new Set(filteredPayments.map(p => p.month));

    allMonths.forEach(m => {
        const paid = paidMonths.has(m);

        // Find payment details for this month (if any)
        const monthPayment = filteredPayments.find(p => p.month === m);
        const amount = monthPayment ? formatCurrency(monthPayment.amount) : '';

        grid.innerHTML += `
            <div class="month-cell">
                <div class="month-badge ${paid ? 'paid' : 'unpaid'}">
                    ${paid ? `<i data-feather="check" style="width: 16px;"></i>` : `<i data-feather="x" style="width: 14px;"></i>`}
                </div>
                <div class="month-label">${m.substring(0, 3)}</div>
                ${paid && amount ? `<div style="font-size: 10px; color: var(--success); margin-top: 2px;">${amount}</div>` : ''}
            </div>
        `;
    });
}

function renderUserPaymentHistory(payments) {
    const history = document.getElementById('user-payments');
    history.innerHTML = '';

    if (payments.length === 0) {
        history.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--text-secondary);">No payments yet</div>';
    } else {
        payments.forEach(p => {
            history.innerHTML += `
                <div class="list-item type-${p.type}">
                    <div class="item-icon">${getIconForType(p.type)}</div>
                    <div class="item-content">
                        <div class="item-title">${p.type_amharic}</div>
                        <div class="item-subtitle">${p.month} • ${p.month_amharic}</div>
                    </div>
                    <div class="item-trailing">
                        <div class="item-value">${formatCurrency(p.amount)}</div>
                    </div>
                </div>
            `;
        });
    }
}

// ========== DETAIL VIEW & FILTERS ==========

function showDetailView(houseNumber, typeFilter = null) {
    if (!housesData) return;
    const house = housesData.houses.find(h => h.number === houseNumber);
    if (!house) return;

    document.getElementById('detail-view').style.display = 'block';

    // Header
    document.getElementById('detail-title').textContent = `House ${houseNumber}`;

    // Filter payments
    let payments = house.payments;
    let total = house.total;

    if (typeFilter) {
        payments = payments.filter(p => p.type === typeFilter);
        total = payments.reduce((sum, p) => sum + p.amount, 0);
        document.getElementById('detail-title').textContent = `${houseNumber} - ${typeFilter}`;
    }

    document.getElementById('detail-total').textContent = formatCurrency(total);

    const list = document.getElementById('detail-list');
    list.innerHTML = '';

    payments.forEach(p => {
        list.innerHTML += `
            <div class="list-item type-${p.type}">
                 <div class="item-icon">${getIconForType(p.type)}</div>
                 <div class="item-content">
                    <div class="item-title">${p.month_amharic} (${p.month})</div>
                    <div class="item-subtitle">${p.type_amharic}</div>
                 </div>
                 <div class="item-trailing">
                    <div class="item-value">${formatCurrency(p.amount)}</div>
                    <div class="item-subvalue">${p.txid || ''}</div>
                 </div>
            </div>
        `;
    });

    feather.replace();
}

function hideDetailView() {
    document.getElementById('detail-view').style.display = 'none';
}

function showTypeHouses(type) {
    if (!housesData) { loadHouses().then(() => showTypeHouses(type)); return; }

    // Filter
    const filtered = housesData.houses.filter(h => h.payments.some(p => p.type === type));

    // Reuse detail view as a list view for the type
    document.getElementById('detail-view').style.display = 'block';
    document.getElementById('detail-title').textContent = `${dashboardData.by_type[type].name}`;

    const list = document.getElementById('detail-list');
    list.innerHTML = '';

    // Calculate total for this type
    const totalType = filtered.reduce((acc, h) => acc + h.payments.filter(p => p.type === type).reduce((s, x) => s + x.amount, 0), 0);
    document.getElementById('detail-total').textContent = formatCurrency(totalType);

    filtered.sort((a, b) => (parseInt(a.number) || 0) - (parseInt(b.number) || 0));

    filtered.forEach(h => {
        const pTotal = h.payments.filter(p => p.type === type).reduce((s, x) => s + x.amount, 0);
        list.innerHTML += `
            <div class="list-item" onclick="showDetailView('${h.number}', '${type}')">
                <div class="item-icon"><i data-feather="home"></i></div>
                <div class="item-content">
                    <div class="item-title">House ${h.number}</div>
                    <div class="item-subtitle">${h.name || 'Resident'}</div>
                </div>
                <div class="item-trailing">
                    <div class="item-value">${formatCurrency(pTotal)}</div>
                </div>
            </div>
        `;
    });
    feather.replace();
}

// ========== TOAST NOTIFICATIONS ==========
function showToast(message, type = 'success', duration = 3000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icon = type === 'success' ? 'check-circle' : type === 'error' ? 'alert-circle' : 'info';
    toast.innerHTML = `
        <i data-feather="${icon}" style="width: 20px; height: 20px;"></i>
        <span>${message}</span>
    `;

    container.appendChild(toast);
    feather.replace();

    setTimeout(() => toast.classList.add('show'), 10);

    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// ========== DRAG AND DROP ==========
function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    const uploadArea = document.getElementById('upload-area');
    if (uploadArea) {
        uploadArea.classList.add('dragover');
    }
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    const uploadArea = document.getElementById('upload-area');
    if (uploadArea) {
        uploadArea.classList.remove('dragover');
    }
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    const uploadArea = document.getElementById('upload-area');
    if (uploadArea) {
        uploadArea.classList.remove('dragover');
    }

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        const file = files[0];
        if (file.type.startsWith('image/')) {
            const input = document.getElementById('receipt-input');
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            input.files = dataTransfer.files;
            handleReceiptUpload({ target: input });
        } else {
            showToast('Please upload an image file', 'error');
        }
    }
}

// ========== LOADING STATES ==========
function setLoading(elementId, isLoading) {
    const element = document.getElementById(elementId);
    if (!element) return;

    if (isLoading) {
        element.disabled = true;
        element.style.opacity = '0.6';
        element.style.pointerEvents = 'none';
    } else {
        element.disabled = false;
        element.style.opacity = '1';
        element.style.pointerEvents = 'auto';
    }
}

function showProgress(progress) {
    const progressBar = document.getElementById('submit-progress');
    const progressFill = progressBar?.querySelector('.progress-fill');
    if (progressBar && progressFill) {
        progressBar.style.display = 'block';
        progressFill.style.width = `${progress}%`;
    }
}

function hideProgress() {
    const progressBar = document.getElementById('submit-progress');
    if (progressBar) {
        progressBar.style.display = 'none';
    }
}

// ========== HELPERS ==========
function formatCurrency(val) {
    if (!val || isNaN(val)) return '0 ETB';
    return new Intl.NumberFormat('en-US', {
        style: 'currency', currency: 'ETB', maximumFractionDigits: 0
    }).format(val);
}

function getIconForType(type) {
    const map = {
        water: 'droplet', electricity: 'zap', development: 'trending-up', penalty: 'alert-triangle', other: 'list'
    };
    const icon = map[type] || 'file-text';
    return `<i data-feather="${icon}"></i>`;
}

function getCurrentEthiopianMonth() {
    const months = ['Tir', 'Yekatit', 'Megabit', 'Miyazya', 'Ginbot', 'Sene', 'Hamle', 'Nehase', 'Pagume', 'Meskerem', 'Tikimt', 'Hidar', 'Tahsas'];
    return months[new Date().getMonth()];
}


// ========== PAYMENT SUBMISSION ==========

let currentReceiptData = null;
let currentReceiptId = null;

function showPaymentView() {
    document.getElementById('payment-view').style.display = 'block';
    goToPaymentStep(1);
    loadPaymentFormData();
    feather.replace();
}

function hidePaymentView() {
    document.getElementById('payment-view').style.display = 'none';
    resetPaymentForm();

    // Refresh user panel to show new payment
    if (currentGroupId) {
        showUserPanel(currentGroupId);
    }
}

function goToPaymentStep(step) {
    document.getElementById('payment-step-1').style.display = 'none';
    document.getElementById('payment-step-loading').style.display = 'none';
    document.getElementById('payment-step-2').style.display = 'none';
    document.getElementById('payment-step-success').style.display = 'none';

    if (step === 1) {
        document.getElementById('payment-step-1').style.display = 'block';
    } else if (step === 'loading') {
        document.getElementById('payment-step-loading').style.display = 'block';
    } else if (step === 2) {
        document.getElementById('payment-step-2').style.display = 'block';
    } else if (step === 'success') {
        document.getElementById('payment-step-success').style.display = 'block';
    }

    feather.replace();
}

function resetPaymentForm() {
    currentReceiptData = null;
    currentReceiptId = null;
    window.extractedReceiptData = {};
    window.isEditMode = false;

    const receiptImage = document.getElementById('receipt-image');
    const receiptPreview = document.getElementById('receipt-preview');
    const uploadArea = document.getElementById('upload-area');
    const continueBtn = document.getElementById('btn-continue-step1');
    const inputHouse = document.getElementById('input-house');
    const inputType = document.getElementById('input-type');
    const inputMonth = document.getElementById('input-month');
    const nameDisplay = document.getElementById('house-name-display');
    const errorDisplay = document.getElementById('house-error');
    const errorsEl = document.getElementById('form-errors');
    const successEl = document.getElementById('form-success');
    const editIndicator = document.getElementById('edit-mode-indicator');
    const beneficiaryEl = document.getElementById('extracted-beneficiary');

    if (receiptImage) receiptImage.src = '';
    if (receiptPreview) receiptPreview.style.display = 'none';
    if (uploadArea) {
        uploadArea.style.display = 'block';
        uploadArea.classList.remove('dragover');
    }
    if (continueBtn) {
        continueBtn.style.opacity = '0.5';
        continueBtn.style.pointerEvents = 'none';
    }
    if (inputHouse) inputHouse.value = '';
    if (inputType) inputType.value = '';
    if (inputMonth) inputMonth.value = '';
    if (nameDisplay) nameDisplay.style.display = 'none';
    if (errorDisplay) errorDisplay.style.display = 'none';
    if (errorsEl) errorsEl.style.display = 'none';
    if (successEl) successEl.style.display = 'none';
    if (editIndicator) editIndicator.style.display = 'none';
    if (beneficiaryEl) beneficiaryEl.innerHTML = '';

    hideProgress();
}

async function loadPaymentFormData() {
    // Load payment types
    try {
        const res = await fetch(`${API_BASE}/api/payment-types`);
        const data = await res.json();

        const typeSelect = document.getElementById('input-type');
        typeSelect.innerHTML = '<option value="">Select type...</option>';
        data.types.forEach(t => {
            typeSelect.innerHTML += `<option value="${t.id}">${t.name} (${t.english})</option>`;
        });
    } catch (e) { console.error(e); }

    // Load months
    try {
        const res = await fetch(`${API_BASE}/api/months`);
        const data = await res.json();

        const monthSelect = document.getElementById('input-month');
        monthSelect.innerHTML = '<option value="">Select month...</option>';
        data.months.forEach(m => {
            monthSelect.innerHTML += `<option value="${m.english}">${m.amharic} (${m.english})</option>`;
        });
    } catch (e) { console.error(e); }
}

function handleReceiptUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
        showToast('Please upload an image file', 'error');
        return;
    }

    // Validate file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
        showToast('Image size should be less than 10MB', 'error');
        return;
    }

    const reader = new FileReader();
    reader.onload = function (e) {
        currentReceiptData = e.target.result;
        const preview = document.getElementById('receipt-image');
        const previewContainer = document.getElementById('receipt-preview');
        const uploadArea = document.getElementById('upload-area');
        const continueBtn = document.getElementById('btn-continue-step1');

        if (preview) {
            preview.src = currentReceiptData;
            preview.onload = function () {
                previewContainer.style.display = 'block';
                previewContainer.style.animation = 'fadeInUp var(--transition-base)';
            };
        }

        // Hide upload area after image is selected
        if (uploadArea) {
            uploadArea.style.display = 'none';
        }

        // Enable Continue button
        if (continueBtn) {
            continueBtn.style.opacity = '1';
            continueBtn.style.pointerEvents = 'auto';
            continueBtn.style.cursor = 'pointer';
        }

        showToast('Receipt image loaded successfully', 'success', 2000);
    };

    reader.onerror = function () {
        showToast('Error reading file', 'error');
    };

    reader.readAsDataURL(file);
}

async function processReceipt() {
    if (!currentReceiptData) {
        showToast('Please upload a receipt image first', 'error');
        return;
    }

    goToPaymentStep('loading');
    showProgress(30);

    try {
        showProgress(50);
        const res = await fetch(`${API_BASE}/api/upload-receipt/${currentGroupId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Telegram-Init-Data': tg?.initData || ''
            },
            body: JSON.stringify({ image: currentReceiptData })
        });

        showProgress(80);
        const data = await res.json();

        if (data.success) {
            showProgress(100);
            currentReceiptId = data.receipt_id;
            const extracted = data.extracted || {};

            // Show extracted data
            const amountEl = document.getElementById('extracted-amount');
            const txidEl = document.getElementById('extracted-txid');
            const beneficiaryEl = document.getElementById('extracted-beneficiary');

            if (amountEl) {
                amountEl.textContent = extracted.amount ? formatCurrency(parseFloat(extracted.amount)) : 'Not detected';
                if (!extracted.amount) {
                    amountEl.style.color = 'var(--warning)';
                }
            }

            if (txidEl) {
                if (extracted.transaction_id) {
                    txidEl.innerHTML = `
                        <div style="display: flex; align-items: center; gap: 6px;">
                            <i data-feather="check-circle" style="width: 14px; height: 14px; color: var(--success);"></i>
                            <span>TXN: ${extracted.transaction_id}</span>
                        </div>
                    `;
                    txidEl.style.color = 'var(--success)';
                } else {
                    txidEl.innerHTML = `
                        <div style="display: flex; align-items: center; gap: 6px;">
                            <i data-feather="alert-circle" style="width: 14px; height: 14px; color: var(--warning);"></i>
                            <span style="color: var(--warning);">TXN: Not detected (will proceed without TXID)</span>
                        </div>
                    `;
                    txidEl.style.color = 'var(--warning)';
                }
                feather.replace();
            }

            // Show beneficiary validation
            if (beneficiaryEl) {
                if (extracted.beneficiary) {
                    const isValid = extracted.beneficiary_valid;
                    beneficiaryEl.innerHTML = `
                        <div style="display: flex; align-items: center; gap: 8px; margin-top: 8px;">
                            <i data-feather="${isValid ? 'check-circle' : 'alert-circle'}" style="width: 16px; height: 16px; color: ${isValid ? 'var(--success)' : 'var(--danger)'};"></i>
                            <span style="color: ${isValid ? 'var(--success)' : 'var(--danger)'}; font-size: 13px;">
                                ${isValid ? 'Valid beneficiary' : 'Invalid beneficiary: ' + (extracted.beneficiary || 'Not found')}
                            </span>
                        </div>
                    `;
                    feather.replace();
                } else {
                    beneficiaryEl.innerHTML = `
                        <div style="display: flex; align-items: center; gap: 8px; margin-top: 8px;">
                            <i data-feather="alert-circle" style="width: 16px; height: 16px; color: var(--warning);"></i>
                            <span style="color: var(--warning); font-size: 13px;">Beneficiary not found on receipt</span>
                        </div>
                    `;
                    feather.replace();
                }
            }

            // Store extracted data
            window.extractedReceiptData = {
                amount: extracted.amount || '',
                transaction_id: extracted.transaction_id || '',
                payer_name: extracted.payer_name || '',
                beneficiary: extracted.beneficiary || '',
                beneficiary_valid: extracted.beneficiary_valid || false,
                beneficiary_normalized: extracted.beneficiary_normalized || ''
            };

            // Pre-fill form if data available
            if (extracted.amount) {
                showToast('Receipt processed successfully', 'success');
            } else {
                showToast('Receipt processed, but some data may need manual entry', 'warning');
            }

            setTimeout(() => {
                hideProgress();
                goToPaymentStep(2);
            }, 500);
        } else {
            hideProgress();
            showToast('Failed to process receipt: ' + (data.error || 'Unknown error'), 'error');
            goToPaymentStep(1);
        }

    } catch (e) {
        console.error(e);
        hideProgress();
        showToast('Network error. Please check your connection and try again', 'error');
        goToPaymentStep(1);
    }
}

let houseLookupTimeout = null;

async function lookupHouse() {
    const houseNumber = document.getElementById('input-house').value.trim();
    const nameDisplay = document.getElementById('house-name-display');
    const errorDisplay = document.getElementById('house-error');
    const successEl = document.getElementById('form-success');

    if (nameDisplay) nameDisplay.style.display = 'none';
    if (errorDisplay) errorDisplay.style.display = 'none';
    if (successEl) successEl.style.display = 'none';

    if (houseNumber.length < 3) return;

    // Debounce
    clearTimeout(houseLookupTimeout);
    houseLookupTimeout = setTimeout(async () => {
        try {
            const res = await fetch(`${API_BASE}/api/lookup-house/${currentGroupId}/${houseNumber}`, {
                headers: { 'X-Telegram-Init-Data': tg?.initData || '' }
            });
            const data = await res.json();

            if (data.found) {
                const nameText = document.getElementById('house-name-text');
                if (nameText) {
                    nameText.textContent = data.name || data.owner || 'Resident';
                }
                if (nameDisplay) {
                    nameDisplay.style.display = 'flex';
                    nameDisplay.style.alignItems = 'center';
                    nameDisplay.style.gap = '6px';
                    nameDisplay.style.animation = 'fadeInUp var(--transition-base)';
                }
                if (successEl) {
                    successEl.textContent = `✓ House found: ${data.name || data.owner || 'Resident'}`;
                    successEl.style.display = 'block';
                }
            } else {
                if (errorDisplay) {
                    errorDisplay.textContent = 'House not in registry (will be added)';
                    errorDisplay.style.display = 'block';
                    errorDisplay.style.color = 'var(--warning)';
                }
            }

            feather.replace();
        } catch (e) {
            console.error(e);
            if (errorDisplay) {
                errorDisplay.textContent = 'Error looking up house';
                errorDisplay.style.display = 'block';
            }
        }
    }, 300);
}

async function submitPayment() {
    const houseNumber = document.getElementById('input-house').value.trim();
    const paymentType = document.getElementById('input-type').value;
    const month = document.getElementById('input-month').value;
    const errorsEl = document.getElementById('form-errors');
    const successEl = document.getElementById('form-success');
    const submitBtn = document.getElementById('btn-submit-payment');

    // Clear previous messages
    if (errorsEl) errorsEl.style.display = 'none';
    if (successEl) successEl.style.display = 'none';

    // Enhanced validation
    const errors = [];
    if (!houseNumber) {
        errors.push(t('houseNumberRequired'));
    } else if (!/^\d{3,4}$/.test(houseNumber)) {
        errors.push('House number must be 3-4 digits');
    }

    if (!paymentType) {
        errors.push(t('paymentTypeRequired'));
    }

    if (!month) {
        errors.push(t('monthRequired'));
    }

    // Transaction ID is optional - show warning if missing but allow submission
    const extracted = window.extractedReceiptData || {};
    if (!extracted.transaction_id || extracted.transaction_id === 'N/A') {
        // Show warning but don't block submission
        const txidEl = document.getElementById('extracted-txid');
        if (txidEl && !txidEl.innerHTML.includes('Not detected')) {
            // Already shown during receipt processing
        }
    }

    if (errors.length > 0) {
        if (errorsEl) {
            errorsEl.innerHTML = errors.map(e => `• ${e}`).join('<br>');
            errorsEl.style.display = 'block';
        }
        showToast('Please fill all required fields', 'error');
        return;
    }

    // Disable submit button
    setLoading('btn-submit-payment', true);
    showProgress(20);
    goToPaymentStep('loading');

    try {
        const extracted = window.extractedReceiptData || {};
        // Use empty string instead of 'N/A' for missing TXID
        const txid = extracted.transaction_id && extracted.transaction_id !== 'N/A'
            ? extracted.transaction_id
            : '';

        const payload = {
            house_number: houseNumber,
            payment_type: paymentType,
            month: month,
            amount: extracted.amount || 0,
            transaction_id: txid,
            payer_name: extracted.payer_name || '',
            receipt_id: currentReceiptId,
            is_edit_mode: window.isEditMode || false,
            beneficiary: extracted.beneficiary || '',
            beneficiary_valid: extracted.beneficiary_valid || false
        };

        showProgress(50);
        const res = await fetch(`${API_BASE}/api/submit-payment/${currentGroupId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Telegram-Init-Data': tg?.initData || ''
            },
            body: JSON.stringify(payload)
        });

        showProgress(80);
        const data = await res.json();

        if (data.success) {
            showProgress(100);
            const successMsg = document.getElementById('success-message');
            if (successMsg) {
                successMsg.textContent = `House ${houseNumber} - ${paymentType} - ${month}`;
            }

            // Clear edit mode
            window.isEditMode = false;

            showToast('Payment submitted successfully!', 'success');

            // Refresh last submission check
            if (currentGroupId) {
                checkLastSubmission(currentGroupId);
            }

            setTimeout(() => {
                hideProgress();
                goToPaymentStep('success');
            }, 500);
        } else {
            hideProgress();
            const errorMsgs = data.errors?.map(e => e.message).join('<br>') || 'Submission failed';
            if (errorsEl) {
                errorsEl.innerHTML = errorMsgs.split('\n').map(e => `• ${e}`).join('<br>');
                errorsEl.style.display = 'block';
            }
            showToast('Failed to submit payment. Please check the errors below', 'error');
            goToPaymentStep(2);
        }

    } catch (e) {
        console.error(e);
        hideProgress();
        const errorMsg = 'Network error. Please check your connection and try again.';
        if (errorsEl) {
            errorsEl.textContent = errorMsg;
            errorsEl.style.display = 'block';
        }
        showToast(errorMsg, 'error');
        goToPaymentStep(2);
    } finally {
        setLoading('btn-submit-payment', false);
    }
}

// ========== USER REGISTRATION ==========

function showRegistrationScreen() {
    hideAllViews();
    document.getElementById('registration-screen').style.display = 'block';

    // Check if already has pending request
    checkPendingRegistration();

    // Setup form handler
    const form = document.getElementById('registration-form');
    if (form) {
        form.onsubmit = handleRegistrationSubmit;
    }

    feather.replace();
}

async function checkPendingRegistration() {
    try {
        const res = await fetch(`${API_BASE}/api/check-registration-status`, {
            headers: { 'X-Telegram-Init-Data': tg?.initData || '' }
        });
        const data = await res.json();

        if (data.has_pending) {
            const pendingEl = document.getElementById('reg-pending');
            if (pendingEl) {
                pendingEl.style.display = 'block';
            }
            // Disable submit button
            const btn = document.getElementById('btn-register');
            if (btn) {
                btn.disabled = true;
                btn.style.opacity = '0.5';
                btn.style.pointerEvents = 'none';
            }
        }
    } catch (e) {
        console.error('Error checking pending:', e);
    }
}

async function handleRegistrationSubmit(e) {
    e.preventDefault();

    const houseNumber = document.getElementById('reg-house').value.trim();
    const residentName = document.getElementById('reg-name').value.trim();
    const errorEl = document.getElementById('reg-error');
    const btn = document.getElementById('btn-register');

    // Clear previous errors
    if (errorEl) errorEl.style.display = 'none';

    // Validate
    if (!houseNumber || !residentName) {
        if (errorEl) {
            errorEl.textContent = 'Please fill in all fields';
            errorEl.style.display = 'block';
        }
        return;
    }

    // Validate house number is numeric
    if (!/^\d{3,4}$/.test(houseNumber)) {
        if (errorEl) {
            errorEl.innerHTML = `
                <strong>Invalid house number</strong><br>
                Please enter only the house number (e.g., 407)<br>
                <span style="font-size: 13px;">❌ Do NOT include "Block 22" or any text</span>
            `;
            errorEl.style.display = 'block';
        }
        return;
    }

    // Get group ID (use first admin group or default)
    const groupId = currentUser.admin_groups?.[0]?.id || Object.keys(currentUser.groups || {})[0] || -1003290908954;

    try {
        setLoading('btn-register', true);

        const res = await fetch(`${API_BASE}/api/request-access/${groupId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Telegram-Init-Data': tg?.initData || ''
            },
            body: JSON.stringify({
                house_number: houseNumber,
                resident_name: residentName
            })
        });

        const data = await res.json();

        if (res.ok && data.success) {
            // Show success message
            const pendingEl = document.getElementById('reg-pending');
            if (pendingEl) {
                pendingEl.style.display = 'block';
            }

            // Disable form
            btn.disabled = true;
            btn.style.opacity = '0.5';
            btn.style.pointerEvents = 'none';
            document.getElementById('reg-house').disabled = true;
            document.getElementById('reg-name').disabled = true;

            showToast('Registration request submitted successfully!', 'success');

        } else {
            // Show error
            if (errorEl) {
                errorEl.textContent = data.error || 'Failed to submit request';
                errorEl.style.display = 'block';
            }
            showToast(data.error || 'Failed to submit request', 'error');
        }

    } catch (e) {
        console.error(e);
        if (errorEl) {
            errorEl.textContent = 'Network error. Please try again.';
            errorEl.style.display = 'block';
        }
        showToast('Network error. Please try again.', 'error');
    } finally {
        setLoading('btn-register', false);
    }
}


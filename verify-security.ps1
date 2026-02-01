# ============================================
# PRE-PUSH SECURITY VERIFICATION SCRIPT
# ============================================
# Run this script before pushing to GitHub
# ============================================

Write-Host ""
Write-Host "SECURITY CHECK - Verifying Repository Safety" -ForegroundColor Cyan
Write-Host ""

$errors = 0
$warnings = 0

# 1. CHECK .gitignore EXISTS
Write-Host "1. Checking .gitignore exists..." -ForegroundColor Yellow
if (Test-Path ".gitignore") {
    Write-Host "   OK: .gitignore found" -ForegroundColor Green
} else {
    Write-Host "   ERROR: .gitignore not found!" -ForegroundColor Red
    $errors++
}

# 2. VERIFY SENSITIVE FILES ARE IGNORED
Write-Host ""
Write-Host "2. Verifying sensitive files are properly ignored..." -ForegroundColor Yellow

$sensitiveFiles = @(
    "credentials.json",
    "token.txt",
    ".env",
    "groups.json",
    "houses.json"
)

foreach ($file in $sensitiveFiles) {
    $status = git check-ignore $file 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   OK: $file is ignored" -ForegroundColor Green
    } else {
        Write-Host "   WARNING: $file might not be ignored!" -ForegroundColor Yellow
        $warnings++
    }
}

# 3. CHECK FOR STAGED SENSITIVE FILES
Write-Host ""
Write-Host "3. Checking for accidentally staged sensitive files..." -ForegroundColor Yellow

$stagedFiles = git diff --cached --name-only 2>$null

$foundDangerous = $false
foreach ($staged in $stagedFiles) {
    if ($staged -match "credentials\.json|token\.txt|^\.env$|^groups\.json$|^houses\.json$|\.session$") {
        Write-Host "   DANGER: Sensitive file staged: $staged" -ForegroundColor Red
        $errors++
        $foundDangerous = $true
    }
}

if (-not $foundDangerous) {
    Write-Host "   OK: No sensitive files staged" -ForegroundColor Green
}

# 4. VERIFY EXAMPLE FILES EXIST
Write-Host ""
Write-Host "4. Verifying template files exist..." -ForegroundColor Yellow

$requiredTemplates = @(
    ".env.example",
    "groups.json.example",
    "houses.json.example"
)

foreach ($template in $requiredTemplates) {
    if (Test-Path $template) {
        Write-Host "   OK: $template exists" -ForegroundColor Green
    } else {
        Write-Host "   ERROR: $template missing!" -ForegroundColor Red
        $errors++
    }
}

# 5. CHECK GIT HISTORY FOR SENSITIVE FILES
Write-Host ""
Write-Host "5. Checking git history for sensitive files..." -ForegroundColor Yellow

$historyFiles = @(
    "credentials.json",
    "token.txt",
    ".env"
)

$foundInHistory = $false
foreach ($file in $historyFiles) {
    $history = git log --all --full-history -- $file 2>$null
    if ($history) {
        Write-Host "   CRITICAL: $file found in git history!" -ForegroundColor Red
        Write-Host "      You MUST clean git history before pushing!" -ForegroundColor Red
        $errors++
        $foundInHistory = $true
    }
}

if (-not $foundInHistory) {
    Write-Host "   OK: No sensitive files in git history" -ForegroundColor Green
}

# FINAL REPORT
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "SECURITY CHECK COMPLETE" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Errors:   $errors" -ForegroundColor $(if ($errors -eq 0) { "Green" } else { "Red" })
Write-Host "Warnings: $warnings" -ForegroundColor $(if ($warnings -eq 0) { "Green" } else { "Yellow" })

if ($errors -eq 0 -and $warnings -eq 0) {
    Write-Host ""
    Write-Host "ALL CHECKS PASSED - Safe to push to GitHub!" -ForegroundColor Green
    Write-Host ""
    exit 0
} elseif ($errors -eq 0) {
    Write-Host ""
    Write-Host "WARNINGS FOUND - Review before pushing" -ForegroundColor Yellow
    Write-Host ""
    exit 0
} else {
    Write-Host ""
    Write-Host "ERRORS FOUND - DO NOT PUSH TO GITHUB!" -ForegroundColor Red
    Write-Host "Fix all errors before pushing to repository." -ForegroundColor Red
    Write-Host ""
    exit 1
}

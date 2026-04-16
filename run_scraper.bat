@echo off
REM ══════════════════════════════════════════════════════════
REM  Work Truck Depot — Weekly Market Intelligence Scraper
REM  Double-click to run manually, or schedule via Task Scheduler
REM
REM  One-time setup (run once in terminal):
REM    pip install -r Scraper\requirements.txt
REM    python -m playwright install chromium
REM
REM  To schedule weekly (run as Administrator in cmd):
REM    schtasks /create /tn "WTD Market Scraper" ^
REM      /tr "C:\Users\marti\Desktop\Work\Work Truck Depot\run_scraper.bat" ^
REM      /sc WEEKLY /d MON /st 06:00 /ru SYSTEM /rl HIGHEST /f
REM ══════════════════════════════════════════════════════════

setlocal

set "BASE=C:\Users\marti\Desktop\Work\Work Truck Depot"
set "SCRAPER=%BASE%\Scraper\scrape.py"
set "LOG=%BASE%\Scraper\scrape.log"

echo.
echo [%date% %time%] WTD Market Scraper starting...
echo [%date% %time%] WTD Market Scraper starting... >> "%LOG%"

REM Check Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Install Python 3 and add it to PATH.
    echo ERROR: Python not found >> "%LOG%"
    pause
    exit /b 1
)

REM Run the scraper
cd /d "%BASE%\Scraper"
python scrape.py

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Scraper exited with code %errorlevel%. Check Scraper\scrape.log for details.
    echo [%date% %time%] ERROR: exit code %errorlevel% >> "%LOG%"
    pause
    exit /b %errorlevel%
)

echo.
echo Done! Dashboard updated: %BASE%\multi_source_dashboard.html
echo Opening dashboard...
start "" "%BASE%\multi_source_dashboard.html"

exit /b 0

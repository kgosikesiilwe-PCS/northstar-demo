@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 START_HERE.py
  pause
  exit /b
)
where python >nul 2>nul
if %errorlevel%==0 (
  python START_HERE.py
  pause
  exit /b
)
echo Python 3 is not installed. Install it from https://www.python.org/downloads/ and run this again.
pause

@echo off
cd /d "%~dp0"

echo ============================================================
echo  Screen Translator
echo ============================================================
echo.
echo  Launching mode selector...
echo  (use --continuous or --study to skip this dialog)
echo ============================================================

python main.py
pause

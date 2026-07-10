@echo off
cd /d "%~dp0"
echo ============================================================
echo  Screen Translator - Build Script
echo ============================================================
echo.

echo [1/3] Installing dependencies...
pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [2/3] Clearing previous build...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

echo.
echo [3/3] Building executable with PyInstaller...
pyinstaller --noconfirm screen_translator.spec
if %ERRORLEVEL% neq 0 (
    echo ERROR: Build failed.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ============================================================
echo  Build complete!
echo  Output: dist\ScreenTranslator\
echo.
echo  To distribute: zip the dist\ScreenTranslator folder
echo  To run:       dist\ScreenTranslator\ScreenTranslator.exe
echo ============================================================
echo.
echo  Launching modes:
echo    --continuous  (default)  Real-time overlay mode
echo    --study                  Manual capture with history
echo ============================================================
pause

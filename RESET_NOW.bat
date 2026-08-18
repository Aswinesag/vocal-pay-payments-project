@echo off
setlocal
cd /d "%~dp0"

echo.
echo ========================================
echo   VocalPay Database Reset Utility
echo ========================================
echo.
echo This operation permanently deletes all VocalPay records.
echo Stop the FastAPI server before continuing.
echo.
pause

if exist "venv311\Scripts\python.exe" (
    set "PYTHON=venv311\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

echo Resetting the database configured by app.core.config.settings...
"%PYTHON%" reset_db.py
if errorlevel 1 (
    echo.
    echo ERROR: Database reset failed.
    exit /b 1
)

echo.
echo Verifying database record counts...
"%PYTHON%" verify_database.py
if errorlevel 1 (
    echo.
    echo ERROR: Database verification failed.
    exit /b 1
)

echo.
echo ========================================
echo   Database reset completed successfully
echo ========================================
echo.
echo Restart the server with:
echo uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
echo.
pause
endlocal

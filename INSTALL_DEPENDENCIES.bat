@echo off
echo ================================================================
echo VocalPay Dependency Installation Script
echo ================================================================
echo.

echo Installing required packages...
python -m pip install --upgrade pip
pip install faiss-cpu==1.8.0
pip install passlib[bcrypt]==1.7.4
pip install python-jose[cryptography]==3.3.0
pip install jinja2==3.1.4

echo.
echo ================================================================
echo Installation Complete - Verifying...
echo ================================================================
echo.

python -c "import faiss; print('✅ FAISS installed')" 2>&1
python -c "import passlib; print('✅ passlib installed')" 2>&1
python -c "import jose; print('✅ python-jose installed')" 2>&1
python -c "import jinja2; print('✅ Jinja2 installed')" 2>&1

echo.
echo ================================================================
echo All dependencies verified successfully!
echo You can now start the server with:
echo   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
echo ================================================================
pause

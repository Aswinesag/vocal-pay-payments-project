# VocalPay Startup Troubleshooting Guide

## Current Issue: Application Won't Start

### Step 1: Install Missing Dependencies

Run the installation script:
```bash
INSTALL_DEPENDENCIES.bat
```

Or manually install:
```bash
pip install faiss-cpu==1.8.0
pip install passlib[bcrypt]==1.7.4
pip install python-jose[cryptography]==3.3.0
pip install jinja2==3.1.4
```

### Step 2: Database Migration (Add hashed_password column)

The `User` table now requires a `hashed_password` column. Run this Python script:

```python
# migrate_database.py
import asyncio
from sqlalchemy import text
from app.database.database import async_engine

async def migrate():
    async with async_engine.begin() as conn:
        try:
            # Check if column exists
            result = await conn.execute(
                text("SELECT hashed_password FROM users LIMIT 1")
            )
            print("✅ hashed_password column already exists")
        except Exception:
            # Add column if missing
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN hashed_password VARCHAR(255) DEFAULT '' NOT NULL")
            )
            print("✅ Added hashed_password column to users table")

asyncio.run(migrate())
```

### Step 3: Verify Configuration

Check `.env` file has required settings:
```env
# Database
DATABASE_URL=sqlite+aiosqlite:///./vocalpay.db

# JWT Authentication (REQUIRED)
JWT_SECRET_KEY=CHANGE_THIS_TO_A_SECURE_RANDOM_SECRET_KEY_IN_PRODUCTION_MIN_32_CHARS
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Biometric Thresholds
SPEAKER_PASS_THRESHOLD=0.75
FACE_PASS_THRESHOLD=0.80
LIVENESS_CRITICAL_THRESHOLD=0.40
```

### Step 4: Test Individual Components

```bash
# Test config loading
python -c "from app.core.config import settings; print('✅ Config OK')"

# Test security module
python -c "from app.core.security import hash_password; print('✅ Security OK')"

# Test database
python -c "from app.database.database import async_engine; print('✅ Database OK')"

# Test FAISS
python -c "import faiss; print('✅ FAISS OK')"

# Test full app
python -c "from app.main import app; print('✅ App OK')"
```

### Step 5: Start Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Common Errors & Solutions

### Error: "No module named 'faiss'"
**Solution:** `pip install faiss-cpu==1.8.0`

### Error: "No module named 'passlib'"
**Solution:** `pip install passlib[bcrypt]==1.7.4`

### Error: "No module named 'jose'"
**Solution:** `pip install python-jose[cryptography]==3.3.0`

### Error: "ValidationError: ACCESS_TOKEN_EXPIRE_MINUTES"
**Solution:** Already fixed - `strict=False` in config.py

### Error: "no such column: users.hashed_password"
**Solution:** Run database migration script above

### Error: "FAISS index not initialized"
**Solution:** This is OK - index builds on first use, or falls back to linear search

---

## Debug Mode Startup

If issues persist, run with detailed logging:

```bash
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)

from app.main import app
print('App loaded successfully')
"
```

---

## Expected Startup Output

```
INFO:     Will watch for changes in these directories: ['D:\\VocalPay']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using WatchFiles
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

Then access: http://localhost:8000/

---

## Still Having Issues?

Run the diagnostic script:
```bash
python diagnose_startup.py
```

This will check:
- Python version
- All required packages
- Module imports
- Settings loading
- FastAPI app import

And provide a detailed report of what's failing.

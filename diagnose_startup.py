"""Diagnostic script to identify VocalPay startup issues."""

import sys

print("=" * 60)
print("VocalPay Startup Diagnostic")
print("=" * 60)

# Test 1: Check Python version
print(f"\n1. Python Version: {sys.version}")

# Test 2: Check required packages
print("\n2. Checking required packages...")
required_packages = [
    'fastapi',
    'uvicorn',
    'sqlalchemy',
    'aiosqlite',
    'pydantic',
    'pydantic_settings',
    'loguru',
    'numpy',
    'torch',
    'faiss',
    'passlib',
    'jose',
]

for package in required_packages:
    try:
        __import__(package)
        print(f"   ✅ {package}")
    except ImportError as e:
        print(f"   ❌ {package} - {str(e)}")

# Test 3: Try importing app modules
print("\n3. Testing app module imports...")
modules = [
    'app.core.config',
    'app.core.security',
    'app.core.vector_index',
    'app.database.database',
    'app.database.models',
]

for module in modules:
    try:
        __import__(module)
        print(f"   ✅ {module}")
    except Exception as e:
        print(f"   ❌ {module}")
        print(f"      Error: {str(e)}")

# Test 4: Try loading settings
print("\n4. Testing settings load...")
try:
    from app.core.config import settings
    print(f"   ✅ Settings loaded")
    print(f"   - JWT_SECRET_KEY length: {len(settings.JWT_SECRET_KEY)}")
    print(f"   - ACCESS_TOKEN_EXPIRE_MINUTES: {settings.ACCESS_TOKEN_EXPIRE_MINUTES} (type: {type(settings.ACCESS_TOKEN_EXPIRE_MINUTES).__name__})")
except Exception as e:
    print(f"   ❌ Settings failed: {str(e)}")

# Test 5: Try importing FastAPI app
print("\n5. Testing FastAPI app import...")
try:
    from app.main import app
    print(f"   ✅ FastAPI app imported")
    print(f"   - Routes: {len(app.routes)}")
except Exception as e:
    print(f"   ❌ FastAPI app import failed")
    print(f"      Error: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Diagnostic Complete")
print("=" * 60)

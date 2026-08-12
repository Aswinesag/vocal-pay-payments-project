"""Quick verification script."""
import sys

print("Testing imports...")

try:
    import faiss
    print("✅ faiss")
except Exception as e:
    print(f"❌ faiss: {e}")
    sys.exit(1)

try:
    import passlib
    print("✅ passlib")
except Exception as e:
    print(f"❌ passlib: {e}")
    sys.exit(1)

try:
    import jose
    print("✅ jose")
except Exception as e:
    print(f"❌ jose: {e}")
    sys.exit(1)

try:
    from app.core.config import settings
    print(f"✅ config (ACCESS_TOKEN_EXPIRE_MINUTES={settings.ACCESS_TOKEN_EXPIRE_MINUTES})")
except Exception as e:
    print(f"❌ config: {e}")
    sys.exit(1)

try:
    from app.main import app
    print(f"✅ app (routes={len(app.routes)})")
except Exception as e:
    print(f"❌ app: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ ALL CHECKS PASSED - Server ready to start!")

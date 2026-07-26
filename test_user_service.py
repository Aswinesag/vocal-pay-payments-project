from app.services.user_service import (
    DEFAULT_LANGUAGE,
    MAX_FAILED_LOGIN_ATTEMPTS,
    _validate_full_name,
)

print("\n========== USER SERVICE ==========")

print(DEFAULT_LANGUAGE)
print(MAX_FAILED_LOGIN_ATTEMPTS)

print(_validate_full_name(" Aswin Kumar "))

try:
    _validate_full_name("A")
except Exception as exc:
    print(type(exc).__name__)
    print(exc)
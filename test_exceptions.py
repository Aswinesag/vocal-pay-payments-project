from app.core.exceptions import (
    AuthenticationError,
    ValidationError,
)

try:

    raise AuthenticationError(
        reason="Invalid API Key"
    )

except Exception as e:

    print(type(e).__name__)
    print(e)
    print(e.to_dict())

print()

try:

    raise ValidationError(
        field="amount"
    )

except Exception as e:

    print(type(e).__name__)
    print(e)
    print(e.to_dict())
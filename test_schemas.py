from app.database.schemas import (
    APIResponse,
    ErrorResponse,
    HealthResponse,
)

print("\n========== API RESPONSE ==========")
response = APIResponse(
    success=True,
    message="OK",
)
print(response.model_dump())

print("\n========== ERROR RESPONSE ==========")
error = ErrorResponse(
    success=False,
    message="Validation failed",
    error_code="INVALID_REQUEST",
)
print(error.model_dump())

print("\n========== HEALTH ==========")
health = HealthResponse(
    status="healthy",
    version="1.0.0",
    database="connected",
    ollama="ready",
    whisper="loaded",
)
print(health.model_dump())

from app.database.schemas import (
    UserRegistrationRequest,
    UserUpdateRequest,
)

print("\n========== USER REGISTRATION ==========")

registration = UserRegistrationRequest(
    user_id="user_001",
    full_name="Aswin Kumar",
    email="aswin@example.com",
    phone_number="+919876543210",
    speaker_embedding=[0.1, 0.2, 0.3],
    face_embedding=[0.4, 0.5, 0.6],
)

print(registration.model_dump())

print("\n========== USER UPDATE ==========")

update = UserUpdateRequest(
    full_name="Aswin K",
)

print(update.model_dump(exclude_none=True))
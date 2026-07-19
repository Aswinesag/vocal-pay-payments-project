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

from app.database.schemas import (
    TransactionInitiateRequest,
    RiskAssessmentResponse,
)

print("\n========== TRANSACTION INITIATE ==========")

request = TransactionInitiateRequest(
    amount=2500.50,
    recipient_id="merchant_001",
    device_id="android_pixel_7",
    audio_duration_seconds=4.2,
    audio_size_mb=1.8,
)

print(request.model_dump())

print("\n========== RISK RESPONSE ==========")

risk = RiskAssessmentResponse(
    transaction_id="TXN-12345678",
    risk_level="MEDIUM",
    speaker_score=0.82,
    face_score=0.88,
    fraud_score=0.42,
    requires_verification=True,
)

print(risk.model_dump())

from datetime import datetime, timedelta

from app.database.schemas import (
    PendingOTPResponse,
    PendingChallengeResponse,
    TransactionSuccessResponse,
    TransactionFraudResponse,
)

expires = datetime.utcnow() + timedelta(minutes=5)

print("\n========== OTP RESPONSE ==========")
otp = PendingOTPResponse(
    success=True,
    message="OTP verification required",
    transaction_id="TXN-OTP-001",
    expires_at=expires,
)
print(otp.model_dump())

print("\n========== CHALLENGE RESPONSE ==========")
challenge = PendingChallengeResponse(
    success=True,
    message="Voice challenge required",
    transaction_id="TXN-CH-001",
    challenge_phrase="Transfer 409 green",
    expires_at=expires,
)
print(challenge.model_dump())

print("\n========== SUCCESS RESPONSE ==========")
success = TransactionSuccessResponse(
    success=True,
    message="Transaction approved",
    transaction_id="TXN-SUCCESS-001",
    amount=2500.50,
    risk_level="LOW",
    xai_summary="Voice and face verification passed.",
)
print(success.model_dump())

print("\n========== FRAUD RESPONSE ==========")
fraud = TransactionFraudResponse(
    success=False,
    message="Replay attack detected",
    error_code="REPLAY_ATTACK",
    transaction_id="TXN-FRAUD-001",
    replay_attack=True,
)
print(fraud.model_dump())

from app.database.schemas import (
    OTPVerificationRequest,
    ChallengeVerificationRequest,
)

print("\n========== OTP VERIFICATION ==========")

otp_request = OTPVerificationRequest(
    transaction_id="TXN-OTP-001",
    device_id="android_pixel_7",
    otp_code="483291",
)

print(otp_request.model_dump())

print("\n========== CHALLENGE VERIFICATION ==========")

challenge_request = ChallengeVerificationRequest(
    transaction_id="TXN-CH-001",
    device_id="android_pixel_7",
    audio_duration_seconds=3.8,
    audio_size_mb=1.2,
    challenge_attempt=1,
)

print(challenge_request.model_dump())

from datetime import datetime, timedelta

from app.database.schemas import (
    VerificationSuccessResponse,
    VerificationFailureResponse,
    TransactionExpiredResponse,
)

print("\n========== VERIFICATION SUCCESS ==========")

success = VerificationSuccessResponse(
    success=True,
    message="Verification successful",
    transaction_id="TXN-OTP-001",
    amount=2500.50,
    risk_level="MEDIUM",
    verification_method="otp",
    xai_summary="OTP validated and biometric scores remained within threshold.",
    processing_time_ms=842.5,
)

print(success.model_dump())

print("\n========== VERIFICATION FAILURE ==========")

failure = VerificationFailureResponse(
    success=False,
    message="Invalid OTP",
    error_code="OTP_INVALID",
    transaction_id="TXN-OTP-001",
    verification_method="otp",
    remaining_attempts=2,
    risk_level="MEDIUM",
)

print(failure.model_dump())

print("\n========== TRANSACTION EXPIRED ==========")

expired = TransactionExpiredResponse(
    success=False,
    message="Transaction expired",
    error_code="TRANSACTION_EXPIRED",
    transaction_id="TXN-OTP-001",
    expired_at=datetime.utcnow() - timedelta(minutes=1),
)

print(expired.model_dump())

from datetime import datetime

from app.database.schemas import (
    TransactionSummary,
    LedgerEntry,
    TransactionResponse,
)

print("\n========== TRANSACTION SUMMARY ==========")

summary = TransactionSummary(
    transaction_id="TXN-123",
    amount=2500.50,
    status="SUCCESS",
    risk_level="LOW",
    created_at=datetime.utcnow(),
)

print(summary.model_dump())

print("\n========== LEDGER ENTRY ==========")

ledger = LedgerEntry(
    transaction_id="TXN-123",
    amount=2500.50,
    entry_type="debit",
    description="Transfer to merchant_001",
    balance_after=12499.50,
    created_at=datetime.utcnow(),
)

print(ledger.model_dump())

print("\n========== TRANSACTION DETAIL ==========")

detail = TransactionResponse(
    id=1,
    transaction_id="TXN-123",
    user_id="user_001",
    amount=2500.50,
    status="SUCCESS",
    risk_level="LOW",
    success=True,
    speaker_score=0.94,
    face_score=0.91,
    fraud_score=0.08,
    replay_attack=False,
    xai_reason="Voice and face verification passed with high confidence.",
    processing_time_ms=842.5,
    created_at=datetime.utcnow(),
    updated_at=datetime.utcnow(),
)

print(detail.model_dump())

from datetime import datetime

from app.database.schemas import (
    PaginationMeta,
    TransactionHistoryResponse,
    LedgerResponse,
    TransactionHistoryQuery,
    TransactionSummary,
    LedgerEntry,
)

print("\n========== PAGINATION ==========")

pagination = PaginationMeta(
    page=1,
    page_size=20,
    total_items=42,
    total_pages=3,
    has_next=True,
    has_previous=False,
)

print(pagination.model_dump())

print("\n========== HISTORY RESPONSE ==========")

history = TransactionHistoryResponse(
    success=True,
    message="History fetched successfully",
    data=[
        TransactionSummary(
            transaction_id="TXN-001",
            amount=2500.50,
            status="SUCCESS",
            risk_level="LOW",
            created_at=datetime.utcnow(),
        )
    ],
    pagination=pagination,
)

print(history.model_dump())

print("\n========== LEDGER RESPONSE ==========")

ledger = LedgerResponse(
    success=True,
    message="Ledger generated",
    entries=[
        LedgerEntry(
            transaction_id="TXN-001",
            amount=2500.50,
            entry_type="debit",
            description="Transfer to merchant_001",
            balance_after=12499.50,
            created_at=datetime.utcnow(),
        )
    ],
    opening_balance=15000.00,
    closing_balance=12499.50,
)

print(ledger.model_dump())

print("\n========== HISTORY QUERY ==========")

query = TransactionHistoryQuery(
    page=2,
    page_size=10,
    status="SUCCESS",
)

print(query.model_dump(exclude_none=True))

from datetime import datetime

from app.database.schemas import (
    FraudEventResponse,
    FraudEventCreate,
    FraudStatistics,
)

print("\n========== FRAUD EVENT RESPONSE ==========")

fraud_response = FraudEventResponse(
    id=1,
    transaction_id="TXN-FRAUD-001",
    user_id="user_001",
    event_type="REPLAY_ATTACK",
    risk_level="CRITICAL",
    blocked=True,
    replay_attack=True,
    reason="Spectral roll-off below threshold.",
    created_at=datetime.utcnow(),
)

print(fraud_response.model_dump())

print("\n========== FRAUD CREATE ==========")

fraud_create = FraudEventCreate(
    transaction_id="TXN-FRAUD-001",
    user_id="user_001",
    event_type="REPLAY_ATTACK",
    risk_level="CRITICAL",
    blocked=True,
    replay_attack=True,
    reason="DSP replay detector triggered.",
)

print(fraud_create.model_dump())

print("\n========== FRAUD STATS ==========")

stats = FraudStatistics(
    total_events=42,
    blocked_events=18,
    replay_attacks=7,
    liveness_failures=5,
    biometric_mismatches=4,
    challenge_failures=2,
    last_24h_events=6,
)

print(stats.model_dump())

from app.database.schemas import (
    AuditLogResponse,
    AuditLogQuery,
    SecurityDashboardSummary,
)

print("\n========== AUDIT RESPONSE ==========")

audit = AuditLogResponse(
    id=1,
    transaction_id="TXN-123",
    user_id="user_001",
    endpoint="/api/v1/transaction/initiate",
    method="POST",
    event_type="TRANSACTION_INITIATED",
    status="SUCCESS",
    message="Transaction initiation completed.",
    processing_time_ms=842.5,
    created_at=datetime.utcnow(),
)

print(audit.model_dump())

print("\n========== AUDIT QUERY ==========")

query = AuditLogQuery(
    page=1,
    page_size=100,
    event_type="TRANSACTION_INITIATED",
)

print(query.model_dump(exclude_none=True))

print("\n========== DASHBOARD SUMMARY ==========")

dashboard = SecurityDashboardSummary(
    active_users=128,
    transactions_today=542,
    fraud_events_today=7,
    blocked_transactions_today=3,
    replay_attacks_today=2,
    average_fraud_score=0.31,
    system_health="healthy",
)

print(dashboard.model_dump())
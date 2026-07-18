from app.core.constants import (
    APIResponseCode,
    TransactionStatus,
    RiskLevel,
    FraudDecision,
)

print()

print("========== API RESPONSE ==========")

print(APIResponseCode.SUCCESS)
print(APIResponseCode.PENDING_OTP)
print(APIResponseCode.PENDING_CHALLENGE)
print(APIResponseCode.FAILED_FRAUD)

print()

print("========== TRANSACTION STATUS ==========")

print(TransactionStatus.INITIATED)
print(TransactionStatus.PENDING_OTP)
print(TransactionStatus.PENDING_CHALLENGE)
print(TransactionStatus.APPROVED)
print(TransactionStatus.COMPLETED)

print()

print("========== RISK LEVEL ==========")

print(RiskLevel.LOW)
print(RiskLevel.MEDIUM)
print(RiskLevel.HIGH)
print(RiskLevel.CRITICAL)

print()

print("========== FRAUD DECISION ==========")

print(FraudDecision.APPROVE)
print(FraudDecision.REQUIRE_OTP)
print(FraudDecision.REQUIRE_VOICE_CHALLENGE)
print(FraudDecision.BLOCK)

from app.core.constants import (
    TransactionIntent,
    VerificationType,
    ModelComponent,
    LogComponent,
    DeviceType,
)

print()

print("========== TRANSACTION INTENT ==========")

for item in TransactionIntent:
    print(item)

print()

print("========== VERIFICATION TYPE ==========")

for item in VerificationType:
    print(item)

print()

print("========== MODEL COMPONENT ==========")

for item in ModelComponent:
    print(item)

print()

print("========== LOG COMPONENT ==========")

for item in LogComponent:
    print(item)

print()

print("========== DEVICE TYPE ==========")

for item in DeviceType:
    print(item)

print()

print("========== API MESSAGES ==========")

print(SUCCESS_MESSAGE)
print(OTP_REQUIRED_MESSAGE)
print(VOICE_CHALLENGE_REQUIRED_MESSAGE)
print(REPLAY_ATTACK_MESSAGE)

print()

print("========== AI MODELS ==========")

print(MODEL_DSP)
print(MODEL_WHISPER)
print(MODEL_ECAPA)
print(MODEL_INSIGHTFACE)
print(MODEL_MINIFASNET)
print(MODEL_OLLAMA)

print()

print("========== RISK REASONS ==========")

print(RISK_REASON_REPLAY_ATTACK)
print(RISK_REASON_LIVENESS_FAILURE)
print(RISK_REASON_HIGH_AMOUNT)

print()

print("========== PROJECT ==========")

print(PROJECT_NAME)
print(PROJECT_SHORT_NAME)
print(PROJECT_VERSION)
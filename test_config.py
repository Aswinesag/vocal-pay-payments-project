from app.core.config import Settings

settings = Settings()

print()

print("========== APPLICATION ==========")

print(settings.APP_NAME)

print(settings.APP_VERSION)

print(settings.ENVIRONMENT)

print(settings.DEBUG)

print()

print("========== SERVER ==========")

print(settings.HOST)

print(settings.PORT)

print(settings.API_PREFIX)

print()

print("========== DIRECTORIES ==========")

print(settings.BASE_DIR.exists())

print(settings.DATABASE_DIR.exists())

print(settings.LOG_DIR.exists())

print(settings.MODEL_DIR.exists())

print(settings.UPLOAD_DIR.exists())

print()

print("========== DATABASE ==========")

print(settings.DATABASE_URL)

print()

print("========== LOGGING ==========")

print(settings.LOG_LEVEL)

print(settings.LOG_DIRECTORY)

print(settings.AUDIT_LOG_ENABLED)

print()

print("========== AUDIO ==========")

print(settings.MAX_AUDIO_DURATION)

print(settings.MAX_AUDIO_SIZE_MB)

print(settings.ALLOWED_AUDIO_FORMATS)

print()

print("========== IMAGE ==========")

print(settings.MAX_IMAGE_SIZE_MB)

print(settings.ALLOWED_IMAGE_FORMATS)

print()

print("========== CORS ==========")

print(settings.ALLOWED_ORIGINS)

print()

print("========== PERFORMANCE ==========")

print(settings.MAX_WORKERS)

print(settings.REQUEST_TIMEOUT_SECONDS)

print()

print("========== WHISPER ==========")

print(settings.WHISPER_MODEL)
print(settings.WHISPER_DEVICE)
print(settings.WHISPER_COMPUTE_TYPE)
print(settings.WHISPER_BEAM_SIZE)
print(settings.WHISPER_LANGUAGE)

print()

print("========== SPEAKER ==========")

print(settings.SPEAKER_DEVICE)
print(settings.SPEAKER_SIMILARITY_THRESHOLD)

print()

print("========== FACE ==========")

print(settings.INSIGHTFACE_DEVICE)
print(settings.FACE_SIMILARITY_THRESHOLD)

print()

print("========== LIVENESS ==========")

print(settings.LIVENESS_DEVICE)
print(settings.LIVENESS_THRESHOLD)

print()

print("========== DSP ==========")

print(settings.ENABLE_DSP_GATEKEEPER)
print(settings.SPECTRAL_ROLLOFF_THRESHOLD)
print(settings.SPECTRAL_CENTROID_THRESHOLD)

print()

print("========== RISK ENGINE ==========")

print(settings.LOW_RISK_MAX)
print(settings.MEDIUM_RISK_MAX)
print(settings.HIGH_RISK_MAX)
print(settings.OTP_LENGTH)
print(settings.OTP_EXPIRY_MINUTES)
print(settings.CHALLENGE_EXPIRY_MINUTES)

print()

print("========== OLLAMA ==========")

print(settings.OLLAMA_ENABLED)
print(settings.OLLAMA_HOST)
print(settings.OLLAMA_MODEL)
print(settings.OLLAMA_TIMEOUT_SECONDS)

print()

print("========== TRANSACTION ==========")

print(settings.DEFAULT_CURRENCY)
print(settings.MAX_TRANSACTION_AMOUNT)

print()

print("========== CONVENIENCE PROPERTIES ==========")

print(settings.allowed_audio_formats)

print(settings.allowed_image_formats)

print(settings.allowed_origins)

print()

print("========== PATHS ==========")

print(settings.database_path)

print(settings.application_log_path)

print(settings.audit_log_path)

print(settings.upload_path)

print(settings.model_path)
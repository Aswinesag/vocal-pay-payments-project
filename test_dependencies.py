from app.core.dependencies import (
    get_settings,
    get_logger,
    get_model_registry,
    get_model_locks,
    is_model_loaded,
)

settings = get_settings()
logger = get_logger()

print()
print("========== SETTINGS ==========")
print(settings.APP_NAME)
print(settings.WHISPER_MODEL)

print()
print("========== LOGGER ==========")
logger.info("Dependency injection logger test.")

print()
print("========== MODEL REGISTRY ==========")

registry = get_model_registry()

for name, model in registry.items():
    print(f"{name:<12} -> {model}")

print()
print("========== LOCKS ==========")

locks = get_model_locks()

for name, lock in locks.items():
    print(f"{name:<12} -> {type(lock).__name__}")

print()
print("========== LOADED STATUS ==========")

for name in registry.keys():
    print(f"{name:<12} -> {is_model_loaded(name)}")

from app.core.dependencies import get_whisper_model

print()
print("========== WHISPER ==========")

whisper = get_whisper_model()

print(type(whisper).__name__)

print()

print("Loaded:", whisper is not None)

from app.core.dependencies import get_speaker_model

print()
print("========== SPEAKER MODEL ==========")

speaker = get_speaker_model()

print(type(speaker).__name__)

print("Loaded:", speaker is not None)

print("Device: CPU (Expected)")

from app.core.dependencies import get_face_model

print()
print("========== FACE MODEL ==========")

face = get_face_model()

print(type(face).__name__)

print("Loaded:", face is not None)

from app.core.dependencies import (
    get_ollama_client,
    get_liveness_detector,
)

print()
print("========== OLLAMA ==========")

client = get_ollama_client()

print(type(client).__name__)

print("Loaded:", client is not None)

print()

print("========== LIVENESS STUB ==========")

detector = get_liveness_detector()

print(type(detector).__name__)

try:
    detector.predict(None)

except NotImplementedError as exc:
    print(exc)

from app.core.dependencies import (
    get_request_context,
    get_request_id,
    get_transaction_id,
)

from app.core.log_context import (
    RequestContext,
    set_context,
)

set_context(
    RequestContext(
        request_id="REQ-12345678",
        transaction_id="TXN-87654321",
        user_id="test_user",
        session_id="SES-11111111",
        client_ip="127.0.0.1",
        user_agent="pytest",
        endpoint="/api/v1/test",
        method="POST",
    )
)

print()
print("========== REQUEST DEPENDENCY ==========")

ctx = get_request_context()

print(ctx)

print(get_request_id())

print(get_transaction_id())

from app.core.dependencies import (
    get_application_health,
    is_application_ready,
    get_loaded_models,
    get_runtime_information,
)

print()
print("========== APPLICATION HEALTH ==========")

print(get_application_health())

print()

print("Ready:", is_application_ready())

print()

print("========== LOADED MODELS ==========")

for name, loaded in get_loaded_models().items():
    print(f"{name:<12} -> {loaded}")

print()

print("========== RUNTIME ==========")

for key, value in get_runtime_information().items():
    print(f"{key:<15}: {value}")

from app.core.dependencies import (
    cleanup_models,
    has_loaded_models,
    get_loaded_models,
)

print()
print("========== CLEANUP ==========")

print("Before cleanup:", has_loaded_models())

cleanup_models()

print("After cleanup:", has_loaded_models())

print()

for name, loaded in get_loaded_models().items():
    print(f"{name:<12} -> {loaded}")

from app.core.dependencies import (
    initialize_dependencies,
    warmup_dependencies,
    shutdown_dependencies,
)

print()
print("========== STARTUP ==========")

initialize_dependencies()

print()

print("========== WARM-UP ==========")

warmup_dependencies()

print()

print("========== SHUTDOWN ==========")

shutdown_dependencies()
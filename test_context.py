from app.core.log_context import (
    initialize_request_context,
    get_context,
    update_context,
    clear_context,
)

ctx = initialize_request_context(
    user_id="test_user_001",
    client_ip="127.0.0.1",
    user_agent="Swagger",
    endpoint="/api/v1/asr",
    method="POST",
)

print(ctx)

update_context(user_id="test_user_999")

print(get_context())

clear_context()

print(get_context())
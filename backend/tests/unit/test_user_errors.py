from bebcare.utils.user_errors import (
    GENERATE_TASK_FAILED,
    is_safe_user_message,
    user_safe_detail,
    user_safe_task_error,
)


def test_blocks_script_commands():
    assert not is_safe_user_message(".\\scripts\\backend.ps1 start")
    assert user_safe_detail(
        RuntimeError(".\\scripts\\backend.ps1 start"),
        fallback="blocked",
    ) == "blocked"


def test_allows_validation_messages():
    assert is_safe_user_message("Brand slug 'acme' already exists")
    assert user_safe_detail(
        ValueError("Brand slug 'acme' already exists"),
        fallback="fallback",
    ) == "Brand slug 'acme' already exists"


def test_task_error_uses_stable_code_for_unsafe_exceptions():
    assert (
        user_safe_task_error(RuntimeError("HTTPConnectionPool(host='localhost')"))
        == GENERATE_TASK_FAILED
    )

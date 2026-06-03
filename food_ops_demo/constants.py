from __future__ import annotations


class AdapterMode:
    FAKE = "fake"
    MOCK_WEB = "mock_web"
    SHADOW = "shadow"
    BROWSER_USE = "browser_use"


class TaskState:
    CREATED = "created"
    PARSED = "parsed"
    VALIDATED = "validated"
    PREVIEWED = "previewed"
    AWAITING_APPROVAL = "awaiting_approval"
    QUEUED = "queued"
    SESSION_READY = "session_ready"
    PRE_SNAPSHOT_DONE = "pre_snapshot_done"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    SHADOW_PREFILLED = "shadow_prefilled"
    PENDING_REVIEW = "pending_review"
    MANUAL_REQUIRED = "manual_required"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OperationType:
    UPDATE_PRICE = "menu.update_price"
    UPDATE_SALE_STATUS = "menu.update_sale_status"
    UPDATE_BUSINESS_HOURS = "store.update_business_hours"
    UPDATE_PHONE = "store.update_phone"


class ErrorCode:
    ADAPTER_MODE_NOT_FOUND = "adapter_mode_not_found"
    AUTH_REQUIRED = "auth_required"
    TARGET_NOT_FOUND = "target_not_found"
    STORE_NOT_FOUND = "store_not_found"
    INVALID_STATE = "invalid_state"
    VERIFICATION_FAILED = "verification_failed"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    BROWSER_USE_AGENT_FAILED = "browser_use_agent_failed"
    BROWSER_USE_STRUCTURED_OUTPUT_INVALID = "browser_use_structured_output_invalid"
    BROWSER_USE_VERIFICATION_FAILED = "browser_use_verification_failed"
    BROWSER_USE_UNSUPPORTED_OPERATION = "browser_use_unsupported_operation"
    BROWSER_USE_CONFIGURATION_ERROR = "browser_use_configuration_error"


DEFAULT_STORE_NAME = "人民广场店"

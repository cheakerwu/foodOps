from food_ops_demo.constants import AdapterMode, ErrorCode, OperationType, TaskState


def test_adapter_modes_match_route_payload_values():
    assert AdapterMode.FAKE == "fake"
    assert AdapterMode.MOCK_WEB == "mock_web"
    assert AdapterMode.SHADOW == "shadow"
    assert AdapterMode.BROWSER_USE == "browser_use"


def test_task_state_values_match_existing_timeline_values():
    assert TaskState.AWAITING_APPROVAL == "awaiting_approval"
    assert TaskState.PENDING_REVIEW == "pending_review"
    assert TaskState.SUCCEEDED == "succeeded"
    assert TaskState.FAILED == "failed"


def test_operation_type_values_match_operation_plan_payloads():
    assert OperationType.UPDATE_PRICE == "menu.update_price"
    assert OperationType.UPDATE_SALE_STATUS == "menu.update_sale_status"
    assert OperationType.UPDATE_BUSINESS_HOURS == "store.update_business_hours"
    assert OperationType.UPDATE_PHONE == "store.update_phone"


def test_error_code_values_match_existing_api_contracts():
    assert ErrorCode.ADAPTER_MODE_NOT_FOUND == "adapter_mode_not_found"
    assert ErrorCode.AUTH_REQUIRED == "auth_required"
    assert ErrorCode.VERIFICATION_FAILED == "verification_failed"
    assert ErrorCode.BROWSER_USE_AGENT_FAILED == "browser_use_agent_failed"

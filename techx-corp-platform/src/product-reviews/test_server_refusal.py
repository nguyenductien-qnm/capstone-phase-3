import pytest
from unittest.mock import patch, MagicMock
from product_reviews_server import get_ai_assistant_response

@patch('product_reviews_server.apply_guardrail_input')
@patch('product_reviews_server.invoke_bedrock_converse_with_fallback')
def test_blocked_injection_returns_refusal(mock_invoke, mock_guardrail_input):
    # Setup mock to return blocked_in = True
    mock_guardrail_input.return_value = (True, "[filtered]")
    
    # Call the function
    response = get_ai_assistant_response("PRODUCT_ID", "malicious input")
    
    # Assert Bedrock is never called
    mock_invoke.assert_not_called()
    
    # Assert the refusal string is returned
    assert "Xin lỗi, câu hỏi chứa nội dung không hợp lệ nên mình không thể xử lý" in response.response


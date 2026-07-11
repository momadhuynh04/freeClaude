import pytest
from pydantic import ValidationError
from models.anthropic import AnthropicRequest, AnthropicResponse

def test_anthropic_request_parsing_valid():
    data = {
        "model": "claude-3-opus-20240229",
        "messages": [
            {"role": "user", "content": "Hello"}
        ],
        "system": "You are a helpful assistant",
        "stream": True,
        "temperature": 0.7
    }
    
    req = AnthropicRequest(**data)
    assert req.model == "claude-3-opus-20240229"
    assert len(req.messages) == 1
    assert req.messages[0].role == "user"
    assert req.messages[0].content == "Hello"
    assert req.system == "You are a helpful assistant"
    assert req.stream is True
    assert req.temperature == 0.7

def test_anthropic_request_parsing_missing_fields():
    data = {
        "model": "claude-3"
        # missing messages
    }
    with pytest.raises(ValidationError):
        AnthropicRequest(**data)

def test_anthropic_request_parsing_complex_content():
    data = {
        "model": "claude-3",
        "messages": [
            {
                "role": "user", 
                "content": [
                    {"type": "text", "text": "What is in this image?"},
                    {"type": "image", "source": {"type": "base64", "data": "..."}}
                ]
            }
        ]
    }
    req = AnthropicRequest(**data)
    assert isinstance(req.messages[0].content, list)
    assert req.messages[0].content[0]["type"] == "text"
    assert req.messages[0].content[1]["type"] == "image"

def test_anthropic_response_parsing():
    data = {
        "id": "msg_123",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": "Hi"}],
        "model": "claude-3",
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": 10,
            "output_tokens": 5
        }
    }
    
    resp = AnthropicResponse(**data)
    assert resp.id == "msg_123"
    assert resp.content[0]["text"] == "Hi"
    assert resp.usage.input_tokens == 10
    assert resp.usage.output_tokens == 5

import pytest
from models.anthropic import AnthropicRequest, Message
from provider.openrouter.adapter import OpenRouterProvider

@pytest.mark.asyncio
async def test_translate_request():
    provider = OpenRouterProvider(target_model="openrouter/qwen/qwen3.7-plus")
    
    anthropic_req = AnthropicRequest(
        model="claude-3-7-sonnet-20250219",
        messages=[Message(role="user", content="Hello")],
        stream=False
    )
    
    openai_req = await provider.translate_request(anthropic_req)
    
    assert openai_req["model"] == "openrouter/qwen/qwen3.7-plus"
    assert openai_req["messages"][0]["role"] == "user"
    assert openai_req["messages"][0]["content"] == "Hello"
    assert openai_req["stream"] is False

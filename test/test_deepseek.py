import pytest
from models.anthropic import AnthropicRequest, Message
from provider.deepseekplatform.adapter import DeepSeekProvider

@pytest.mark.asyncio
async def test_deepseek_translate_request():
    provider = DeepSeekProvider(target_model="deepseek-chat")
    
    anthropic_req = AnthropicRequest(
        model="claude-3-5-haiku-20241022",
        messages=[Message(role="user", content="Hello")],
        stream=False
    )
    
    deepseek_req = await provider.translate_request(anthropic_req)
    
    assert deepseek_req["model"] == "deepseek-chat"
    assert deepseek_req["messages"][0]["role"] == "user"
    assert deepseek_req["messages"][0]["content"] == "Hello"
    assert deepseek_req["stream"] is False

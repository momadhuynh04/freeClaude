import pytest
from unittest.mock import patch, MagicMock
from provider.openai_base import OpenAIBaseProvider

@pytest.mark.asyncio
@patch('httpx.AsyncClient.stream')
async def test_openai_stream_text_happy_path(mock_stream):
    # Mock stream response
    class MockStreamContextManager:
        async def __aenter__(self):
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            async def aiter_lines():
                yield 'data: {"choices": [{"delta": {"content": "Hello"}}]}'
                yield 'data: {"choices": [{"delta": {"content": " World"}}]}'
                yield 'data: {"choices": [{"finish_reason": "stop"}]}'
                yield 'data: [DONE]'
            
            mock_response.aiter_lines = aiter_lines
            return mock_response
            
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    mock_stream.return_value = MockStreamContextManager()
    
    provider = OpenAIBaseProvider(base_url="http://test", api_key="test", target_model="test")
    
    events = []
    async for event in provider.stream({"messages": []}):
        events.append(event)
        
    assert len(events) == 7
    assert events[0].event == "message_start"
    
    assert events[1].event == "content_block_start"
    assert events[1].data["content_block"]["type"] == "text"
    
    assert events[2].event == "content_block_delta"
    assert events[2].data["delta"]["text"] == "Hello"
    
    assert events[3].event == "content_block_delta"
    assert events[3].data["delta"]["text"] == " World"
    
    assert events[4].event == "content_block_stop"
    
    assert events[5].event == "message_delta"
    # Ensure finish_reason stop converts to end_turn
    assert events[5].data["delta"]["stop_reason"] in ("end_turn", "stop")
    
    assert events[6].event == "message_stop"

@pytest.mark.asyncio
@patch('httpx.AsyncClient.stream')
async def test_openai_stream_tool_calls(mock_stream):
    class MockStreamContextManager:
        async def __aenter__(self):
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            async def aiter_lines():
                # Mock tool call stream
                yield 'data: {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_abc", "function": {"name": "test_tool"}}]}}]}'
                yield 'data: {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "{\\"k\\" "}}]}}]}'
                yield 'data: {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": ": \\"v\\"}"}}]}}]}'
                yield 'data: {"choices": [{"finish_reason": "tool_calls"}]}'
                yield 'data: [DONE]'
                
            mock_response.aiter_lines = aiter_lines
            return mock_response
            
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    mock_stream.return_value = MockStreamContextManager()
    
    provider = OpenAIBaseProvider(base_url="http://test", api_key="test", target_model="test")
    
    events = []
    async for event in provider.stream({"messages": []}):
        events.append(event)
        
    assert len(events) == 7
    assert events[0].event == "message_start"
    
    assert events[1].event == "content_block_start"
    assert events[1].data["content_block"]["type"] == "tool_use"
    assert events[1].data["content_block"]["id"] == "toolu_call_abc" # Ensures prefixing works
    
    assert events[2].event == "content_block_delta"
    assert events[2].data["delta"]["partial_json"] == '{"k" '
    
    assert events[3].event == "content_block_delta"
    assert events[3].data["delta"]["partial_json"] == ': "v"}'
    
    assert events[4].event == "content_block_stop"
    
    assert events[5].event == "message_delta"
    assert events[5].data["delta"]["stop_reason"] == "tool_use"
    
    assert events[6].event == "message_stop"

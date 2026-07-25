import json
import httpx
from typing import AsyncIterator, Dict, Any, List
from provider.base import BaseProvider
from models.anthropic import AnthropicRequest, AnthropicResponse, AnthropicUsage
from models.events import SSEEvent
import uuid


def _anthropic_content_to_openai(role: str, content: Any) -> List[Dict[str, Any]]:
    """
    Convert an Anthropic message (role + content) to a list of OpenAI-format messages.
    Handles text, tool_use (assistant calling tools), and tool_result (user returning results).
    """
    if isinstance(content, str):
        return [{"role": role, "content": content}]

    # Content is a list of blocks
    messages = []
    text_parts: List[str] = []
    tool_calls: List[Dict[str, Any]] = []

    for block in content:
        block_type = block.get("type")

        if block_type == "text":
            text_parts.append(block.get("text", ""))

        elif block_type == "tool_use":
            # Anthropic tool_use → OpenAI tool_call
            raw_id = block.get("id", f"call_{uuid.uuid4().hex}")
            tc_id = raw_id[6:] if raw_id.startswith("toolu_") else raw_id
            tool_calls.append({
                "id": tc_id,
                "type": "function",
                "function": {
                    "name": block.get("name", ""),
                    "arguments": json.dumps(block.get("input", {}))
                }
            })

        elif block_type == "tool_result":
            # Anthropic tool_result → OpenAI tool role message
            result_content = block.get("content", "")
            if isinstance(result_content, list):
                result_content = "\n".join(
                    c.get("text", "") for c in result_content if c.get("type") == "text"
                )
            raw_id = block.get("tool_use_id", "")
            tc_id = raw_id[6:] if raw_id.startswith("toolu_") else raw_id
            messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": result_content
            })

    # Combine text + tool_calls into a single assistant message
    if role == "assistant" and (text_parts or tool_calls):
        msg: Dict[str, Any] = {"role": "assistant"}
        msg["content"] = "\n".join(text_parts) if text_parts else None
        if tool_calls:
            msg["tool_calls"] = tool_calls
        messages.insert(0, msg)
    elif role == "user" and text_parts:
        messages.insert(0, {"role": "user", "content": "\n".join(text_parts)})

    return messages


def _anthropic_tools_to_openai(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert Anthropic tool definitions to OpenAI function-calling format."""
    result = []
    for tool in tools:
        result.append({
            "type": "function",
            "function": {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {})
            }
        })
    return result


def _openai_tool_calls_to_anthropic(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert OpenAI tool_calls in a response to Anthropic tool_use content blocks."""
    blocks = []
    for tc in tool_calls:
        fn = tc.get("function", {})
        try:
            input_data = json.loads(fn.get("arguments", "{}"))
        except json.JSONDecodeError:
            input_data = {}
            
        raw_id = tc.get("id", f"call_{uuid.uuid4().hex}")
        tc_id = raw_id if raw_id.startswith("toolu_") else f"toolu_{raw_id}"
        
        blocks.append({
            "type": "tool_use",
            "id": tc_id,
            "name": fn.get("name", ""),
            "input": input_data
        })
    return blocks


class OpenAIBaseProvider(BaseProvider):
    """
    Shared base provider for any OpenAI Chat Completions compatible API.
    Handles full Anthropic ↔ OpenAI translation including tool use.
    """
    def __init__(self, target_model: str, base_url: str, api_key: str):
        super().__init__(target_model)
        self.base_url = base_url
        self.api_key = api_key

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def translate_request(self, anthropic_request: AnthropicRequest) -> Dict[str, Any]:
        """Convert Anthropic Messages request to OpenAI Chat Completions request."""
        messages = []

        # System prompt
        if anthropic_request.system:
            system_content = anthropic_request.system
            if isinstance(system_content, list):
                system_content = "\n".join(
                    m.get("text", "") for m in system_content if m.get("type") == "text"
                )
            messages.append({"role": "system", "content": system_content})

        # Conversation messages — handles text, tool_use, tool_result
        for msg in anthropic_request.messages:
            converted = _anthropic_content_to_openai(msg.role, msg.content)
            messages.extend(converted)

        body: Dict[str, Any] = {
            "model": self.target_model,
            "messages": messages,
            "stream": anthropic_request.stream,
        }

        if anthropic_request.max_tokens:
            body["max_tokens"] = anthropic_request.max_tokens
        if anthropic_request.temperature is not None:
            body["temperature"] = anthropic_request.temperature

        # Map Anthropic thinking → OpenAI reasoning_effort
        if anthropic_request.thinking and anthropic_request.thinking.type == "enabled":
            budget = anthropic_request.thinking.budget_tokens
            if budget > 16000:
                body["reasoning_effort"] = "xhigh"
            elif budget > 8000:
                body["reasoning_effort"] = "high"
            elif budget > 2000:
                body["reasoning_effort"] = "medium"
            else:
                body["reasoning_effort"] = "low"

        # Tool definitions
        if anthropic_request.tools:
            body["tools"] = _anthropic_tools_to_openai(anthropic_request.tools)

        return body

    async def translate_response(self, provider_response: Dict[str, Any]) -> AnthropicResponse:
        """Convert OpenAI Chat Completions response to Anthropic Messages response."""
        choice = provider_response.get("choices", [{}])[0]
        message = choice.get("message", {})
        finish_reason = choice.get("finish_reason")

        content_blocks: List[Dict[str, Any]] = []

        # Text content
        text = message.get("content")
        if text:
            content_blocks.append({"type": "text", "text": text})

        # Tool calls
        tool_calls = message.get("tool_calls")
        if tool_calls:
            content_blocks.extend(_openai_tool_calls_to_anthropic(tool_calls))
            finish_reason = "tool_use"

        if not content_blocks:
            content_blocks.append({"type": "text", "text": ""})

        provider_usage = provider_response.get("usage", {})
        usage = AnthropicUsage(
            input_tokens=provider_usage.get("prompt_tokens", 0),
            output_tokens=provider_usage.get("completion_tokens", 0)
        )

        return AnthropicResponse(
            id=f"msg_{provider_response.get('id', uuid.uuid4().hex)}",
            model=self.target_model,
            content=content_blocks,
            stop_reason=finish_reason,
            usage=usage
        )

    async def generate(self, request_body: Dict[str, Any]) -> AnthropicResponse:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._get_headers(),
                json=request_body,
                timeout=120.0
            )
            resp.raise_for_status()
            return await self.translate_response(resp.json())

    async def stream(self, request_body: Dict[str, Any]) -> AsyncIterator[SSEEvent]:
        request_body["stream"] = True
        msg_id = f"msg_{uuid.uuid4().hex}"

        yield SSEEvent(event="message_start", data={
            "type": "message_start",
            "message": {
                "id": msg_id, "type": "message", "role": "assistant",
                "content": [], "model": self.target_model,
                "stop_reason": None, "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0}
            }
        })

        # Streaming state
        text_block_open = False
        tool_blocks: Dict[int, Dict[str, Any]] = {}  # index → partial tool call
        block_index = 0

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._get_headers(),
                json=request_body,
                timeout=120.0
            ) as response:
                if response.status_code != 200:
                    await response.aread()
                    response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})

                    # --- Text delta ---
                    text_delta = delta.get("content")
                    if text_delta:
                        if not text_block_open:
                            yield SSEEvent(event="content_block_start", data={
                                "type": "content_block_start", "index": block_index,
                                "content_block": {"type": "text", "text": ""}
                            })
                            text_block_open = True
                        yield SSEEvent(event="content_block_delta", data={
                            "type": "content_block_delta", "index": block_index,
                            "delta": {"type": "text_delta", "text": text_delta}
                        })

                    # --- Tool call delta ---
                    for tc_chunk in delta.get("tool_calls", []):
                        tc_index = tc_chunk.get("index", 0)

                        if tc_index not in tool_blocks:
                            # Close text block if open
                            if text_block_open:
                                yield SSEEvent(event="content_block_stop", data={
                                    "type": "content_block_stop", "index": block_index
                                })
                                text_block_open = False
                                block_index += 1

                            fn_info = tc_chunk.get("function", {})
                            raw_id = tc_chunk.get("id", f"call_{uuid.uuid4().hex}")
                            tool_id = raw_id if raw_id.startswith("toolu_") else f"toolu_{raw_id}"
                            tool_name = fn_info.get("name", "")
                            tool_blocks[tc_index] = {"id": tool_id, "name": tool_name, "args_buf": ""}

                            yield SSEEvent(event="content_block_start", data={
                                "type": "content_block_start", "index": block_index + tc_index,
                                "content_block": {
                                    "type": "tool_use",
                                    "id": tool_id,
                                    "name": tool_name,
                                    "input": {}
                                }
                            })

                        args_delta = tc_chunk.get("function", {}).get("arguments", "")
                        if args_delta:
                            tool_blocks[tc_index]["args_buf"] += args_delta
                            yield SSEEvent(event="content_block_delta", data={
                                "type": "content_block_delta",
                                "index": block_index + tc_index,
                                "delta": {"type": "input_json_delta", "partial_json": args_delta}
                            })

        # Close any open blocks
        if text_block_open:
            yield SSEEvent(event="content_block_stop", data={
                "type": "content_block_stop", "index": block_index
            })
        for tc_index in tool_blocks:
            yield SSEEvent(event="content_block_stop", data={
                "type": "content_block_stop", "index": block_index + tc_index
            })

        stop_reason = "tool_use" if tool_blocks else "end_turn"
        yield SSEEvent(event="message_delta", data={
            "type": "message_delta",
            "delta": {"stop_reason": stop_reason, "stop_sequence": None},
            "usage": {"output_tokens": 0}
        })
        yield SSEEvent(event="message_stop", data={"type": "message_stop"})

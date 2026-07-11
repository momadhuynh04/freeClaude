from pydantic import BaseModel
from typing import List, Optional, Union, Dict, Any

class OpenAIMessage(BaseModel):
    role: str
    content: Union[str, List[Dict[str, Any]]]
    model_config = {"extra": "allow"}

class OpenAIRequest(BaseModel):
    model: str
    messages: List[OpenAIMessage]
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    model_config = {"extra": "allow"}

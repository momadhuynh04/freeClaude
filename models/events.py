from pydantic import BaseModel
from typing import Dict, Any
import json

class SSEEvent(BaseModel):
    event: str
    data: Dict[str, Any]
    
    def format(self) -> str:
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"

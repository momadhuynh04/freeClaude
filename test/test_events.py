import json
from models.events import SSEEvent

def test_sse_event_format_simple():
    event = SSEEvent(event="message", data={"text": "hello"})
    formatted = event.format()
    
    assert formatted.startswith("event: message\n")
    assert "data: " in formatted
    assert formatted.endswith("\n\n")
    
    # Check JSON encoding
    data_str = formatted.split("data: ")[1].strip()
    parsed_data = json.loads(data_str)
    assert parsed_data == {"text": "hello"}

def test_sse_event_format_empty_data():
    event = SSEEvent(event="ping", data={})
    formatted = event.format()
    
    assert formatted == 'event: ping\ndata: {}\n\n'

def test_sse_event_format_complex_data():
    complex_data = {
        "nested": {"key": "value"},
        "list": [1, 2, "3", {"inner": True}],
        "null_val": None
    }
    event = SSEEvent(event="complex", data=complex_data)
    formatted = event.format()
    
    data_str = formatted.split("data: ")[1].strip()
    parsed_data = json.loads(data_str)
    assert parsed_data == complex_data

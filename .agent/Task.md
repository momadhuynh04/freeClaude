# Task Tracker

## Phase 1: Foundation (MVP)
- [x] Update `requirements.txt` with FastAPI, Uvicorn, httpx, pydantic.
- [x] Create `config.json` with initial model mappings.
- [x] Implement `config/settings.py` and `config/model_map.py` to parse config.
- [x] Implement `models/anthropic.py` and `models/events.py`.
- [x] Implement `models/openai_compat.py`.
- [x] Implement `provider/base.py` (BaseProvider).
- [x] Implement `provider/openrouter/adapter.py` and `provider/openrouter/config.py`.
- [x] Implement `proxy/router.py` for model resolution.
- [x] Implement `proxy/handler.py`, `proxy/streaming.py` and `proxy/middleware.py`.
- [x] Implement `proxy/server.py` (FastAPI app, endpoints).
- [x] Implement `cli/main.py`.
- [x] Write integration test (`test_openrouter.py`).
- [x] Update `CHANGELOG.md`.

## Phase 2: Multi-Provider
- [x] Implement `provider/deepseekplatform/adapter.py` (Anthropic + OpenAI fallback).
- [x] Implement `provider/custom/adapter.py` (Custom Provider template).
- [x] Update `proxy/router.py` to instantiate DeepSeek and Custom adapters.
- [x] Write integration test (`test_deepseek.py`).
- [x] Add error handling for API errors in `proxy/server.py` (e.g., rate limits, invalid keys).
- [x] Update `CHANGELOG.md`.

## Phase 4: Polish
- [x] Integrate WebUI with proxy server.
- [x] Create comprehensive `README.md`.
- [x] Finalize `CHANGELOG.md`.
- [x] End-to-end testing with `claude-code`.

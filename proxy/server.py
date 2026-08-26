from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from typing import Dict, Literal, Optional
import subprocess
import urllib.parse
import platform
import shutil
import sys

from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import json
import datetime
import asyncio

from models.anthropic import AnthropicRequest
from models.openai_compat import OpenAIRequest, ResponsesRequest
from proxy.router import provider_router
from config.model_map import model_mapper
from config.codex_config import setup_codex_config, persist_codex_env_var, get_codex_config_path, DEFAULT_BASE_URL as CODEX_BASE_URL
from proxy.openai_ingress import (
    openai_chat_to_anthropic,
    anthropic_response_to_openai_chat,
    anthropic_events_to_openai_stream,
    openai_error_line,
)
from proxy.responses_ingress import (
    responses_to_anthropic,
    anthropic_response_to_responses_object,
    anthropic_events_to_responses_stream,
    has_native_tool_call,
    stream_text,
    stream_events,
    response_text,
    looks_like_action_narration,
    AGENTIC_NUDGE,
    _unwrap_additional_tools,
)

AGENTIC_RETRY_ATTEMPTS = 3

PROXY_URL = "http://127.0.0.1:8082"

IDE_DEFINITIONS = [
    {"id": "vscode", "name": "VS Code", "binary": "code", "config_dir": "Code", "supports_claude_extension": True},
    {"id": "vscodium", "name": "VSCodium", "binary": "codium", "config_dir": "VSCodium", "supports_claude_extension": True},
    {"id": "cursor", "name": "Cursor", "binary": "cursor", "config_dir": "Cursor", "supports_claude_extension": True},
]

def _detect_ides():
    detected = {}
    for ide in IDE_DEFINITIONS:
        binary_path = shutil.which(ide["binary"])
        if binary_path:
            version = ""
            try:
                result = subprocess.run([binary_path, "--version"], capture_output=True, text=True, timeout=5)
                version = result.stdout.strip().split("\n")[0] if result.returncode == 0 else ""
            except Exception:
                pass
            detected[ide["id"]] = {
                "binary": binary_path,
                "version": version,
                "name": ide["name"],
                "config_dir": ide["config_dir"],
                "supports_claude_extension": ide["supports_claude_extension"],
                "last_detected": datetime.datetime.now().isoformat()
            }
    return detected

def _save_ide_detection(detected):
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
    data = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                pass
    data["ide_detected"] = detected
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def _get_ide_settings_path(config_dir):
    system = platform.system()
    home = os.path.expanduser("~")
    if system == "Linux":
        return os.path.join(home, ".config", config_dir, "User", "settings.json")
    elif system == "Windows":
        return os.path.join(os.environ.get("APPDATA", ""), config_dir, "User", "settings.json")
    else:
        return os.path.join(home, "Library", "Application Support", config_dir, "User", "settings.json")

def _safe_merge_json(filepath, updates):
    data = {}
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                pass
    changed = False
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            for sub_key, sub_value in value.items():
                if data[key].get(sub_key) != sub_value:
                    data[key][sub_key] = sub_value
                    changed = True
        else:
            if data.get(key) != value:
                data[key] = value
                changed = True
    if changed:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    return changed

def _proxy_env() -> dict:
    """Environment variables injected into any launched CLI/IDE so both
    Claude Code and Codex route through the proxy."""
    return {
        "ANTHROPIC_BASE_URL": PROXY_URL,
        "ANTHROPIC_API_KEY": "freeClaude",
        "OPENAI_BASE_URL": f"{PROXY_URL}/v1",
        "FREECLAUDE_API_KEY": "freeClaude",
    }

def _setup_claude_env():
    claude_settings_path = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
    return _safe_merge_json(claude_settings_path, {
        "env": {
            "ANTHROPIC_BASE_URL": PROXY_URL,
            "ANTHROPIC_API_KEY": "freeClaude"
        }
    })

def _setup_ide_settings(config_dir):
    settings_path = _get_ide_settings_path(config_dir)
    return _safe_merge_json(settings_path, {
        "claudeCode.disableLoginPrompt": True
    })

def _launch_ide(binary, cwd):
    # Extend (not replace) the environment — GUI apps need PATH/DISPLAY/etc.,
    # plus proxy vars so the Codex extension routes through the proxy.
    env = os.environ.copy()
    env.update(_proxy_env())
    subprocess.Popen([binary, "--new-window", cwd], start_new_session=True, env=env)

def _find_linux_terminal():
    terminals = [
        "gnome-terminal", "konsole", "xfce4-terminal", "lxterminal",
        "alacritty", "kitty", "foot", "terminology", "xterm"
    ]
    for term in terminals:
        if shutil.which(term):
            return term
    return None

def _launch_terminal(cmd, cwd):
    system = platform.system()
    env = os.environ.copy()
    env.update(_proxy_env())

    if system == "Windows":
        import base64
        ps_cmd = cmd.replace('&&', ';')
        encoded = base64.b64encode(ps_cmd.encode('utf-16-le')).decode('ascii')
        return subprocess.Popen(
            f'start "" powershell -NoExit -EncodedCommand {encoded}',
            shell=True, cwd=cwd, env=env
        )
    elif system == "Linux":
        terminal = _find_linux_terminal()
        if not terminal:
            raise RuntimeError("No terminal emulator found. Install gnome-terminal, konsole, xterm, etc.")

        if terminal == "gnome-terminal":
            term_cmd = [terminal, "--working-directory", cwd, "--", "bash", "-c", f"{cmd}; exec bash"]
        elif terminal == "konsole":
            term_cmd = [terminal, "--workdir", cwd, "-e", "bash", "-c", f"{cmd}; exec bash"]
        elif terminal == "kitty":
            term_cmd = [terminal, "--directory", cwd, "bash", "-c", f"{cmd}; exec bash"]
        elif terminal == "alacritty":
            term_cmd = [terminal, "--working-directory", cwd, "-e", "bash", "-c", f"{cmd}; exec bash"]
        elif terminal == "foot":
            term_cmd = [terminal, "--working-directory", cwd, "bash", "-c", f"{cmd}; exec bash"]
        else:
            term_cmd = [terminal, "-e", f"bash -c 'cd {cwd} && {cmd}; exec bash'"]

        return subprocess.Popen(term_cmd, env=env, start_new_session=True)
    else:
        escaped_cwd = cwd.replace('"', '\\"')
        escaped_cmd = cmd.replace('"', '\\"')
        apple_script = f'tell app "Terminal" to do script "cd \\"{escaped_cwd}\\"; {escaped_cmd}"'
        return subprocess.Popen(
            ["osascript", "-e", apple_script],
            env=env
        )

app = FastAPI(title="freeClaude Proxy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

class ModelMappingRequest(BaseModel):
    source_model: str
    target: str

class LaunchRequest(BaseModel):
    path: Optional[str] = None
    repo_url: Optional[str] = None

class IDESetupRequest(BaseModel):
    editors: list[str] = []

class IDELaunchRequest(BaseModel):
    editor: str
    path: Optional[str] = None

@app.get("/api/ide-detect")
async def ide_detect():
    detected = _detect_ides()
    if detected:
        _save_ide_detection(detected)
    return {"detected": detected}

@app.get("/api/ide-detect-refresh")
async def ide_detect_refresh():
    detected = _detect_ides()
    _save_ide_detection(detected)
    return {"detected": detected}

@app.post("/api/ide-setup")
async def ide_setup(request: IDESetupRequest):
    results = []

    claude_changed = _setup_claude_env()
    results.append({"target": "claude_settings", "configured": claude_changed})

    codex_changed = setup_codex_config()
    persist_codex_env_var()
    results.append({"target": "codex_config", "configured": codex_changed})

    detected = _detect_ides()
    for ide_def in IDE_DEFINITIONS:
        if ide_def["id"] in request.editors and ide_def["id"] in detected:
            if ide_def["supports_claude_extension"]:
                changed = _setup_ide_settings(ide_def["config_dir"])
                results.append({"target": ide_def["id"], "configured": changed})
            else:
                results.append({"target": ide_def["id"], "configured": False, "note": "IDE does not support Claude Code extension — use terminal inside this IDE with `claude` CLI instead"})

    return {"status": "success", "results": results}

@app.post("/api/ide-launch")
async def ide_launch(request: IDELaunchRequest):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_cwd = base_dir

    if request.path and os.path.isdir(request.path):
        target_cwd = request.path

    detected = _detect_ides()
    info = detected.get(request.editor)
    if not info:
        raise HTTPException(status_code=404, detail=f"IDE '{request.editor}' not found. Run /api/ide-detect-refresh first.")

    try:
        _launch_ide(info["binary"], target_cwd)
        return {"status": "success", "message": f"Launched {info['name']}!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/models")
async def get_models():
    return {"mappings": model_mapper.get_all()}

# Simple in-memory cache for models
cached_available_models = {}

@app.get("/api/available-models")
async def get_available_models():
    global cached_available_models
    if cached_available_models:
        return cached_available_models
        
    models_data = {
        "openrouter": [],
        "deepseekplatform": ["deepseek-chat", "deepseek-reasoner", "deepseek-coder"]
    }
    
    # Fetch OpenRouter models
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://openrouter.ai/api/v1/models", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                models_data["openrouter"] = [m["id"] for m in data.get("data", [])]
    except Exception as e:
        print(f"Error fetching OpenRouter models: {e}")
        models_data["openrouter"] = ["qwen/qwen-turbo", "meta-llama/llama-3-8b-instruct"]
        
    # Fetch DeepSeek models
    try:
        from config.settings import settings
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://api.deepseek.com/models", headers={"Authorization": f"Bearer {settings.deepseek_api_key}"}, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                models_data["deepseekplatform"] = [m["id"] for m in data.get("data", [])]
            else:
                models_data["deepseekplatform"] = ["deepseek-chat", "deepseek-reasoner"]
    except Exception as e:
        print(f"Error fetching DeepSeek models: {e}")
        models_data["deepseekplatform"] = ["deepseek-chat", "deepseek-reasoner", "deepseek-coder"]

        
    try:
        from config.custom_providers import load_custom_providers as _load_cp
        for _pid, _spec in _load_cp().items():
            models_data[_pid] = [m.get("id") for m in (_spec.get("models") or []) if isinstance(m, dict) and m.get("id")]
    except Exception:
        pass

    cached_available_models = models_data
    return models_data

class CustomModelSpec(BaseModel):
    id: str
    name: str
    reasoning: bool = False
    image: bool = False

class CustomProviderSpec(BaseModel):
    id: str
    display_name: str
    provider_api: str
    base_url: str
    api_key: str
    headers: Optional[Dict[str, str]] = None
    models: list[CustomModelSpec]


@app.get("/api/custom-providers")
async def list_custom_providers():
    from config.custom_providers import get_masked_providers
    return {"providers": get_masked_providers()}


@app.post("/api/custom-providers")
async def create_custom_provider(request: CustomProviderSpec):
    from config.custom_providers import load_custom_providers, save_custom_providers, normalize_api_key_input
    raw_env = normalize_api_key_input(request.api_key)
    if not raw_env.strip():
        headers = request.headers or {}
        has_headers = any(k.strip() and v.strip() for k, v in headers.items()) if isinstance(headers, dict) else False
        if not has_headers:
            raise HTTPException(status_code=400, detail="API key ENV var is required (or provide auth via headers)")
    else:
        try:
            from config.custom_providers import validate_spec as _vs
            _vs({"id": request.id, "display_name": request.display_name, "provider_api": request.provider_api, "base_url": request.base_url, "api_key_env": raw_env, "headers": request.headers, "models": [m.model_dump() for m in request.models]})
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
    spec = {
        "id": request.id.strip().lower(),
        "display_name": request.display_name.strip(),
        "provider_api": request.provider_api,
        "base_url": request.base_url.strip().rstrip("/"),
        "api_key_env": raw_env,
        "headers": request.headers or {},
        "models": [m.model_dump() for m in request.models],
    }
    providers = load_custom_providers()
    providers[spec["id"]] = spec
    save_custom_providers(providers)
    global cached_available_models
    cached_available_models = {}
    from config.custom_providers import get_masked_providers as _masked
    masked = _masked()
    return {"status": "success", "providers": masked}


@app.delete("/api/custom-providers/{provider_id}")
async def delete_custom_provider(provider_id: str):
    from config.custom_providers import delete_provider, load_custom_providers, get_masked_providers
    providers = load_custom_providers()
    if provider_id not in providers:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")
    orphaned = [k for k, v in model_mapper.get_all().items() if v.startswith(f"{provider_id}/")]
    delete_provider(provider_id)
    global cached_available_models
    cached_available_models = {}
    return {"status": "success", "providers": get_masked_providers(), "orphaned_mappings": orphaned}


@app.get("/api/custom-providers/{provider_id}/models")
async def fetch_custom_provider_models(provider_id: str):
    import os as _os
    from config.custom_providers import load_custom_providers
    spec = load_custom_providers().get(provider_id)
    if not spec:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")
    api_key = _os.environ.get(spec.get("api_key_env", ""), "") if spec.get("api_key_env") else ""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    if spec.get("headers"):
        headers.update(spec["headers"])
    base = spec.get("base_url", "").rstrip("/")
    candidates = [f"{base}/models", f"{base}/v1/models"] if not base.endswith("/models") else [base]
    for url in candidates:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers, timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data.get("data"), list):
                        ids = [m.get("id") for m in data["data"] if isinstance(m, dict) and m.get("id")]
                        return {"ids": ids}
                    if isinstance(data, list):
                        return {"ids": [str(x) for x in data]}
        except Exception:
            continue
    return {"ids": []}


@app.post("/api/models")
async def update_model(request: ModelMappingRequest):
    model_mapper.set_mapping(request.source_model, request.target)
    return {"status": "success", "mappings": model_mapper.get_all()}

def _resolve_launch(request: LaunchRequest, cli_cmd: str):
    """Resolve a LaunchRequest to (shell_command, working_directory)."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_cwd = base_dir

    if request.repo_url:
        projects_dir = os.path.join(base_dir, "projects")
        os.makedirs(projects_dir, exist_ok=True)

        parsed_url = urllib.parse.urlparse(request.repo_url)
        path_parts = parsed_url.path.strip("/").split("/")
        repo_name = path_parts[-1] if path_parts else "repo"
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]

        repo_path = os.path.join(projects_dir, repo_name)

        if os.path.exists(repo_path):
            cmd = f'cd "{repo_path}" && {cli_cmd}'
        else:
            cmd = f'cd "{projects_dir}" && git clone {request.repo_url} && cd "{repo_name}" && {cli_cmd}'
    else:
        if request.path and os.path.isdir(request.path):
            target_cwd = request.path
        cmd = cli_cmd

    return cmd, target_cwd

@app.post("/api/launch")
async def launch_claude(request: LaunchRequest):
    cmd, target_cwd = _resolve_launch(request, "claude")

    try:
        _launch_terminal(cmd, target_cwd)
        return {"status": "success", "message": "Launched Claude Code!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------------------------
# Codex CLI support (OpenAI-native clients via /v1/chat/completions)
# ---------------------------------------------------------------------------

@app.get("/api/codex-detect")
async def codex_detect():
    detected = {}
    binary_path = shutil.which("codex")
    if binary_path:
        version = ""
        try:
            result = subprocess.run([binary_path, "--version"], capture_output=True, text=True, timeout=10)
            version = result.stdout.strip().split("\n")[0] if result.returncode == 0 else ""
        except Exception:
            pass
        detected = {
            "binary": binary_path,
            "version": version,
            "name": "Codex CLI",
            "last_detected": datetime.datetime.now().isoformat()
        }
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
        data = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    pass
        data["codex_cli_detected"] = detected
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    return {"detected": detected}

class CodexSetupRequest(BaseModel):
    base_url: Optional[str] = None

@app.post("/api/codex-setup")
async def codex_setup(request: Optional[CodexSetupRequest] = None):
    base_url = (request.base_url if request and request.base_url else CODEX_BASE_URL)
    changed = setup_codex_config(base_url=base_url)
    persisted = persist_codex_env_var()
    return {
        "status": "success",
        "configured": changed,
        "config_path": get_codex_config_path(),
        "base_url": base_url,
        "env_persisted": persisted
    }

@app.post("/api/codex-launch")
async def codex_launch(request: LaunchRequest):
    cmd, target_cwd = _resolve_launch(request, "codex")

    try:
        _launch_terminal(cmd, target_cwd)
        return {"status": "success", "message": "Launched Codex!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/browse-folder")
async def browse_folder():
    try:
        system = platform.system()

        def _run_linux_picker():
            for picker in ["zenity", "kdialog", "yad"]:
                if shutil.which(picker):
                    try:
                        if picker == "zenity":
                            cmd = [picker, "--file-selection", "--directory", "--title=Select Project Folder"]
                        elif picker == "yad":
                            cmd = [picker, "--file-selection", "--directory", "--title=Select Project Folder"]
                        else:
                            cmd = [picker, "--getexistingdirectory", "--title=Select Project Folder"]
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                        path = result.stdout.strip()
                        if path:
                            return path
                    except Exception:
                        pass
            return None

        def _run_win_picker():
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                path = filedialog.askdirectory(parent=root, title="Select Project Folder")
                root.destroy()
                return path if path else None
            except Exception:
                return None

        def _run_tkinter_picker():
            script = '''
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.attributes('-topmost', True)
print(filedialog.askdirectory(parent=root, title="Select Project Folder"))
'''
            try:
                result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30)
                return result.stdout.strip()
            except Exception:
                return None

        if system == "Linux":
            path = await asyncio.to_thread(_run_linux_picker)
            if path:
                return {"path": path}

        if system == "Windows":
            path = await asyncio.to_thread(_run_win_picker)
            if path:
                return {"path": path}

        path = await asyncio.to_thread(_run_tkinter_picker)
        if path:
            return {"path": path}
    except Exception:
        pass

    return {"path": ""}

@app.post("/v1/messages")
async def handle_messages(request: AnthropicRequest):
    print(f"\n[🚀] Received request from Claude Code for model: {request.model}")
    try:
        provider = provider_router.get_provider(request.model)
        
        provider_request_body = await provider.translate_request(request)
        
        if request.stream:
            async def event_generator():
                try:
                    async for event in provider.stream(provider_request_body):
                        yield event.format()
                except httpx.HTTPStatusError as e:
                    error_detail = e.response.text if hasattr(e, 'response') else str(e)
                    error_msg = f"Provider API Error {e.response.status_code}: {error_detail}"
                    print(f"[❌] {error_msg}")
                    import json
                    yield f'event: error\ndata: {{"type": "error", "error": {{"type": "api_error", "message": {json.dumps(error_msg)}}}}}\n\n'
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    error_msg = str(e)
                    print(f"[❌] {error_msg}")
                    import json
                    yield f'event: error\ndata: {{"type": "error", "error": {{"type": "api_error", "message": {json.dumps(error_msg)}}}}}\n\n'
            
            return StreamingResponse(event_generator(), media_type="text/event-stream")
        else:
            response = await provider.generate(provider_request_body)
            return response.model_dump(exclude_none=True)
            
    except httpx.HTTPStatusError as e:
        error_detail = e.response.text if hasattr(e, 'response') else str(e)
        error_msg = f"Provider API Error {e.response.status_code}: {error_detail}"
        print(f"[❌] {error_msg}")
        return JSONResponse(
            status_code=e.response.status_code,
            content={"type": "error", "error": {"type": "api_error", "message": error_msg}}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = str(e)
        return JSONResponse(
            status_code=500,
            content={"type": "error", "error": {"type": "api_error", "message": error_msg}}
        )

@app.post("/v1/chat/completions")
async def handle_chat_completions(request: OpenAIRequest):
    print(f"\n[🤖] Received request from OpenAI-compatible client (Codex) for model: {request.model}")
    try:
        anthropic_request = openai_chat_to_anthropic(request)
        provider = provider_router.get_provider(anthropic_request.model)

        provider_request_body = await provider.translate_request(anthropic_request)

        if request.stream:
            async def event_generator():
                try:
                    async for line in anthropic_events_to_openai_stream(
                        provider.stream(provider_request_body), request.model
                    ):
                        yield line
                except httpx.HTTPStatusError as e:
                    error_detail = e.response.text if hasattr(e, 'response') else str(e)
                    error_msg = f"Provider API Error {e.response.status_code}: {error_detail}"
                    print(f"[❌] {error_msg}")
                    yield openai_error_line(error_msg)
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"[❌] {e}")
                    yield openai_error_line(str(e))
                    yield "data: [DONE]\n\n"

            return StreamingResponse(event_generator(), media_type="text/event-stream")
        else:
            response = await provider.generate(provider_request_body)
            return anthropic_response_to_openai_chat(response, request.model)

    except httpx.HTTPStatusError as e:
        error_detail = e.response.text if hasattr(e, 'response') else str(e)
        error_msg = f"Provider API Error {e.response.status_code}: {error_detail}"
        print(f"[❌] {error_msg}")
        return JSONResponse(
            status_code=e.response.status_code,
            content={"error": {"message": error_msg, "type": "api_error", "code": None}}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": {"message": str(e), "type": "api_error", "code": None}}
        )

@app.post("/v1/responses")
async def handle_responses(request: ResponsesRequest):
    """OpenAI Responses API — native ingress for Codex CLI / Codex VS Code extension."""
    print(f"\n[🤖] Received Responses API request from Codex for model: {request.model}")
    try:
        raw_tools: list = []
        raw_tools.extend(request.tools or [])
        if getattr(request, "additional_tools", None):
            raw_tools.extend(request.additional_tools or [])
        extra = getattr(request, "__pydantic_extra__", None) or {}
        if extra.get("additional_tools"):
            raw_tools.extend(extra["additional_tools"] or [])
        if isinstance(request.input, list):
            for _item in request.input:
                if isinstance(_item, dict) and _item.get("type") == "additional_tools":
                    raw_tools.extend(_item.get("tools", []) or [])
        flat_tools = _unwrap_additional_tools(raw_tools)
        tool_schemas = {
            t.get("name"): (t.get("parameters") or t.get("input_schema") or {})
            for t in flat_tools
            if isinstance(t, dict) and t.get("name")
        }
        if flat_tools:
            print(f"[🔧] Codex tools unwrapped: {list(tool_schemas.keys())}")
        anthropic_request = responses_to_anthropic(request)
        provider = provider_router.get_provider(anthropic_request.model)

        provider_request_body = await provider.translate_request(anthropic_request)

        if request.stream:
            async def event_generator():
                nonlocal provider_request_body
                for attempt in range(AGENTIC_RETRY_ATTEMPTS):
                    events_buffer = []
                    try:
                        async for ev in provider.stream(provider_request_body):
                            events_buffer.append(ev)
                    except httpx.HTTPStatusError as e:
                        error_detail = e.response.text if hasattr(e, 'response') else str(e)
                        error_msg = f"Provider API Error {e.response.status_code}: {error_detail}"
                        print(f"[❌] {error_msg}")
                        yield f'event: response.failed\ndata: {json.dumps({"type": "response.failed", "response": {"error": {"code": "api_error", "message": error_msg}}})}\n\n'
                        return
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        print(f"[❌] {e}")
                        yield f'event: response.failed\ndata: {json.dumps({"type": "response.failed", "response": {"error": {"code": "api_error", "message": str(e)}}})}\n\n'
                        return

                    text = stream_text(events_buffer)
                    saw_stop = any(
                        ev.data.get("type") == "message_stop" for ev in events_buffer
                    )
                    premature_cut = not events_buffer or not saw_stop
                    narrated = (
                        tool_schemas
                        and not has_native_tool_call(events_buffer)
                        and looks_like_action_narration(text)
                    )

                    if (not narrated and not premature_cut) or attempt == AGENTIC_RETRY_ATTEMPTS - 1:
                        if premature_cut:
                            print(f"[⚠️] Upstream stream ended prematurely (no message_stop) after {attempt + 1} attempt(s)")
                        print(f"[🔁] Attempt {attempt + 1}/{AGENTIC_RETRY_ATTEMPTS}")
                        async for line in anthropic_events_to_responses_stream(
                            stream_events(events_buffer), request.model, tool_schemas
                        ):
                            yield line
                        return

                    # Narration instead of action, or a cut stream — retry.
                    reason = "premature stream cut" if premature_cut else "narration without tool call"
                    print(f"[🔁] {reason}, retrying ({attempt + 1}/{AGENTIC_RETRY_ATTEMPTS})")
                    anthropic_request.system = (
                        (anthropic_request.system or "") + "\n\n" + AGENTIC_NUDGE
                    ).strip()
                    provider_request_body = await provider.translate_request(anthropic_request)

            return StreamingResponse(event_generator(), media_type="text/event-stream")
        else:
            for attempt in range(AGENTIC_RETRY_ATTEMPTS):
                response = await provider.generate(provider_request_body)
                narrated = (
                    tool_schemas
                    and not any(b.get("type") == "tool_use" for b in response.content)
                    and looks_like_action_narration(response_text(response))
                )
                if not narrated or attempt == AGENTIC_RETRY_ATTEMPTS - 1:
                    return anthropic_response_to_responses_object(response, request.model, tool_schemas)

                print(f"[🔁] Model narrated instead of calling a tool, retrying ({attempt + 1}/{AGENTIC_RETRY_ATTEMPTS})")
                anthropic_request.system = (
                    (anthropic_request.system or "") + "\n\n" + AGENTIC_NUDGE
                ).strip()
                provider_request_body = await provider.translate_request(anthropic_request)

    except httpx.HTTPStatusError as e:
        error_detail = e.response.text if hasattr(e, 'response') else str(e)
        error_msg = f"Provider API Error {e.response.status_code}: {error_detail}"
        print(f"[❌] {error_msg}")
        return JSONResponse(
            status_code=e.response.status_code,
            content={"error": {"message": error_msg, "type": "api_error", "code": None}}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": {"message": str(e), "type": "api_error", "code": None}}
        )

@app.api_route("/api/hello", methods=["GET", "HEAD"])
async def api_hello():
    return {"message": "freeClaude proxy is running"}

@app.post("/v1/messages/count_tokens")
@app.post("/v1/messages/count_tokens/")
async def count_tokens(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}

    token_count = 0
    messages = body.get("messages", [])
    system = body.get("system", "")

    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            token_count += len(content.split()) * 2
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    text = block.get("text", "")
                    token_count += len(text.split()) * 2

    if isinstance(system, str):
        token_count += len(system.split()) * 2
    elif isinstance(system, list):
        for block in system:
            if isinstance(block, dict):
                token_count += len(block.get("text", "").split()) * 2

    if token_count == 0:
        token_count = 100

    return {"input_tokens": token_count}

@app.api_route("/v1/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"])
async def catch_all_v1(path_name: str, request: Request):
    print(f"\n[⚠️] Unhandled /v1 endpoint called: {request.method} /v1/{path_name}")
    body = await request.body()
    print(f"[⚠️] Body: {body.decode('utf-8', errors='ignore')}")
    return JSONResponse(
        status_code=404,
        content={"type": "error", "error": {"type": "api_error", "message": f"Endpoint /v1/{path_name} not implemented in freeClaude proxy."}}
    )

webui_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "webui", "dist")
if os.path.exists(webui_dist):
    app.mount("/", StaticFiles(directory=webui_dist, html=True), name="webui")
else:
    @app.get("/")
    async def root():
        return {"message": "WebUI not built. Run 'npm run build' in webui/ directory."}

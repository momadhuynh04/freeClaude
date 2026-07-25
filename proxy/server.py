from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from typing import Optional
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

from models.anthropic import AnthropicRequest
from proxy.router import provider_router
from config.model_map import model_mapper

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

def _setup_claude_env():
    claude_settings_path = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
    return _safe_merge_json(claude_settings_path, {
        "env": {
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:8082",
            "ANTHROPIC_API_KEY": "freeClaude"
        }
    })

def _setup_ide_settings(config_dir):
    settings_path = _get_ide_settings_path(config_dir)
    return _safe_merge_json(settings_path, {
        "claudeCode.disableLoginPrompt": True
    })

def _launch_ide(binary, cwd):
    subprocess.Popen([binary, "--new-window", cwd], start_new_session=True)

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
    env["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:8082"
    env["ANTHROPIC_API_KEY"] = "freeClaude"

    if system == "Windows":
        safe_cmd = cmd.replace('"', '\\"')
        return subprocess.Popen(
            f'start "" cmd /k "{safe_cmd}"',
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

        
    cached_available_models = models_data
    return models_data

@app.post("/api/models")
async def update_model(request: ModelMappingRequest):
    model_mapper.set_mapping(request.source_model, request.target)
    return {"status": "success", "mappings": model_mapper.get_all()}

@app.post("/api/launch")
async def launch_claude(request: LaunchRequest):
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
            cmd = f'cd "{repo_path}" && claude'
        else:
            cmd = f'cd "{projects_dir}" && git clone {request.repo_url} && cd "{repo_name}" && claude'
    else:
        if request.path and os.path.isdir(request.path):
            target_cwd = request.path
        cmd = "claude"

    try:
        _launch_terminal(cmd, target_cwd)
        return {"status": "success", "message": "Launched Claude Code!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/browse-folder")
async def browse_folder():
    system = platform.system()

    if system == "Linux":
        for picker in ["zenity", "kdialog", "yad"]:
            if shutil.which(picker):
                try:
                    if picker == "zenity":
                        cmd = [picker, "--file-selection", "--directory", "--title=Select Project Folder"]
                    elif picker == "yad":
                        cmd = [picker, "--file-selection", "--directory", "--title=Select Project Folder"]
                    else:
                        cmd = [picker, "--getexistingdirectory", "--title=Select Project Folder"]
                    result = subprocess.run(
                        cmd,
                        capture_output=True, text=True, timeout=30
                    )
                    path = result.stdout.strip()
                    if path:
                        return {"path": path}
                except Exception:
                    pass

    if system == "Windows":
        try:
            ps_script = '''
Add-Type -AssemblyName System.Windows.Forms
$folder = [System.Windows.Forms.FolderBrowserDialog]::new()
$folder.Description = "Select Project Folder"
$folder.ShowNewFolderButton = $true
if ($folder.ShowDialog() -eq "OK") { $folder.SelectedPath }
'''
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=30
            )
            path = result.stdout.strip()
            if path:
                return {"path": path}
        except Exception:
            pass

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
        path = result.stdout.strip()
        return {"path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/messages")
async def handle_messages(request: AnthropicRequest):
    print(f"\n[🚀] Nhận request từ Claude Code cho model: {request.model}")
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

@app.get("/api/hello")
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

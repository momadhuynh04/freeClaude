from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from typing import Optional
import subprocess
import urllib.parse

from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os

from models.anthropic import AnthropicRequest
from proxy.router import provider_router
from config.model_map import model_mapper

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
    target_cwd = base_dir # Default
    
    if request.repo_url:
        # Create projects dir
        projects_dir = os.path.join(base_dir, "projects")
        os.makedirs(projects_dir, exist_ok=True)
        
        # Get repo name from url
        parsed_url = urllib.parse.urlparse(request.repo_url)
        path_parts = parsed_url.path.strip("/").split("/")
        repo_name = path_parts[-1] if path_parts else "repo"
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
            
        repo_path = os.path.join(projects_dir, repo_name)
        
        if not os.path.exists(repo_path):
            pass
            
        target_cwd = projects_dir
        # Command to run in new window: git clone -> cd repo -> claude
        cmd_str = f'start cmd /k "if not exist "{repo_name}" git clone {request.repo_url} && cd "{repo_name}" && claude"'
    else:
        if request.path and os.path.isdir(request.path):
            target_cwd = request.path
        cmd_str = 'start cmd /k "claude"'

    # Set up environment variables
    env = os.environ.copy()
    env["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:8082"
    env["ANTHROPIC_API_KEY"] = "freeClaude"
    
    try:
        subprocess.Popen(cmd_str, shell=True, cwd=target_cwd, env=env)
        return {"status": "success", "message": "Launched Claude Code!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/browse-folder")
async def browse_folder():
    """Opens a native Windows folder picker dialogue."""
    script = '''
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.attributes('-topmost', True)
print(filedialog.askdirectory(parent=root, title="Select Project Folder"))
'''
    try:
        result = subprocess.run(["python", "-c", script], capture_output=True, text=True)
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

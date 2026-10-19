import sys
import time
import os
import subprocess
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from orchestrator import LLMOrchestrator

app = FastAPI(title="Edge Inverter Text-to-SQL AI System")

# Serve static UI files
app.mount("/static", StaticFiles(directory="static"), name="static")

mcp_process = None
MCP_PORT = 8000
MCP_URL = f"http://127.0.0.1:{MCP_PORT}/mcp"

def ensure_mcp_server():
    """Ensure local FastMCP server process is running."""
    global mcp_process
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.post(MCP_URL, json={})
            if resp.status_code in (200, 400):  # Server responds
                return
    except Exception:
        pass

    # Launch FastMCP server process if not running
    if mcp_process is None or mcp_process.poll() is not None:
        cmd = [sys.executable, "inv_mcp.py"]
        db_env = os.getenv("INVERTER_DB_PATH") or os.getenv("DB_PATH")
        if db_env:
            cmd.extend(["--db-path", db_env])
        mcp_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)

@app.on_event("startup")
def startup_event():
    ensure_mcp_server()

@app.on_event("shutdown")
def shutdown_event():
    global mcp_process
    if mcp_process and mcp_process.poll() is None:
        mcp_process.terminate()

class QueryRequest(BaseModel):
    prompt: str
    provider: str = "google"
    auth_type: str = "api_key"  # 'api_key' or 'oauth'
    access_token: Optional[str] = None
    api_keys: List[str] = []
    model_name: Optional[str] = None
    mcp_url: Optional[str] = None

@app.get("/", response_class=HTMLResponse)
def get_index():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/health")
def health_check():
    ensure_mcp_server()
    mcp_status = "running"
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.post(MCP_URL, json={})
            if resp.status_code not in (200, 400):
                mcp_status = "error"
    except Exception:
        mcp_status = "offline"

    return {
        "status": "ok",
        "mcp_server": mcp_status,
        "mcp_url": MCP_URL
    }

@app.post("/api/query")
def process_query(req: QueryRequest):
    ensure_mcp_server()
    target_mcp_url = req.mcp_url if req.mcp_url and req.mcp_url.strip() else MCP_URL
    orchestrator = LLMOrchestrator(mcp_server_url=target_mcp_url)

    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    try:
        res = orchestrator.execute_with_llm(
            provider=req.provider,
            keys=req.api_keys,
            user_prompt=req.prompt,
            model_name=req.model_name,
            auth_type=req.auth_type,
            access_token=req.access_token
        )
        return res
    except Exception as e:
        import traceback
        print(f"\n[ERROR] Exception processing query for provider '{req.provider}':", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5115)

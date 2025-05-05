"""FastAPI server for Nagatha core agent."""
from typing import Any, Dict, List
import asyncio

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from nagatha_assistant.core.agent import (
    start_session,
    list_sessions,
    get_messages,
    send_message,
    push_message,
    subscribe_session,
    unsubscribe_session,
)


# Pydantic models
class StartSessionResponse(BaseModel):
    id: int

class MessageItem(BaseModel):
    id: int
    session_id: int
    timestamp: str
    role: str
    content: str

class SendMessageRequest(BaseModel):
    content: str
    model: str = None
    memory_limit: int = None

class SendMessageResponse(BaseModel):
    reply: str

class PushMessageRequest(BaseModel):
    content: str
    role: str = "assistant"

app = FastAPI(title="Nagatha Core API", description="API for Nagatha core agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
from nagatha_assistant.core.agent import _ensure_plugins_ready

@app.on_event("startup")
async def _startup_plugins():
    """
    Ensure all plugins are discovered and set up at server startup.
    """
    await _ensure_plugins_ready()

@app.get("/", response_model=Dict[str, str])
async def index():
    return {"status": "ok"}

@app.get("/sessions", response_model=List[Dict[str, Any]])
async def list_sessions_endpoint():
    sessions = await list_sessions()
    return [{"id": s.id, "created_at": s.created_at.isoformat()} for s in sessions]

@app.get("/plugins", response_model=List[Dict[str, Any]])
async def list_plugins():
    """
    List all registered plugins and their function specs.
    """
    from nagatha_assistant.core.agent import _ensure_plugins_ready

    plugin_manager = await _ensure_plugins_ready()
    result = []
    for plugin in plugin_manager.plugins:
        result.append({
            "name": plugin.name,
            "version": plugin.version,
            "functions": plugin.function_specs(),
        })
    return result

@app.post("/sessions", response_model=StartSessionResponse)
async def new_session_endpoint():
    sid = await start_session()
    return {"id": sid}

@app.get("/sessions/{sid}/messages", response_model=List[MessageItem])
async def get_messages_endpoint(sid: int):
    msgs = await get_messages(sid)
    return [
        {
            "id": m.id,
            "session_id": m.session_id,
            "timestamp": m.timestamp.isoformat(),
            "role": m.role,
            "content": m.content,
        }
        for m in msgs
    ]

@app.post("/sessions/{sid}/messages", response_model=SendMessageResponse)
async def send_message_endpoint(sid: int, req: SendMessageRequest):
    reply = await send_message(
        sid, req.content, model=req.model, memory_limit=req.memory_limit
    )
    return {"reply": reply}

@app.post("/sessions/{sid}/push")
async def push_message_endpoint(sid: int, req: PushMessageRequest):
    await push_message(sid, req.content, role=req.role)
    return {"status": "pushed"}

@app.websocket("/ws/{sid}")
async def websocket_endpoint(websocket: WebSocket, sid: int):
    await websocket.accept()

    async def on_message(msg):
        payload = {
            "id": msg.id,
            "session_id": msg.session_id,
            "timestamp": msg.timestamp.isoformat(),
            "role": msg.role,
            "content": msg.content,
        }
        await websocket.send_json(payload)

    subscribe_session(sid, on_message)
    initial = await get_messages(sid)
    for m in initial:
        await on_message(m)

    try:
        while True:
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        unsubscribe_session(sid, on_message)

def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run("nagatha_assistant.server:app", host=host, port=port)
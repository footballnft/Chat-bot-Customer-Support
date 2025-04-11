from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from agno.agent import Agent
from agno.models.groq import Groq
from agno.utils.pprint import pprint_run_response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware import Middleware
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import traceback
import json
import time
from typing import Dict, List

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=[
            "https://pennyfundme5-neon.vercel.app",
            "http://localhost:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"]
    )
]

app = FastAPI(middleware=middleware)
app.state.limiter = limiter

# Rate limit error handler
@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."},
    )

# Define AI agent
customer_support_agent = Agent(
    name="Crypto Support Agent",
    role="Provide customer support for a decentralized fiat-to-crypto platform.",
    model=Groq(id="llama-3.3-70b-versatile"),
    instructions=[
        "Answer user questions about fiat-to-crypto transactions.",
        "Provide troubleshooting steps for transaction failures.",
        "Explain crypto wallet setup and security best practices.",
    ],
    markdown=True,
)

# Session management
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        self.user_sessions: Dict[int, List[dict]] = {}
        self.rate_limits: Dict[str, Dict[str, float]] = {}  # {ip: {"last_request": timestamp, "count": int}}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        session_id = id(websocket)
        self.active_connections[session_id] = websocket
        self.user_sessions[session_id] = [{
            "role": "system",
            "content": "You are a helpful customer support agent for a crypto platform."
        }]
        return session_id

    def disconnect(self, session_id: int):
        self.active_connections.pop(session_id, None)
        self.user_sessions.pop(session_id, None)

    def check_rate_limit(self, ip: str) -> bool:
        """Allow 10 requests per minute per IP"""
        now = time.time()
        if ip not in self.rate_limits:
            self.rate_limits[ip] = {"last_request": now, "count": 1}
            return True

        time_passed = now - self.rate_limits[ip]["last_request"]
        if time_passed > 60:  # Reset after 1 minute
            self.rate_limits[ip] = {"last_request": now, "count": 1}
            return True

        if self.rate_limits[ip]["count"] >= 10:
            return False

        self.rate_limits[ip]["count"] += 1
        return True

manager = ConnectionManager()

# HTTP endpoint for direct POST requests
class Query(BaseModel):
    question: str

@app.post("/ask")
@limiter.limit("10/minute")
async def ask_agent(request: Request, query: Query):
    try:
        if not manager.check_rate_limit(request.client.host):
            raise HTTPException(status_code=429, detail="Too many requests")

        response = customer_support_agent.run(query.question)
        response_text = getattr(response, 'content',
                      getattr(response, 'text',
                      getattr(response, 'response', str(response))))

        if not response_text:
            import io
            from contextlib import redirect_stdout
            f = io.StringIO()
            with redirect_stdout(f):
                pprint_run_response(response, markdown=True)
            response_text = f.getvalue()

        return {"response": response_text.strip()}

    except HTTPException:
        raise
    except Exception as e:
        print("🔥 Exception occurred:", str(e))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.options("/ask")
async def preflight_handler():
    return {"message": "CORS preflight"}

# WebSocket for real-time chat support
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    session_id = await manager.connect(websocket)
    client_ip = websocket.client.host

    try:
        while True:
            if not manager.check_rate_limit(client_ip):
                await websocket.send_text("⚠️ Too many requests. Please wait a minute.")
                await websocket.close(code=1008)  # Policy Violation
                break

            question = await websocket.receive_text()
            print(f"👤 User {session_id}: {question}")

            # Append question to history
            manager.user_sessions[session_id].append({
                "role": "user",
                "content": str(question)
            })

            # Process message
            response = customer_support_agent.run(question)
            response_text = getattr(response, 'content',
                                getattr(response, 'text',
                                getattr(response, 'response', str(response))))
            response_text = str(response_text)

            # Append response to history
            manager.user_sessions[session_id].append({
                "role": "assistant",
                "content": response_text
            })
            print(f"🤖 AI to {session_id}: {response_text}")

            await websocket.send_text(response_text.strip())

    except WebSocketDisconnect:
        print(f"Client {session_id} disconnected")
    except Exception as e:
        print(f"❌ Error in WebSocket {session_id}:", str(e))
        traceback.print_exc()
        try:
            await websocket.send_text("⚠️ An error occurred. Please try again later.")
            await websocket.close()
        except:
            pass
    finally:
        manager.disconnect(session_id)

@app.get("/")
async def root():
    return {"message": "Welcome to the Crypto Support Agent API!"}

@app.on_event("shutdown")
async def shutdown_event():
    print("Shutting down... cleaning up connections")
    for session_id in list(manager.active_connections.keys()):
        try:
            await manager.active_connections[session_id].close()
        except:
            pass
    manager.active_connections.clear()
    manager.user_sessions.clear()
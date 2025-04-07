from fastapi import FastAPI, HTTPException, WebSocket
from pydantic import BaseModel
from agno.agent import Agent
from agno.models.groq import Groq
from agno.utils.pprint import pprint_run_response
from fastapi.middleware.cors import CORSMiddleware
import traceback  # Add this at the top

app = FastAPI()

# CORS config for your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://pennyfundme5-neon.vercel.app",
        "http://localhost:3000",  # For local testing
    ],  # Change this to your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]  # Expose all headers to the client
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

# Session memory store for each WebSocket user
user_sessions = {}

# HTTP endpoint for direct POST requests
class Query(BaseModel):
    question: str

@app.post("/ask")
async def ask_agent(query: Query):
    try:
        # Get the RunResponse object
        response = customer_support_agent.run(query.question)

        # Extract the text content from the response
        # According to Agno docs, RunResponse should have the actual response content
        # Try multiple possible response attributes
        response_text = getattr(response, 'content',
                      getattr(response, 'text',
                      getattr(response, 'response', str(response))))


    # If the above doesn't work, try the pretty print function's output
        if not response_text:
            import io
            from contextlib import redirect_stdout

            f = io.StringIO()
            with redirect_stdout(f):
                pprint_run_response(response, markdown=True)
            response_text = f.getvalue()

        return {"response": response_text.strip()}

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
    await websocket.accept()
    session_id = id(websocket)  # Unique session ID
    user_sessions[session_id] = []  # Store chat history

    while True:
        try:
            question = await websocket.receive_text()
            print(f"👤 User: {question}")

            # Append question to history with proper format
            user_sessions[session_id].append({"role": "user", "content": str(question)})

            # Pass chat history to AI - ensure each message has proper format
            formatted_messages = [
                {"role": msg["role"], "content": str(msg["content"])}
                for msg in user_sessions[session_id]
            ]

            response = customer_support_agent.run(formatted_messages)

            response_text = getattr(response, 'content',
                                getattr(response, 'text',
                                getattr(response, 'response', str(response))))

             # Append response to history
            user_sessions[session_id].append({"role": "assistant", "content": str(response_text)})
            print(f"🤖 AI: {response_text}")

            await websocket.send_text(response_text.strip())

        except Exception as e:
            print("❌ Error in WebSocket:", str(e))
            traceback.print_exc()
            await websocket.send_text("⚠️ An error occurred. Please try again later.")
            break

@app.get("/")
async def root():
    return {"message": "Welcome to the Crypto Support Agent API!"}



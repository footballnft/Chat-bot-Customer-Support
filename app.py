from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agno.agent import Agent
from agno.models.groq import Groq
from agno.utils.pprint import pprint_run_response
from fastapi.middleware.cors import CORSMiddleware
import traceback  # Add this at the top

app = FastAPI()

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

# Request model
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

@app.get("/")
async def root():
    return {"message": "Welcome to the Crypto Support Agent API!"}

# Don't run uvicorn here
# We'll let Render run it with a command

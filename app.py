from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agno.agent import Agent
from agno.models.groq import Groq

app = FastAPI()

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
        response = customer_support_agent(query.question)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    return {"message": "Welcome to the Crypto Support Agent API!"}

# Don't run uvicorn here
# We'll let Render run it with a command

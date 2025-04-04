from agno.agent import Agent
from agno.models.groq import Groq
from agno.tools import WebSearchTools

# Define the Customer Support AI Agent
customer_support_agent = Agent(
    name="Crypto Support AI",
    role="Provide customer support for a decentralized fiat-to-crypto platform.",
    model=Groq(id="llama-3.3-70b-versatile"),  # Uses a Groq AI model
    tools=[WebSearchTools()],  # Optional: Enable live web search
    instructions=[
        "Help users with fiat-to-crypto transactions.",
        "Provide troubleshooting steps for common errors.",
        "Explain how to set up and secure crypto wallets.",
        "Always be polite and concise in responses.",
    ],
    markdown=True,  # Enables formatted responses
    show_tool_calls=True,  # Show when the AI uses external tools
)

# Start an interactive chat session
customer_support_agent.cli_app()

import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools import McpToolset
from mcp import StdioServerParameters

load_dotenv()

# Define the Toolset connecting to our local MCP server
# We use StdioServerParameters to run the mcp_server.py as a subprocess
mcp_toolset = McpToolset(
    connection_params=StdioServerParameters(
        command="python",
        args=[os.path.join(os.path.dirname(__file__), "mcp_server.py")]
    )
)

# Define the GitHub Card Agent
github_card_agent = LlmAgent(
    name="github_card_agent",
    model="gemini-2.5-flash", # Using gemini-2.5-flash for stability
    instruction="""You are a GitHub profile analyst and dev card generator. 
    When a user gives you a GitHub username, you ALWAYS follow this exact sequence:
    1. Call 'scrape_github' with the username.
    2. Call 'analyze_profile' with the full data from 'scrape_github'.
    3. Call 'generate_card_html' using the username, the 'scrape_github' data, and the 'analyze_profile' results.
    4. Call 'save_card' with the username and the generated HTML.
    
    Never skip steps. Be enthusiastic about developers' work. 
    If the profile is private or doesn't exist, say so clearly.""",
    tools=[mcp_toolset]
)

async def run_agent_workflow(username: str):
    """Helper to run the orchestrated agent workflow and get the final card path."""
    query = f"Generate a dev card for GitHub user: {username}"
    
    # Store the last output to return the saved card path
    last_response = ""
    
    # In ADK 2.0.0, we iterate over the events
    async for event in github_card_agent.run(query):
        if event.content:
            for part in event.content.parts:
                if part.text:
                    last_response = part.text
                    
    return last_response

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import asyncio
from google.genai import types

# Google ADK Imports
from google.adk import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService

# Local Agent Import
from agent import github_card_agent

app = FastAPI(title="GitHub Dev Card Generator API")

# 1. Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Setup ADK Services & Runner
session_service = InMemorySessionService()
memory_service = InMemoryMemoryService()

runner = Runner(
    app_name="github-card-generator",
    agent=github_card_agent,
    session_service=session_service,
    memory_service=memory_service,
    auto_create_session=True
)

# 3. Static File Serving
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
CARDS_DIR = os.path.join(STATIC_DIR, "cards")
os.makedirs(CARDS_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class CardRequest(BaseModel):
    username: str

@app.get("/")
async def serve_index():
    index_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html"))
    return FileResponse(index_path)

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/generate")
async def generate_card(request: CardRequest):
    """
    Triggers the ADK Agent to generate a dev card.
    Uses a unique session ID per username.
    """
    username = request.username
    session_id = f"session_{username}"
    message = f"Generate a dev card for {username}"
    
    final_output = ""
    try:
        # Construct the Content object required by the Runner
        message_content = types.Content(
            role="user",
            parts=[types.Part(text=message)]
        )

        # Run the agent via the ADK Runner
        for event in runner.run(user_id=username, session_id=session_id, new_message=message_content):
            # Capture the agent's text response
            if event.content:
                for part in event.content.parts:
                    if part.text:
                        final_output += part.text
        
        # Check if the card was actually saved
        card_file = f"{username}.html"
        card_path = os.path.join(CARDS_DIR, card_file)
        
        if os.path.exists(card_path):
            return {
                "username": username,
                "card_url": f"/static/cards/{card_file}",
                "agent_response": final_output
            }
        else:
            raise Exception("Agent finished but card file was not found.")

    except Exception as e:
        print(f"Error during agent execution: {str(e)}. Triggering robust heuristic pipeline fallback...")
        try:
            # Fallback to direct pipeline just like test_mcp.py
            from mcp_server import scrape_github, analyze_profile, generate_card_html, save_card
            
            github_data = await scrape_github(username)
            if "error" in github_data:
                raise Exception(github_data["error"])
                
            analysis = await analyze_profile(github_data)
            html = await generate_card_html(username, github_data, analysis)
            saved_path = await save_card(username, html)
            
            return {
                "username": username,
                "card_url": f"/static/cards/{username}.html",
                "agent_response": f"Generated successfully via robust fallback pipeline (Agent error: {str(e)})."
            }
        except Exception as fallback_err:
            print(f"Fallback pipeline failed: {str(fallback_err)}")
            raise HTTPException(status_code=500, detail=str(fallback_err))

@app.get("/card/{username}")
async def get_card(username: str):
    """Simple redirect or metadata check for a saved card."""
    card_file = f"{username}.html"
    if os.path.exists(os.path.join(CARDS_DIR, card_file)):
        return {"username": username, "url": f"/static/cards/{card_file}"}
    raise HTTPException(status_code=404, detail="Card not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

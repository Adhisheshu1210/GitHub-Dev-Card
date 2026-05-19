import os
import httpx
import json
import asyncio
from datetime import datetime
from collections import Counter
from jinja2 import Template
from fastmcp import FastMCP
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash-lite-001")

async def download_avatar(username: str, avatar_url: str) -> str:
    """Download and cache GitHub avatar locally to avoid CORS canvas issues."""
    if not avatar_url:
        return ""
    try:
        avatars_dir = os.path.join(os.path.dirname(__file__), "static", "avatars")
        os.makedirs(avatars_dir, exist_ok=True)
        local_path = os.path.join(avatars_dir, f"{username}.png")
        if os.path.exists(local_path):
            return f"/static/avatars/{username}.png"
        async with httpx.AsyncClient() as client:
            res = await client.get(avatar_url)
            if res.status_code == 200:
                with open(local_path, "wb") as f:
                    f.write(res.content)
                return f"/static/avatars/{username}.png"
    except Exception as e:
        print(f"Error downloading avatar for {username}: {str(e)}")
    return avatar_url

mcp = FastMCP("GitHub Card Tools")

@mcp.tool()
async def scrape_github(username: str) -> dict:
    """Fetch GitHub profile and repository statistics using GitHub REST API."""
    async with httpx.AsyncClient() as client:
        # Fetch Profile
        profile_res = await client.get(f"https://api.github.com/users/{username}")
        if profile_res.status_code != 200:
            return {"error": f"User {username} not found"}
        
        profile = profile_res.json()
        avatar_url = profile.get("avatar_url")
        local_avatar_url = await download_avatar(username, avatar_url)
        
        # Fetch Repos (sorted by stars, up to 100)
        repos_res = await client.get(f"https://api.github.com/users/{username}/repos?sort=stargazers&per_page=100")
        repos = repos_res.json() if repos_res.status_code == 200 else []
        
        # Aggregate languages
        languages = [r.get("language") for r in repos if r.get("language")]
        lang_counts = Counter(languages).most_common(5)
        
        top_6_repos = []
        for r in repos[:6]:
            top_6_repos.append({
                "name": r.get("name"),
                "stars": r.get("stargazers_count"),
                "language": r.get("language"),
                "description": r.get("description")
            })
            
        return {
            "username": username,
            "name": profile.get("name") or username,
            "avatar_url": local_avatar_url,
            "bio": profile.get("bio"),
            "location": profile.get("location"),
            "public_repos": profile.get("public_repos"),
            "followers": profile.get("followers"),
            "top_6_repos": top_6_repos,
            "most_used_languages": [l[0] for l in lang_counts]
        }

@mcp.tool()
async def analyze_profile(github_data: dict) -> dict:
    """Analyze GitHub profile using Gemini (with fallback) to determine developer personality and theme."""
    prompt = f"""
    Analyze this GitHub profile data and return a JSON object.
    Data: {json.dumps(github_data)}
    
    Required JSON format:
    {{
        "developer_vibe": "one sentence personality description",
        "top_skills": ["skill1", "skill2", "skill3"],
        "fun_fact": "something clever inferred from their repos or bio",
        "card_theme": "one of: hacker, builder, researcher, designer, open-source-hero"
    }}
    Return ONLY the JSON.
    """
    
    try:
        response = model.generate_content(prompt)
        # Extract JSON from potential markdown blocks
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except Exception as e:
        print(f"Gemini API Error: {str(e)}. Using heuristic fallback.")
        # Heuristic Fallback
        repos = github_data.get("top_6_repos", [])
        total_stars = sum(r.get("stars", 0) for r in repos)
        bio = (github_data.get("bio") or "").lower()
        
        theme = "builder"
        if total_stars > 1000 or "linux" in bio:
            theme = "open-source-hero"
        elif "security" in bio or "hack" in bio:
            theme = "hacker"
        elif "research" in bio or "study" in bio:
            theme = "researcher"
        elif "design" in bio or "ui" in bio or "ux" in bio:
            theme = "designer"
            
        return {
            "developer_vibe": f"A prolific developer focused on {github_data.get('most_used_languages', ['code'])[0]}.",
            "top_skills": github_data.get("most_used_languages", ["Coding"])[:3],
            "fun_fact": f"Has gathered over {total_stars} stars on their top projects!",
            "card_theme": theme
        }

@mcp.tool()
async def generate_card_html(username: str, github_data: dict, analysis: dict) -> str:
    """Generate a self-contained HTML/CSS string for a beautiful dev card."""
    
    theme_colors = {
        "hacker": {"bg": "#0d1117", "text": "#58a6ff", "accent": "#238636", "border": "#30363d"},
        "builder": {"bg": "#f6f8fa", "text": "#24292e", "accent": "#0969da", "border": "#d0d7de"},
        "researcher": {"bg": "#ffffff", "text": "#1a1a1a", "accent": "#6f42c1", "border": "#e1e4e8"},
        "designer": {"bg": "#fff5f5", "text": "#d73a49", "accent": "#ea4aaa", "border": "#f9826c"},
        "open-source-hero": {"bg": "#f0fdf4", "text": "#166534", "accent": "#22c55e", "border": "#bbf7d0"}
    }
    
    theme = analysis.get("card_theme", "builder")
    colors = theme_colors.get(theme, theme_colors["builder"])
    
    template_str = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{data.name}} - GitHub Developer Card</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            background: {{ '#0b0f19' if colors.bg == '#0d1117' else ('#f0f2f5' if colors.bg == '#f6f8fa' else ('#f8fafc' if colors.bg == '#ffffff' else '#080c14')) }};
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
            overflow: visible;
        }
        .github-card {
            background: {{colors.bg}};
            color: {{colors.text}};
            border: 2px solid {{colors.border}};
            padding: 25px;
            border-radius: 15px;
            max-width: 450px;
            width: 100%;
            box-shadow: 0 12px 32px rgba(0,0,0,0.25);
            transition: transform 0.3s ease;
        }
        @media print {
            @page { margin: 1cm; }
            body { 
                padding: 0; 
                margin: 0; 
                display: block; 
                background: {{colors.bg}} !important; 
                -webkit-print-color-adjust: exact; 
                print-color-adjust: exact;
            }
            .github-card {
                max-width: 100%;
                width: 100%;
                box-shadow: none;
                border: 2px solid {{colors.border}};
                transform: scale(1.3);
                transform-origin: top left;
                margin: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="github-card">
        <div style="display: flex; align-items: center; margin-bottom: 20px;">
            <img src="{{data.avatar_url}}" style="width: 80px; height: 80px; border-radius: 50%; border: 3px solid {{colors.accent}}; margin-right: 20px; object-fit: cover;">
            <div>
                <h2 style="margin: 0; font-size: 24px;">{{data.name}}</h2>
                <p style="margin: 5px 0 0; opacity: 0.8; font-style: italic; font-size: 14px;"><a href="https://github.com/{{username}}" target="_blank" style="color: inherit; text-decoration: none;">@{{username}}</a></p>
            </div>
        </div>
        
        <p style="font-size: 16px; line-height: 1.4; margin-bottom: 15px;">{{analysis.developer_vibe}}</p>
        
        <div style="margin-bottom: 20px;">
            {% for skill in analysis.top_skills %}
            <span style="background: {{colors.accent}}; color: white; padding: 4px 10px; border-radius: 20px; font-size: 12px; margin-right: 8px; font-weight: bold; display: inline-block; margin-bottom: 6px;">{{skill}}</span>
            {% endfor %}
        </div>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; font-size: 14px; background: rgba(0,0,0,0.03); padding: 10px; border-radius: 8px;">
            <div><strong>Repos:</strong> {{data.public_repos}}</div>
            <div><strong>Followers:</strong> {{data.followers}}</div>
        </div>
        
        <h4 style="margin: 0 0 10px; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">Top Projects</h4>
        <ul style="list-style: none; padding: 0; margin: 0;">
            {% for repo in data.top_6_repos[:3] %}
            <li style="margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid {{colors.border}};">
                <div style="font-weight: bold; font-size: 14px;">{{repo.name}} <span style="font-weight: normal; opacity: 0.7; float: right;">★ {{repo.stars}}</span></div>
                <div style="font-size: 12px; opacity: 0.8;">{{repo.language}}</div>
            </li>
            {% endfor %}
        </ul>
        
        <div style="margin-top: 15px; font-size: 12px; opacity: 0.7; border-top: 1px dashed {{colors.border}}; padding-top: 10px;">
            <strong>Fun Fact:</strong> {{analysis.fun_fact}}
        </div>
    </div>
</body>
</html>"""
    
    template = Template(template_str)
    return template.render(data=github_data, analysis=analysis, colors=colors, username=username)

@mcp.tool()
async def save_card(username: str, html: str) -> str:
    """Save the HTML card to the static directory and return its path."""
    os.makedirs("static/cards", exist_ok=True)
    filename = f"{username}.html"
    file_path = os.path.join("static", "cards", filename)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html)
        
    return f"/static/cards/{filename}"

if __name__ == "__main__":
    mcp.run()

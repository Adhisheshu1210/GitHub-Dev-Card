import asyncio
import os
import json
from mcp_server import scrape_github, analyze_profile, generate_card_html, save_card
from dotenv import load_dotenv

load_dotenv()

async def test_pipeline():
    username = "torvalds"
    print(f"--- Testing Pipeline for: {username} ---")
    
    # 1. Scrape
    print("\n[1/4] Scraping GitHub data...")
    try:
        github_data = await scrape_github(username)
        if "error" in github_data:
            print(f"FAILED: {github_data['error']}")
            return
        print("Success: Data fetched.")
    except Exception as e:
        print(f"FAILED: Error during scrape: {str(e)}")
        return

    # 2. Analyze
    print("\n[2/4] Analyzing profile with Gemini...")
    try:
        analysis = await analyze_profile(github_data)
        print("Success: Analysis complete.")
        print(f"Card Theme: {analysis.get('card_theme')}")
        print(f"Developer Vibe: {analysis.get('developer_vibe')}")
    except Exception as e:
        print(f"FAILED: Error during analysis: {str(e)}")
        return

    # 3. Generate HTML
    print("\n[3/4] Generating HTML card...")
    try:
        html = await generate_card_html(username, github_data, analysis)
        print("Success: HTML generated.")
    except Exception as e:
        print(f"FAILED: Error during HTML generation: {str(e)}")
        return

    # 4. Save
    print("\n[4/4] Saving card...")
    try:
        path = await save_card(username, html)
        print(f"Success: Card saved to {path}")
    except Exception as e:
        print(f"FAILED: Error during save: {str(e)}")
        return

    print("\n--- Pipeline Test Complete! ---")

if __name__ == "__main__":
    asyncio.run(test_pipeline())

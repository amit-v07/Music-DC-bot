import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ai_brain import ai_brain

async def test_ai():
    print("🧠 Testing AI Brain...")
    
    if not ai_brain.enabled:
        print("❌ AI Brain is DISABLED! Check API Key.")
        return

    scenarios = [
        ("skip", {"user": "Amit", "song": "Rick Astley - Never Gonna Give You Up"}),
        ("play", {"user": "Rahul", "song": "Channa Mereya"}),
        ("queue_end", {"user": "Server"})
    ]

    for action, context in scenarios:
        print(f"\n--- Scenario: {action} ---")
        try:
            response = await ai_brain.get_response(action, context)
            print(f"🤖 AI: {response}")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_ai())

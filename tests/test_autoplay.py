"""
Test script for autoplay functionality
Run this to verify the recommendation service works correctly
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audio.recommendation_service import YouTubeMusicRecommendationEngine


async def test_recommendations():
    """Test getting recommendations from a YouTube video"""
    engine = YouTubeMusicRecommendationEngine()
    
    # Test with a popular music video
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up
    
    print(f"🎵 Testing recommendations for: {test_url}")
    print("=" * 60)
    
    try:
        recommendations = await engine.get_related_songs(test_url, count=5)
        
        if recommendations:
            print(f"✅ Found {len(recommendations)} recommendations:")
            print()
            for i, rec in enumerate(recommendations, 1):
                duration_str = f"{rec.duration}s" if rec.duration else "Unknown"
                print(f"{i}. {rec.title}")
                print(f"   URL: {rec.video_url}")
                print(f"   Duration: {duration_str}")
                print(f"   Relevance Score: {rec.relevance_score:.2f}")
                print()
        else:
            print("❌ No recommendations found")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("Testing YouTube Recommendation Engine")
    print("=" * 60)
    asyncio.run(test_recommendations())

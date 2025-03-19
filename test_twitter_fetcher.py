import asyncio
import logging
from direct_twitter_fetcher import DirectTwitterFetcher
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_twitter_fetcher():
    """Test the Twitter fetcher"""
    fetcher = DirectTwitterFetcher()
    
    print("Testing default AI posts...")
    posts = await fetcher.fetch_trending_posts()
    
    if posts:
        print(f"Found {len(posts)} posts")
        for i, post in enumerate(posts):
            print(f"\n=== Post {i+1} ===")
            print(f"Author: @{post['author']}")
            print(f"Content: {post['description'][:100]}...")
            print(f"URL: {post['url']}")
            print(f"Engagement: {post['engagement']['likes']} likes, {post['engagement']['retweets']} retweets")
            print(f"Timestamp: {datetime.fromtimestamp(post['created_utc']).strftime('%Y-%m-%d %H:%M:%S')}")
            print("=================")
    else:
        print("No posts found")
    
    print("\nTesting with specific query 'llama'...")
    posts = await fetcher.fetch_trending_posts("llama")
    
    if posts:
        print(f"Found {len(posts)} posts about 'llama'")
        for i, post in enumerate(posts):
            print(f"\n=== Post {i+1} ===")
            print(f"Author: @{post['author']}")
            print(f"Content: {post['description'][:100]}...")
            print("=================")
    else:
        print("No posts found")

if __name__ == "__main__":
    asyncio.run(test_twitter_fetcher())
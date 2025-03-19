import logging
import asyncio
import json
from datetime import datetime
import sys
from cache_manager import CacheManager
from twitter_fetcher import TwitterFetcher

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('twitter_test.log')
    ]
)
logger = logging.getLogger(__name__)

async def test_twitter_fetching():
    try:
        logger.info("Initializing TwitterFetcher...")
        cache_manager = CacheManager(cache_ttl_hours=1)
        twitter_fetcher = TwitterFetcher(cache_manager)
        
        # Test the fetch trending posts with all methods
        logger.info("Testing fetch_trending_posts method...")
        posts = await twitter_fetcher.fetch_trending_posts(limit=3)
        
        if posts:
            logger.info(f"Successfully fetched {len(posts)} Twitter posts")
            
            for i, post in enumerate(posts):
                print(f"\n=== Post {i+1} ===")
                print(f"Title: {post['title']}")
                print(f"Author: @{post['author']}")
                print(f"URL: {post['url']}")
                print(f"Relevance Score: {post['relevance_score']}")
                print(f"Timestamp: {datetime.fromtimestamp(post['created_utc']).strftime('%Y-%m-%d %H:%M:%S')}")
                
                if 'engagement' in post:
                    engagement = post['engagement']
                    print(f"Likes: {engagement.get('likes', 0)}")
                    print(f"Retweets: {engagement.get('retweets', 0)}")
                    print(f"Replies: {engagement.get('replies', 0)}")
                    
                if 'hashtags' in post and post['hashtags']:
                    print(f"Hashtags: {' '.join(post['hashtags'])}")
                    
                print(f"Description Preview: {post['description'][:150]}...")
                print("=================")
        else:
            logger.error("No posts were returned")
            
        # Test with a specific query
        specific_query = "generative AI"
        logger.info(f"Testing with specific query: '{specific_query}'")
        specific_posts = await twitter_fetcher.fetch_trending_posts(query=specific_query, limit=2)
        
        if specific_posts:
            logger.info(f"Successfully fetched {len(specific_posts)} posts for query '{specific_query}'")
            print(f"\n=== Results for query '{specific_query}' ===")
            for post in specific_posts:
                print(f"Title: {post['title'][:100]}...")
                print(f"URL: {post['url']}")
                print(f"Relevance Score: {post['relevance_score']}")
                print("---")
        else:
            logger.error(f"No posts found for query '{specific_query}'")
    
    except Exception as e:
        logger.error(f"Error during test: {str(e)}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_twitter_fetching())
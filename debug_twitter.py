import logging
import asyncio
import json
import sys
import os
import traceback
from datetime import datetime
from cache_manager import CacheManager

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('twitter_debug.log')
    ]
)
logger = logging.getLogger("twitter_debug")

async def debug_twitter_fetcher():
    """Debug the Twitter fetcher to find issues"""
    logger.info("=== STARTING TWITTER FETCHER DEBUGGING ===")
    
    try:
        # 1. First check if the twitter_fetcher.py file exists
        logger.info("Checking for Twitter fetcher files...")
        required_files = [
            'twitter_fetcher.py',
            'twitter_nitter.py',
            'twitter_rss.py',
            'twitter_filter.py',
            'twitter_utils.py'
        ]
        
        missing_files = []
        for file in required_files:
            if not os.path.exists(file):
                missing_files.append(file)
                
        if missing_files:
            logger.error(f"Missing files: {', '.join(missing_files)}")
            logger.error("Please ensure all Twitter fetcher files are in the current directory")
            return
            
        logger.info("All required files found")
        
        # 2. Import the TwitterFetcher class
        logger.info("Importing TwitterFetcher...")
        try:
            from twitter_fetcher import TwitterFetcher
            logger.info("TwitterFetcher imported successfully")
        except ImportError as e:
            logger.error(f"Failed to import TwitterFetcher: {str(e)}")
            logger.error(traceback.format_exc())
            return
            
        # 3. Create a TwitterFetcher instance
        logger.info("Creating TwitterFetcher instance...")
        cache_manager = CacheManager(cache_ttl_hours=1)
        twitter_fetcher = TwitterFetcher(cache_manager)
        logger.info("TwitterFetcher instance created successfully")
        
        # 4. Test Nitter method directly from the NitterMethod class
        logger.info("Testing Nitter method directly...")
        try:
            nitter_method = twitter_fetcher.nitter_method
            logger.info("Getting working Nitter instance...")
            nitter_instance = await nitter_method._get_working_nitter_instance()
            logger.info(f"Working Nitter instance: {nitter_instance}")
            
            if nitter_instance:
                logger.info("Testing direct search with Nitter...")
                nitter_posts = await nitter_method._fetch_by_search(nitter_instance, "artificial intelligence", 3)
                logger.info(f"Nitter search returned {len(nitter_posts) if nitter_posts else 0} posts")
                
                if nitter_posts:
                    # Print first post details
                    logger.info("First post details:")
                    first_post = nitter_posts[0]
                    for key, value in first_post.items():
                        if key in ['content', 'url', 'author_username', 'timestamp']:
                            logger.info(f"  {key}: {value}")
            else:
                logger.error("No working Nitter instance found!")
                
        except Exception as e:
            logger.error(f"Error testing Nitter method: {str(e)}")
            logger.error(traceback.format_exc())
            
        # 5. Test RSS method
        logger.info("Testing RSS method directly...")
        try:
            rss_method = twitter_fetcher.rss_method
            rss_posts = await rss_method.fetch_posts("AI", 3)
            logger.info(f"RSS method returned {len(rss_posts) if rss_posts else 0} posts")
            
            if rss_posts:
                # Print first post details
                logger.info("First RSS post details:")
                first_post = rss_posts[0]
                for key, value in first_post.items():
                    if key in ['title', 'url', 'author_username', 'content']:
                        logger.info(f"  {key}: {value}")
        except Exception as e:
            logger.error(f"Error testing RSS method: {str(e)}")
            logger.error(traceback.format_exc())
            
        # 6. Test the filtering components
        logger.info("Testing filtering components...")
        try:
            from twitter_filter import filter_and_score_posts
            
            # Create a simple test post
            test_posts = [{
                'author_name': 'AI Research',
                'author_username': 'ai_research',
                'content': 'New breakthrough in artificial intelligence machine learning models with transformer architecture',
                'url': 'https://twitter.com/test',
                'timestamp': int(datetime.now().timestamp()),
                'replies': 10,
                'retweets': 50,
                'likes': 100,
                'hashtags': ['#AI', '#MachineLearning'],
                'type': 'twitter_post'
            }]
            
            filtered_posts = filter_and_score_posts(test_posts)
            logger.info(f"Filtering returned {len(filtered_posts) if filtered_posts else 0} posts")
            
            if filtered_posts:
                logger.info(f"Filtered post relevance score: {filtered_posts[0].get('relevance_score', 'N/A')}")
                logger.info(f"Filtered post quality score: {filtered_posts[0].get('quality_score', 'N/A')}")
        except Exception as e:
            logger.error(f"Error testing filtering: {str(e)}")
            logger.error(traceback.format_exc())
        
        # 7. Finally, test the full fetch_trending_posts method
        logger.info("Testing full fetch_trending_posts method...")
        try:
            posts = await twitter_fetcher.fetch_trending_posts("AI", limit=5)
            logger.info(f"fetch_trending_posts returned {len(posts) if posts else 0} posts")
            
            if posts:
                # Log all returned posts
                for i, post in enumerate(posts):
                    logger.info(f"=== Post {i+1} ===")
                    for key, value in post.items():
                        if key not in ['description']:  # Skip long content
                            logger.info(f"  {key}: {value}")
                
                # Check for required fields
                missing_fields = []
                required_fields = ['title', 'url', 'author', 'description', 'created_utc', 'relevance_score']
                
                for field in required_fields:
                    if field not in posts[0]:
                        missing_fields.append(field)
                
                if missing_fields:
                    logger.error(f"Posts are missing required fields: {', '.join(missing_fields)}")
                else:
                    logger.info("Posts have all required fields")
            else:
                logger.error("No posts returned from fetch_trending_posts!")
        except Exception as e:
            logger.error(f"Error testing fetch_trending_posts: {str(e)}")
            logger.error(traceback.format_exc())
    
    except Exception as e:
        logger.error(f"Unexpected error during debugging: {str(e)}")
        logger.error(traceback.format_exc())
    
    logger.info("=== TWITTER FETCHER DEBUGGING COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(debug_twitter_fetcher())
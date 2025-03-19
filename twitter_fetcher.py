import logging
import random
import asyncio
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

from cache_manager import CacheManager
from twitter_nitter import NitterMethod
from twitter_rss import RSSMethod
from twitter_filter import filter_and_score_posts, enhance_posts

logger = logging.getLogger(__name__)

# AI/ML-related search queries for Twitter
AI_SEARCH_QUERIES = [
    "artificial intelligence",
    "machine learning", 
    "deep learning",
    "AI research",
    "LLM",
    "generative AI"
]

class TwitterFetcher:
    """
    Fetches trending AI-related posts from Twitter (X) using multiple real data methods
    with advanced filtering for higher quality results.
    """
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.thread_pool = ThreadPoolExecutor(max_workers=3)
        
        # Initialize methods
        self.nitter_method = NitterMethod(self.thread_pool)
        self.rss_method = RSSMethod(self.thread_pool)
        
        # State flags
        self.nitter_failing = False
        logger.info("TwitterFetcher initialized with multiple methods")
    
    async def fetch_trending_posts(self, query: Optional[str] = None, limit: int = 5) -> List[Dict]:
        """
        Fetch trending Twitter posts about AI/ML topics using multiple methods
        with advanced filtering
        
        Args:
            query: Specific search query (optional)
            limit: Maximum number of posts to return
            
        Returns:
            List of post dictionaries with content and metadata
        """
        # Use provided query or one of the default AI topics
        search_query = query if query else random.choice(AI_SEARCH_QUERIES)
        cache_key = f"twitter_{search_query.replace(' ', '_')}"
        
        # Check cache first
        cached_posts = self.cache.get(cache_key)
        if cached_posts:
            logger.info(f"Returning cached Twitter posts for '{search_query}'")
            return cached_posts
        
        try:
            all_posts = []
            
            # Method 1: Nitter search if it hasn't been failing
            if not self.nitter_failing:
                logger.info(f"Trying Nitter method with query '{search_query}'")
                nitter_posts = await self.nitter_method.fetch_posts(search_query, limit*2)
                
                if nitter_posts:
                    all_posts.extend(nitter_posts)
                    logger.info(f"Got {len(nitter_posts)} posts from Nitter")
                else:
                    logger.warning("Nitter method failed, marking as failing")
                    self.nitter_failing = True
            
            # Method 2: Direct account fetch from Nitter
            if len(all_posts) < limit*2:
                logger.info("Trying accounts method")
                account_posts = await self.nitter_method.fetch_from_accounts(limit*2)
                
                if account_posts:
                    all_posts.extend(account_posts)
                    logger.info(f"Got {len(account_posts)} posts from AI accounts")
            
            # Method 3: RSS feeds as last resort
            if len(all_posts) < limit:
                logger.info("Trying RSS method")
                rss_posts = await self.rss_method.fetch_posts(search_query, limit*2)
                
                if rss_posts:
                    all_posts.extend(rss_posts)
                    logger.info(f"Got {len(rss_posts)} posts from RSS feeds")
            
            # Apply enhanced filtering and scoring
            if all_posts:
                logger.info(f"Filtering and scoring {len(all_posts)} total posts")
                filtered_posts = filter_and_score_posts(all_posts, search_query)
                
                # Get the highest quality posts
                top_posts = filtered_posts[:limit]
                
                # Enhance posts with additional context
                enhanced_posts = enhance_posts(top_posts)
                
                # Cache the results
                self.cache.set(cache_key, enhanced_posts)
                logger.info(f"Cached {len(enhanced_posts)} high-quality Twitter posts")
                return enhanced_posts
            
            logger.error("All methods failed to fetch Twitter data")
            return []
            
        except Exception as e:
            logger.error(f"Error fetching Twitter posts: {str(e)}", exc_info=True)
            return []
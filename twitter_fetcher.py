import tweepy
from typing import List, Dict, Optional
import logging
from cache_manager import CacheManager

logger = logging.getLogger(__name__)

class TwitterFetcher:
    """
    Fetches trending AI-related tweets
    """
    def __init__(self, api_key: str, api_secret: str, 
                 access_token: str, access_token_secret: str,
                 cache_manager: CacheManager):
        auth = tweepy.OAuthHandler(api_key, api_secret)
        auth.set_access_token(access_token, access_token_secret)
        self.api = tweepy.API(auth)
        self.cache = cache_manager
        
    async def fetch_trending_tweets(self, topic: Optional[str] = None, limit: int = 5) -> List[Dict]:
        """
        Fetch trending tweets about AI
        """
        search_query = topic if topic else "artificial intelligence OR AI news"
        cache_key = f"twitter_{search_query}"
        
        # Check cache first
        cached_tweets = self.cache.get(cache_key)
        if cached_tweets:
            logger.info(f"Returning cached tweets for {search_query}")
            return cached_tweets
            
        try:
            tweets = []
            for tweet in tweepy.Cursor(self.api.search_tweets, 
                                     q=search_query,
                                     lang="en",
                                     tweet_mode="extended").items(limit):
                tweets.append({
                    'text': tweet.full_text,
                    'author': tweet.user.screen_name,
                    'created_at': tweet.created_at.timestamp(),
                    'retweet_count': tweet.retweet_count,
                    'favorite_count': tweet.favorite_count,
                    'id': tweet.id_str
                })
            
            # Cache the results
            self.cache.set(cache_key, tweets)
            return tweets
            
        except Exception as e:
            logger.error(f"Error fetching Twitter posts: {str(e)}")
            return []

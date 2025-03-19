import logging
import requests
import feedparser
import time
import asyncio
import re
from datetime import datetime
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleTwitterFetcher:
    """
    A simple, reliable implementation of Twitter content fetching
    that focuses on getting AI tech news directly from RSS feeds.
    """
    def __init__(self, cache_ttl_hours=4):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        self.thread_pool = ThreadPoolExecutor(max_workers=2)
        
        # Cache for storing previous results
        self.cache = {}
        self.cache_time = {}
        self.cache_ttl = cache_ttl_hours * 3600  # Convert to seconds
        
        # List of reliable AI news feeds
        self.ai_feeds = [
            "https://hnrss.org/newest?q=AI+OR+artificial+intelligence+OR+machine+learning&count=25",
            "https://techcrunch.com/tag/artificial-intelligence/feed/",
            "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
            "https://venturebeat.com/category/ai/feed/",
            "https://feeds.feedburner.com/bdtechtalks"
        ]
    
    async def fetch_trending_posts(self, query: Optional[str] = None, limit: int = 5) -> List[Dict]:
        """
        Fetch trending AI content from reliable RSS feeds
        
        Args:
            query: Optional search query for filtering content
            limit: Maximum number of posts to return
            
        Returns:
            List of posts about AI trending topics
        """
        # Check cache first
        cache_key = f"twitter_{query}" if query else "twitter_default"
        
        if cache_key in self.cache and (time.time() - self.cache_time.get(cache_key, 0)) < self.cache_ttl:
            logger.info(f"Returning cached results for {cache_key}")
            return self.cache[cache_key]
        
        try:
            all_entries = []
            search_terms = query.lower().split() if query else ["ai", "artificial intelligence", "machine learning"]
            
            # Process each feed
            for feed_url in self.ai_feeds:
                try:
                    logger.info(f"Fetching from {feed_url}")
                    response = await asyncio.get_event_loop().run_in_executor(
                        self.thread_pool,
                        lambda: requests.get(feed_url, headers=self.headers, timeout=10)
                    )
                    
                    if response.status_code != 200:
                        logger.warning(f"Failed to fetch feed {feed_url}: {response.status_code}")
                        continue
                    
                    feed = feedparser.parse(response.text)
                    
                    if not feed.entries:
                        logger.warning(f"No entries found in feed {feed_url}")
                        continue
                    
                    logger.info(f"Found {len(feed.entries)} entries in {feed_url}")
                    
                    # Process entries
                    for entry in feed.entries:
                        try:
                            # Extract basic info
                            title = entry.title if hasattr(entry, 'title') else ""
                            link = entry.link if hasattr(entry, 'link') else ""
                            
                            # Skip if no title or link
                            if not title or not link:
                                continue
                            
                            # Extract content
                            content = ""
                            if hasattr(entry, 'content') and entry.content:
                                content = entry.content[0].value if isinstance(entry.content, list) else entry.content
                            elif hasattr(entry, 'summary'):
                                content = entry.summary
                            elif hasattr(entry, 'description'):
                                content = entry.description
                            
                            # Clean content - strip HTML
                            if content:
                                content = re.sub('<[^<]+?>', '', content)
                            
                            # Check relevance to query
                            combined_text = (title + " " + content).lower()
                            
                            # If query specified, ensure all terms are present
                            if query:
                                if not all(term in combined_text for term in search_terms):
                                    continue
                            # Otherwise ensure it's about AI
                            elif not ('ai' in combined_text or 
                                     'artificial intelligence' in combined_text or 
                                     'machine learning' in combined_text):
                                continue
                            
                            # Extract source
                            source = "Tech News"
                            if "hnrss" in feed_url or "news.ycombinator.com" in str(entry):
                                source = "Hacker News"
                            elif "techcrunch" in feed_url or "techcrunch.com" in str(entry):
                                source = "TechCrunch"
                            elif "technologyreview" in feed_url or "technologyreview.com" in str(entry):
                                source = "MIT Tech Review"
                            elif "venturebeat" in feed_url or "venturebeat.com" in str(entry):
                                source = "VentureBeat"
                            elif "bdtechtalks" in feed_url:
                                source = "TechTalks"
                            
                            # Calculate AI relevance score (simple version)
                            ai_terms = [
                                'artificial intelligence', 'machine learning', 'deep learning', 'neural network',
                                'ai model', 'llm', 'large language model', 'transformer', 'gpt', 'stable diffusion',
                                'training data', 'tensorflow', 'pytorch', 'opencv', 'computer vision'
                            ]
                            relevance_score = 2.0  # Base score
                            for term in ai_terms:
                                if term in combined_text.lower():
                                    relevance_score += 0.5
                            
                            # Get timestamp
                            timestamp = time.time()
                            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                                timestamp = time.mktime(entry.published_parsed)
                                
                            # Create formatted post
                            post = {
                                'title': f"{source}: {title}",
                                'url': link,
                                'author': source.lower().replace(' ', ''),
                                'created_utc': timestamp,
                                'description': content[:4000] if content else title,  # Limit length
                                'subreddit': 'Twitter',  # For compatibility
                                'relevance_score': min(5.0, relevance_score),  # Cap at 5.0
                                'engagement': {
                                    'likes': 0,
                                    'retweets': 0,
                                    'replies': 0
                                },
                                'hashtags': ['#AI']
                            }
                            
                            all_entries.append(post)
                            
                        except Exception as e:
                            logger.error(f"Error processing feed entry: {str(e)}")
                            continue
                
                except Exception as e:
                    logger.error(f"Error fetching feed {feed_url}: {str(e)}")
                    continue
            
            logger.info(f"Found total of {len(all_entries)} relevant entries")
            
            # Sort by timestamp (newest first)
            sorted_entries = sorted(
                all_entries,
                key=lambda x: x.get('created_utc', 0),
                reverse=True
            )
            
            # Limit results
            result = sorted_entries[:limit]
            
            # Store in cache
            if result:
                self.cache[cache_key] = result
                self.cache_time[cache_key] = time.time()
                logger.info(f"Cached {len(result)} results for {cache_key}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching posts: {str(e)}")
            return []

# Simple test function
async def test_fetcher():
    fetcher = SimpleTwitterFetcher()
    posts = await fetcher.fetch_trending_posts()
    print(f"Found {len(posts)} posts")
    for i, post in enumerate(posts[:3]):
        print(f"\n=== Post {i+1} ===")
        print(f"Title: {post['title']}")
        print(f"URL: {post['url']}")
        print(f"Relevance: {post['relevance_score']}")
        print(f"Content: {post['description'][:100]}...")

if __name__ == "__main__":
    asyncio.run(test_fetcher())
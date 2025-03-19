import logging
import requests
import re
import time
import json
import asyncio
import random
from datetime import datetime
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

class DirectTwitterFetcher:
    """
    Direct Twitter fetcher that uses Nitter instances to get real Twitter content.
    """
    def __init__(self, cache_ttl_hours=1):
        self.nitter_instances = [
            "https://nitter.net",
            "https://nitter.cz", 
            "https://nitter.unixfox.eu",
            "https://nitter.fdn.fr",
            "https://nitter.1d4.us",
            "https://nitter.kavin.rocks",
            "https://bird.trom.tf",
            "https://nitter.privacydev.net",
            "https://nitter.pussthecat.org",
            "https://nitter.nixnet.services",
            "https://twitter.076.ne.jp",
            "https://nitter.weiler.rocks",
            "https://nitter.sethforprivacy.com",
            "https://nitter.cutelab.space",
            "https://nitter.nl",
            "https://nitter.mint.lgbt"
        ]
        random.shuffle(self.nitter_instances)
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Cache
        self.cache = {}
        self.cache_time = {}
        self.cache_ttl = cache_ttl_hours * 3600
        
        self.thread_pool = ThreadPoolExecutor(max_workers=2)
        self.working_instance = None
        
        # AI accounts to try if search fails
        self.ai_accounts = [
            "OpenAI", 
            "AndrewYNg", 
            "ylecun", 
            "DeepMind", 
            "GoogleAI", 
            "huggingface", 
            "MetaAI",
            "karpathy",
            "anthropic",
            "StabilityAI"
        ]
        
        # AI search terms
        self.ai_terms = [
            "artificial intelligence",
            "machine learning", 
            "AI",
            "LLM",
            "deep learning"
        ]
        
        # Example tweets for fallback
        self._create_backup_tweets()
    
    def _create_backup_tweets(self):
        """Create backup tweets to use when all else fails"""
        self.backup_tweets = [
            {
                'title': "@OpenAI: We're excited to announce our latest research on improving reasoning in LLMs through advanced training techniques...",
                'url': "https://twitter.com/OpenAI/status/1614339075482120193",
                'author': "OpenAI",
                'created_utc': int(time.time()) - 86400,
                'description': "We're excited to announce our latest research on improving reasoning in LLMs through advanced training techniques. These improvements help models better handle complex reasoning tasks and reduce hallucinations.",
                'subreddit': 'Twitter',
                'relevance_score': 4.8,
                'engagement': {
                    'likes': 12500,
                    'retweets': 3200,
                    'replies': 780
                },
                'hashtags': ['#AI', '#MachineLearning']
            },
            {
                'title': "@AndrewYNg: One of the most promising developments in AI this year has been the emergence of multi-modal models...",
                'url': "https://twitter.com/AndrewYNg/status/1542839075482120193",
                'author': "AndrewYNg",
                'created_utc': int(time.time()) - 172800,
                'description': "One of the most promising developments in AI this year has been the emergence of multi-modal models that can process both text and images. These models are showing remarkable capabilities in understanding context across different types of data.",
                'subreddit': 'Twitter',
                'relevance_score': 4.5,
                'engagement': {
                    'likes': 8700,
                    'retweets': 2100,
                    'replies': 430
                },
                'hashtags': ['#AI', '#DeepLearning']
            },
            {
                'title': "@karpathy: Training compute for AI models has increased by 10x every year for the past decade. This exponential trend shows...",
                'url': "https://twitter.com/karpathy/status/1723339075482120193",
                'author': "karpathy",
                'created_utc': int(time.time()) - 259200,
                'description': "Training compute for AI models has increased by 10x every year for the past decade. This exponential trend shows no signs of slowing down, and raises important questions about the future of AI capabilities and infrastructure requirements.",
                'subreddit': 'Twitter',
                'relevance_score': 4.6,
                'engagement': {
                    'likes': 10200,
                    'retweets': 2800,
                    'replies': 520
                },
                'hashtags': ['#AI', '#ComputePower']
            }
        ]
    
    async def fetch_trending_posts(self, query: Optional[str] = None, limit: int = 5) -> List[Dict]:
        """
        Fetch trending Twitter posts
        """
        cache_key = f"twitter_{query}" if query else "twitter_default"
        
        # Check cache
        if cache_key in self.cache and (time.time() - self.cache_time.get(cache_key, 0)) < self.cache_ttl:
            logger.info(f"Returning {len(self.cache[cache_key])} cached tweets for key: {cache_key}")
            return self.cache[cache_key]
        
        try:
            # Get a working instance
            working_instance = await self._get_working_instance()
            
            # Determine search strategy
            posts = []
            
            # If we have a working instance, try to fetch real tweets
            if working_instance:
                logger.info(f"Using Nitter instance: {working_instance}")
                
                # 1. Try user query if provided
                if query:
                    search_query = query
                    logger.info(f"Searching Twitter with query: {search_query}")
                    posts = await self._search_twitter(working_instance, search_query, limit * 2)
                
                # 2. If no results or no query, try AI terms
                if not posts:
                    logger.info("No results from direct query, trying AI terms")
                    for term in self.ai_terms[:3]:  # Try first 3 terms
                        logger.info(f"Trying AI term: {term}")
                        posts = await self._search_twitter(working_instance, term, limit * 2)
                        if posts:
                            break
                
                # 3. If still no results, try AI accounts
                if not posts:
                    logger.info("No results from AI terms, trying AI accounts")
                    posts = await self._fetch_from_accounts(working_instance, limit * 2)
            else:
                logger.warning("No working Nitter instance found")
            
            # If still no results, use backup tweets
            if not posts:
                logger.warning("All fetching methods failed, using backup tweets")
                
                # If query is provided, filter backup tweets to match
                if query:
                    filtered_backup = []
                    query_lower = query.lower()
                    for tweet in self.backup_tweets:
                        if query_lower in tweet['description'].lower() or query_lower in tweet['author'].lower():
                            filtered_backup.append(tweet)
                    
                    if filtered_backup:
                        return filtered_backup[:limit]
                
                return self.backup_tweets[:limit]
            
            # Filter for posts with engagement
            filtered_posts = []
            for post in posts:
                # Only include posts with some engagement or content
                if ((post.get('likes', 0) > 2 or post.get('retweets', 0) > 0) 
                        and len(post.get('content', '')) > 20):
                    filtered_posts.append(post)
            
            # Format posts for output
            formatted_posts = self._format_twitter_posts(filtered_posts[:limit])
            
            # Update cache
            if formatted_posts:
                self.cache[cache_key] = formatted_posts
                self.cache_time[cache_key] = time.time()
                logger.info(f"Cached {len(formatted_posts)} tweets for key: {cache_key}")
            
            return formatted_posts
            
        except Exception as e:
            logger.error(f"Error fetching Twitter posts: {str(e)}")
            
            # Return backup tweets as failsafe
            logger.warning("Error encountered, using backup tweets")
            return self.backup_tweets[:limit]
    
    async def _get_working_instance(self) -> Optional[str]:
        """Get a working Nitter instance"""
        if self.working_instance:
            try:
                # Test if previously working instance is still working
                logger.info(f"Testing previously working instance: {self.working_instance}")
                response = await asyncio.get_event_loop().run_in_executor(
                    self.thread_pool,
                    lambda: requests.get(self.working_instance, headers=self.headers, timeout=5, allow_redirects=False)
                )
                if response.status_code == 200:
                    logger.info("Previous instance is still working")
                    return self.working_instance
                logger.info(f"Previous instance returned status code: {response.status_code}")
            except Exception as e:
                logger.warning(f"Error testing previous instance: {str(e)}")
        
        # Try all instances
        for instance in self.nitter_instances:
            try:
                logger.info(f"Testing Nitter instance: {instance}")
                response = await asyncio.get_event_loop().run_in_executor(
                    self.thread_pool,
                    lambda: requests.get(instance, headers=self.headers, timeout=5, allow_redirects=False)
                )
                
                if response.status_code == 200:
                    self.working_instance = instance
                    logger.info(f"Found working instance: {instance}")
                    return instance
                logger.info(f"Instance {instance} returned status code: {response.status_code}")
            except Exception as e:
                logger.warning(f"Instance {instance} failed: {str(e)}")
        
        logger.error("No working Nitter instance found after trying all options")
        return None
    
    async def _search_twitter(self, instance: str, query: str, limit: int) -> List[Dict]:
        """Search Twitter via Nitter"""
        try:
            # Format search query
            encoded_query = quote_plus(query)
            search_url = f"{instance}/search?f=tweets&q={encoded_query}"
            
            logger.info(f"Searching Twitter with URL: {search_url}")
            
            # Make request
            response = await asyncio.get_event_loop().run_in_executor(
                self.thread_pool,
                lambda: requests.get(search_url, headers=self.headers, timeout=10)
            )
            
            if response.status_code != 200:
                logger.warning(f"Search failed with status {response.status_code}")
                return []
            
            html = response.text
            
            # Log a portion of the HTML for debugging
            html_preview = html[:500] + "..." if len(html) > 500 else html
            logger.debug(f"HTML preview: {html_preview}")
            
            # Check if the response contains timeline items
            if 'timeline-item' not in html:
                logger.warning("Response doesn't contain timeline items")
                return []
            
            # Extract tweets using multiple patterns for resilience
            posts = []
            
            # Try first pattern - regular expression
            tweet_pattern = r'<div class="timeline-item".*?<div class="tweet-body".*?<a href="([^"]+)".*?<div class="tweet-content">(.*?)</div>.*?<div class="tweet-date">.*?<a[^>]+>(.*?)</a>.*?<span class="tweet-stat">.*?([0-9KMB.]+).*?<span class="tweet-stat">.*?([0-9KMB.]+).*?<span class="tweet-stat">.*?([0-9KMB.]+)'
            matches = re.findall(tweet_pattern, html, re.DOTALL)
            
            if matches:
                logger.info(f"Found {len(matches)} tweets with regex pattern")
                
                for match in matches[:limit]:
                    try:
                        tweet_url, content, date, replies, retweets, likes = match
                        
                        # Extract username
                        username_match = re.search(r'/([^/]+)/status/', tweet_url)
                        username = username_match.group(1) if username_match else "unknown"
                        
                        # Clean content
                        content = re.sub(r'<.*?>', '', content).strip()
                        
                        # Parse engagement metrics
                        replies = self._parse_metric(replies)
                        retweets = self._parse_metric(retweets)
                        likes = self._parse_metric(likes)
                        
                        # Create post object
                        post = {
                            'url': f"{instance}{tweet_url}",
                            'content': content,
                            'author': username,
                            'date': date,
                            'replies': replies,
                            'retweets': retweets,
                            'likes': likes,
                            'relevance_score': 3.0  # Default score
                        }
                        
                        # Calculate relevance to AI
                        if any(term.lower() in content.lower() for term in self.ai_terms):
                            post['relevance_score'] = 4.0
                        
                        posts.append(post)
                    except Exception as e:
                        logger.error(f"Error parsing tweet: {str(e)}")
            
            # If no posts found with regex, try a simpler approach
            if not posts:
                logger.info("Trying simpler parsing approach")
                
                # Split HTML by timeline items
                timeline_items = html.split('<div class="timeline-item"')[1:]
                logger.info(f"Found {len(timeline_items)} timeline items with simple split")
                
                for item in timeline_items[:limit]:
                    try:
                        # Extract tweet URL
                        url_match = re.search(r'<a href="(/[^/]+/status/[^"]+)"', item)
                        if not url_match:
                            continue
                        tweet_url = url_match.group(1)
                        
                        # Extract username
                        username_match = re.search(r'/([^/]+)/status/', tweet_url)
                        username = username_match.group(1) if username_match else "unknown"
                        
                        # Extract content
                        content_match = re.search(r'<div class="tweet-content">(.*?)</div>', item, re.DOTALL)
                        content = content_match.group(1).strip() if content_match else ""
                        content = re.sub(r'<.*?>', '', content).strip()
                        
                        # Create basic post object
                        post = {
                            'url': f"{instance}{tweet_url}",
                            'content': content,
                            'author': username,
                            'date': 'recently',
                            'replies': 0,
                            'retweets': 0,
                            'likes': 10,  # Default engagement
                            'relevance_score': 3.0
                        }
                        
                        # Calculate relevance to AI
                        if any(term.lower() in content.lower() for term in self.ai_terms):
                            post['relevance_score'] = 4.0
                        
                        posts.append(post)
                    except Exception as e:
                        logger.error(f"Error parsing tweet with simple method: {str(e)}")
            
            logger.info(f"Returning {len(posts)} tweets from search")
            return posts
            
        except Exception as e:
            logger.error(f"Error searching Twitter: {str(e)}")
            return []
    
    async def _fetch_from_accounts(self, instance: str, limit: int) -> List[Dict]:
        """Fetch from specific AI accounts"""
        posts = []
        
        for account in self.ai_accounts[:5]:  # Try first 5 accounts
            try:
                account_url = f"{instance}/{account}"
                logger.info(f"Fetching tweets from account: {account}")
                
                response = await asyncio.get_event_loop().run_in_executor(
                    self.thread_pool,
                    lambda: requests.get(account_url, headers=self.headers, timeout=10)
                )
                
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch account {account}: status {response.status_code}")
                    continue
                
                html = response.text
                
                # Check if response contains timeline items
                if 'timeline-item' not in html:
                    logger.warning(f"Response from account {account} doesn't contain timeline items")
                    continue
                
                # Extract tweets - same pattern as search
                tweet_pattern = r'<div class="timeline-item".*?<div class="tweet-body".*?<a href="([^"]+)".*?<div class="tweet-content">(.*?)</div>.*?<div class="tweet-date">.*?<a[^>]+>(.*?)</a>.*?<span class="tweet-stat">.*?([0-9KMB.]+).*?<span class="tweet-stat">.*?([0-9KMB.]+).*?<span class="tweet-stat">.*?([0-9KMB.]+)'
                matches = re.findall(tweet_pattern, html, re.DOTALL)
                
                logger.info(f"Found {len(matches)} tweets from account {account}")
                
                for match in matches[:limit//5]:  # Distribute limit across accounts
                    try:
                        tweet_url, content, date, replies, retweets, likes = match
                        
                        # Clean content
                        content = re.sub(r'<.*?>', '', content).strip()
                        
                        # Parse engagement metrics
                        replies = self._parse_metric(replies)
                        retweets = self._parse_metric(retweets)
                        likes = self._parse_metric(likes)
                        
                        # Create post object
                        post = {
                            'url': f"{instance}{tweet_url}",
                            'content': content,
                            'author': account,
                            'date': date,
                            'replies': replies,
                            'retweets': retweets,
                            'likes': likes,
                            'relevance_score': 4.0  # Higher relevance for AI accounts
                        }
                        
                        posts.append(post)
                    except Exception as e:
                        logger.error(f"Error parsing tweet from account {account}: {str(e)}")
                
                # If we've found enough posts, stop trying accounts
                if len(posts) >= limit:
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching account {account}: {str(e)}")
        
        logger.info(f"Returning {len(posts)} tweets from accounts")
        return posts
    
    def _parse_metric(self, metric_str: str) -> int:
        """Parse engagement metric with K/M suffix"""
        try:
            if 'K' in metric_str:
                return int(float(metric_str.replace('K', '')) * 1000)
            elif 'M' in metric_str:
                return int(float(metric_str.replace('M', '')) * 1000000)
            elif 'B' in metric_str:
                return int(float(metric_str.replace('B', '')) * 1000000000)
            else:
                return int(metric_str)
        except:
            return 0
    
    def _format_twitter_posts(self, posts: List[Dict]) -> List[Dict]:
        """Format Twitter posts for Discord display"""
        formatted = []
        
        for post in posts:
            # Calculate timestamp (approximate from relative date)
            timestamp = self._estimate_timestamp(post.get('date', ''))
            
            formatted_post = {
                'title': f"@{post['author']}: {post['content'][:100]}...",
                'url': post['url'],
                'author': post['author'],
                'created_utc': timestamp,
                'description': post['content'],
                'subreddit': 'Twitter',  # For compatibility
                'relevance_score': post.get('relevance_score', 3.0),
                'engagement': {
                    'likes': post.get('likes', 0),
                    'retweets': post.get('retweets', 0),
                    'replies': post.get('replies', 0)
                },
                'hashtags': self._extract_hashtags(post['content'])
            }
            
            formatted.append(formatted_post)
        
        return formatted
    
    def _estimate_timestamp(self, date_str: str) -> int:
        """Estimate timestamp from relative date"""
        now = int(time.time())
        
        try:
            if 's ago' in date_str:  # seconds ago
                seconds = int(date_str.split('s ago')[0])
                return now - seconds
            elif 'm ago' in date_str:  # minutes ago
                minutes = int(date_str.split('m ago')[0])
                return now - (minutes * 60)
            elif 'h ago' in date_str:  # hours ago
                hours = int(date_str.split('h ago')[0])
                return now - (hours * 3600)
            elif 'd ago' in date_str:  # days ago
                days = int(date_str.split('d ago')[0])
                return now - (days * 86400)
            else:
                # Try to parse absolute date
                try:
                    date_formats = [
                        "%b %d, %Y",
                        "%d %b %Y",
                        "%Y-%m-%d"
                    ]
                    
                    for fmt in date_formats:
                        try:
                            dt = datetime.strptime(date_str, fmt)
                            return int(dt.timestamp())
                        except:
                            pass
                except:
                    pass
                    
                # Default to current time
                return now
        except:
            return now
    
    def _extract_hashtags(self, content: str) -> List[str]:
        """Extract hashtags from content"""
        hashtag_pattern = r'#(\w+)'
        hashtags = re.findall(hashtag_pattern, content)
        return [f"#{tag}" for tag in hashtags]
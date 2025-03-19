import logging
import requests
import re
import time
import asyncio
import random
from datetime import datetime
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urlencode

from twitter_utils import extract_engagement_stats, format_post_for_output

logger = logging.getLogger(__name__)

# Popular AI search terms to discover trending content
AI_SEARCH_TERMS = [
    "artificial intelligence",
    "machine learning", 
    "AI research",
    "LLM",
    "generative AI",
    "deep learning",
    "AI ethics",
    "AI news",
    "AI breakthrough",
    "large language model",
    "AI tools",
    "AI application",
    "AI startup",
    "AI technology"
]

# Some known research accounts as a fallback
RESEARCH_ACCOUNTS = [
    "OpenAI",
    "DeepMind",
    "stanfordnlp",
    "StabilityAI"
]

class NitterMethod:
    """
    Implements Twitter post fetching using Nitter instances
    with focus on discovering trending content from diverse sources
    """
    def __init__(self, thread_pool: ThreadPoolExecutor):
        # More instances for redundancy
        self.nitter_instances = [
            "https://nitter.net",
            "https://nitter.cz", 
            "https://nitter.unixfox.eu",
            "https://nitter.fdn.fr",
            "https://nitter.1d4.us",
            "https://nitter.kavin.rocks",
            "https://nitter.esmailelbob.xyz",
            "https://nitter.poast.org",
            "https://bird.trom.tf",
            "https://nitter.privacydev.net",
            "https://nitter.pussthecat.org",
            "https://nitter.nixnet.services"
        ]
        random.shuffle(self.nitter_instances)  # Randomize to distribute load
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.google.com/'
        }
        self.thread_pool = thread_pool
        self.working_instance = None  # Will be set the first time a working instance is found
    
    async def _get_working_nitter_instance(self) -> Optional[str]:
        """Find a working Nitter instance by testing them"""
        # If we already found a working instance, try that first
        if self.working_instance:
            try:
                logger.info(f"Testing previous working instance: {self.working_instance}")
                response = await asyncio.get_event_loop().run_in_executor(
                    self.thread_pool,
                    lambda: requests.get(f"{self.working_instance}", 
                                        headers=self.headers, 
                                        timeout=5,
                                        allow_redirects=False)  # Don't follow redirects
                )
                
                # Check if it's still working
                if response.status_code == 200 and 'nitter' in response.text.lower():
                    logger.info(f"Using previously working instance: {self.working_instance}")
                    return self.working_instance
                else:
                    logger.warning(f"Previous working instance no longer working: {self.working_instance}")
                    self.working_instance = None
                    
            except Exception as e:
                logger.warning(f"Previous working instance failed: {str(e)}")
                self.working_instance = None
        
        # Try all the instances until we find a working one
        for instance in self.nitter_instances:
            try:
                logger.info(f"Testing Nitter instance: {instance}")
                response = await asyncio.get_event_loop().run_in_executor(
                    self.thread_pool,
                    lambda: requests.get(f"{instance}", 
                                        headers=self.headers, 
                                        timeout=5,
                                        allow_redirects=False)  # Don't follow redirects
                )
                
                # Check if it's a real Nitter instance
                if response.status_code == 200 and 'nitter' in response.text.lower():
                    logger.info(f"Using working Nitter instance: {instance}")
                    self.working_instance = instance  # Remember this working instance
                    return instance
                else:
                    logger.warning(f"Nitter instance {instance} returned status code {response.status_code}")
                    
            except Exception as e:
                logger.warning(f"Nitter instance {instance} failed: {str(e)}")
                continue
        
        logger.error("No working Nitter instances found")
        return None
    
    async def fetch_posts(self, search_query: str, limit: int) -> List[Dict]:
        """
        Fetch posts from trending AI content using Nitter search
        
        Args:
            search_query: The search query (if provided by user)
            limit: Maximum number of posts to return
            
        Returns:
            List of posts from diverse sources
        """
        all_posts = []
        
        # Get a working Nitter instance
        nitter_base = await self._get_working_nitter_instance()
        if not nitter_base:
            return []
        
        # If user provided a specific query, prioritize that
        if search_query and search_query.lower() not in ["ai", "artificial intelligence"]:
            specific_query_posts = await self._fetch_by_search(nitter_base, search_query, limit)
            if specific_query_posts:
                all_posts.extend(specific_query_posts)
            
        # Only if we don't have enough posts, try more general AI searches
        if len(all_posts) < limit:
            # Try a few random AI search terms to get diverse content
            search_terms = random.sample(AI_SEARCH_TERMS, min(3, len(AI_SEARCH_TERMS)))
            
            for term in search_terms:
                # Skip if it's the same as the user query
                if term.lower() == search_query.lower():
                    continue
                    
                # Try different filters to get diverse content
                # "top" for high engagement content
                top_posts = await self._fetch_by_search(nitter_base, term, limit//2, filter_type="top")
                if top_posts:
                    all_posts.extend(top_posts)
                
                # "latest" for recent content that might be trending but new
                if len(all_posts) < limit:
                    latest_posts = await self._fetch_by_search(nitter_base, term, limit//2, filter_type="latest")
                    if latest_posts:
                        all_posts.extend(latest_posts)
                
                # If we have enough posts, stop
                if len(all_posts) >= limit * 2:
                    break
        
        # If we still don't have enough posts, try popular hashtags
        if len(all_posts) < limit:
            hashtag_posts = await self._fetch_by_hashtags(nitter_base, limit)
            if hashtag_posts:
                all_posts.extend(hashtag_posts)
        
        # If we STILL don't have enough posts, fall back to known accounts
        if len(all_posts) < limit:
            account_posts = await self.fetch_from_accounts(limit)
            if account_posts:
                all_posts.extend(account_posts)
        
        # Remove duplicates based on URL
        seen_urls = set()
        unique_posts = []
        for post in all_posts:
            if post['url'] not in seen_urls:
                seen_urls.add(post['url'])
                unique_posts.append(post)
        
        # Prioritize diversity - we want posts from different authors
        diverse_posts = []
        seen_authors = set()
        
        # First pass: include one post from each author
        for post in unique_posts:
            author = post.get('author_username', '')
            if author and author not in seen_authors:
                seen_authors.add(author)
                diverse_posts.append(post)
                
                if len(diverse_posts) >= limit:
                    break
        
        # Second pass: if we still need more posts, add additional ones
        if len(diverse_posts) < limit:
            for post in unique_posts:
                if post not in diverse_posts:
                    diverse_posts.append(post)
                    
                    if len(diverse_posts) >= limit:
                        break
        
        logger.info(f"Found {len(diverse_posts)} diverse posts from {len(seen_authors)} different authors")
        return diverse_posts[:limit]
    
    async def _fetch_by_search(self, nitter_base: str, search_query: str, limit: int, filter_type: str = "tweets") -> List[Dict]:
        """
        Fetch posts by search query with specified filter
        
        Args:
            nitter_base: Base URL of Nitter instance
            search_query: Search query
            limit: Maximum number of posts
            filter_type: Filter type ("tweets", "top", "latest", "media", etc.)
            
        Returns:
            List of posts
        """
        try:
            # Format search URL with query parameters
            encoded_query = quote_plus(search_query)
            
            # Use different filters based on type
            if filter_type == "top":
                search_url = f"{nitter_base}/search?f=tweets&q={encoded_query}&since=7d&e-verified=on&e-nativeretweets=on"
            elif filter_type == "latest":
                search_url = f"{nitter_base}/search?f=tweets&q={encoded_query}&since=2d"
            else:
                search_url = f"{nitter_base}/search?f={filter_type}&q={encoded_query}&since=7d"
                
            logger.info(f"Fetching by search: {search_url}")
            
            # Fetch search results page
            response = await asyncio.get_event_loop().run_in_executor(
                self.thread_pool,
                lambda: requests.get(search_url, headers=self.headers, timeout=10, allow_redirects=False)
            )
            
            # Check for redirect or failure
            if response.status_code != 200 or 'support' in response.url:
                logger.error(f"Failed to fetch from Nitter, status code: {response.status_code}, URL: {response.url}")
                return []
            
            # Check if the response contains actual tweets
            if 'timeline-item' not in response.text:
                logger.warning(f"Response doesn't contain timeline items")
                return []
            
            # Parse posts from the HTML response
            posts = await self._parse_nitter_content(response.text, nitter_base)
            if not posts:
                logger.warning(f"No posts found for query: {search_query}")
                return []
            
            logger.info(f"Found {len(posts)} posts from search '{search_query}' with filter '{filter_type}'")
            return posts
            
        except Exception as e:
            logger.error(f"Error in search method: {str(e)}", exc_info=True)
            return []
    
    async def _fetch_by_hashtags(self, nitter_base: str, limit: int) -> List[Dict]:
        """
        Fetch posts by popular AI hashtags
        
        Args:
            nitter_base: Base URL of Nitter instance
            limit: Maximum number of posts
            
        Returns:
            List of posts
        """
        try:
            # Popular AI hashtags
            hashtags = [
                "AI", "ArtificialIntelligence", "MachineLearning", "DeepLearning",
                "GenerativeAI", "AIEthics", "LLM", "AIresearch"
            ]
            
            all_posts = []
            
            # Try a few random hashtags
            for hashtag in random.sample(hashtags, min(3, len(hashtags))):
                hashtag_url = f"{nitter_base}/search?f=tweets&q=%23{hashtag}&since=7d"
                logger.info(f"Fetching by hashtag: #{hashtag}")
                
                response = await asyncio.get_event_loop().run_in_executor(
                    self.thread_pool,
                    lambda: requests.get(hashtag_url, headers=self.headers, timeout=10, allow_redirects=False)
                )
                
                if response.status_code != 200 or 'support' in response.url:
                    logger.warning(f"Failed to fetch hashtag #{hashtag}")
                    continue
                
                if 'timeline-item' not in response.text:
                    logger.warning(f"No timeline items for hashtag #{hashtag}")
                    continue
                
                # Parse posts from the HTML response
                hashtag_posts = await self._parse_nitter_content(response.text, nitter_base)
                if hashtag_posts:
                    all_posts.extend(hashtag_posts)
                    
                    if len(all_posts) >= limit:
                        break
            
            logger.info(f"Found {len(all_posts)} posts from hashtags")
            return all_posts
            
        except Exception as e:
            logger.error(f"Error fetching by hashtags: {str(e)}", exc_info=True)
            return []
    
    async def fetch_from_accounts(self, limit: int) -> List[Dict]:
        """
        Fetch posts from known AI research accounts as a fallback
        
        Args:
            limit: Maximum number of posts to return
            
        Returns:
            List of posts
        """
        try:
            all_posts = []
            working_instance = await self._get_working_nitter_instance()
            
            if not working_instance:
                return []
            
            # Try research accounts until we have enough posts
            for account in RESEARCH_ACCOUNTS:
                try:
                    account_url = f"{working_instance}/{account}"
                    logger.info(f"Fetching posts from research account: {account}")
                    
                    response = await asyncio.get_event_loop().run_in_executor(
                        self.thread_pool,
                        lambda: requests.get(account_url, headers=self.headers, timeout=10, allow_redirects=False)
                    )
                    
                    if response.status_code != 200 or 'timeline-item' not in response.text:
                        logger.warning(f"Failed to fetch from account {account}")
                        continue
                    
                    # Parse posts from the HTML response
                    account_posts = await self._parse_nitter_content(response.text, working_instance)
                    
                    if account_posts:
                        # Add source account to each post for better filtering
                        for post in account_posts:
                            post['source_account'] = account
                            post['is_research_account'] = True
                            all_posts.append(post)
                        
                        if len(all_posts) >= limit:
                            break
                        
                except Exception as e:
                    logger.error(f"Error fetching account {account}: {str(e)}")
                    continue
            
            logger.info(f"Found {len(all_posts)} posts from research accounts")
            return all_posts
            
        except Exception as e:
            logger.error(f"Error in accounts method: {str(e)}", exc_info=True)
            return []
    
    async def _parse_nitter_content(self, html_content: str, nitter_base: str) -> List[Dict]:
        """
        Parse tweets from Nitter HTML content
        
        Args:
            html_content: HTML content from Nitter page
            nitter_base: Base URL of the Nitter instance
            
        Returns:
            List of parsed tweets
        """
        try:
            posts = []
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all tweet containers
            tweet_elements = soup.select('.timeline-item')
            logger.info(f"Found {len(tweet_elements)} tweet elements in HTML")
            
            for tweet in tweet_elements:
                try:
                    # Skip pinned, retweets if they don't have their own content
                    if tweet.select_one('.pinned') or (tweet.select_one('.retweet-header') and not tweet.select_one('.quote')):
                        continue
                    
                    # Get tweet ID and URL
                    tweet_link = tweet.select_one('.tweet-link')
                    if not tweet_link:
                        continue
                    
                    tweet_url = tweet_link['href']
                    full_url = f"{nitter_base}{tweet_url}"
                    
                    # Get author info
                    author_name = tweet.select_one('.fullname').text.strip() if tweet.select_one('.fullname') else "Unknown"
                    author_username = tweet.select_one('.username').text.strip() if tweet.select_one('.username') else "unknown"
                    
                    # Clean up username (remove @ symbol if present)
                    if author_username.startswith('@'):
                        author_username = author_username[1:]
                    
                    # Get tweet content
                    content_elem = tweet.select_one('.tweet-content')
                    content = content_elem.text.strip() if content_elem else ""
                    
                    # Skip tweets that are too short - they're often not informative
                    if len(content) < 20:
                        continue
                    
                    # Extract timestamp
                    time_elem = tweet.select_one('.tweet-date')
                    timestamp = int(time.time())  # Default to current time
                    if time_elem and time_elem.select_one('a'):
                        time_str = time_elem.select_one('a').get('title')
                        if time_str:
                            try:
                                dt = datetime.strptime(time_str, '%b %d, %Y · %I:%M %p %Z')
                                timestamp = int(dt.timestamp())
                            except ValueError:
                                pass
                    
                    # Get engagement metrics
                    stats = tweet.select_one('.tweet-stats')
                    replies, retweets, likes = extract_engagement_stats(stats)
                    
                    # Extract hashtags
                    hashtags = []
                    for tag in tweet.select('.hashtag'):
                        if tag.text.strip().startswith('#'):
                            hashtags.append(tag.text.strip())
                    
                    # Extract media info if available (images, videos, etc.)
                    media = {}
                    if tweet.select_one('.attachments'):
                        media_elems = tweet.select('.attachment')
                        if media_elems:
                            media['has_media'] = True
                            media['media_count'] = len(media_elems)
                    
                    # Check for links
                    has_links = bool(tweet.select('.twitter-timeline-link'))
                    
                    # Check for verified status
                    is_verified = bool(tweet.select_one('.verified-icon'))
                    
                    post_data = {
                        'author_name': author_name,
                        'author_username': author_username,
                        'content': content,
                        'url': full_url,
                        'timestamp': timestamp,
                        'replies': replies,
                        'retweets': retweets,
                        'likes': likes,
                        'hashtags': hashtags,
                        'has_links': has_links,
                        'media': media,
                        'is_verified': is_verified,
                        'type': 'twitter_post',
                        'raw_engagement_score': (likes*1.0 + retweets*2.0 + replies*1.5)
                    }
                    
                    posts.append(post_data)
                
                except Exception as e:
                    logger.error(f"Error parsing tweet: {str(e)}")
                    continue
            
            logger.info(f"Successfully parsed {len(posts)} tweets from Nitter")
            return posts
        
        except Exception as e:
            logger.error(f"Error parsing tweets from HTML: {str(e)}", exc_info=True)
            return []
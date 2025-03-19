import logging
import requests
import feedparser
import time
import asyncio
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus
import re

from twitter_utils import format_post_for_output, strip_html_tags

logger = logging.getLogger(__name__)

class RSSMethod:
    """
    Implements Twitter/AI content fetching using RSS feeds
    """
    def __init__(self, thread_pool: ThreadPoolExecutor):
        self.thread_pool = thread_pool
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml'
        }
        # List of AI/ML specific RSS feeds
        self.ai_feeds = [
            "https://hnrss.org/newest?q=AI+OR+artificial+intelligence+OR+machine+learning&count=25",
            "https://techcrunch.com/tag/artificial-intelligence/feed/",
            "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
            "https://www.deeplearning.ai/feed/",
            "https://blogs.nvidia.com/feed/",
            "https://lexfridman.com/feed/",
            "https://venturebeat.com/category/ai/feed/",
            "https://ai.googleblog.com/atom.xml"
        ]
        # Use a cache to avoid refetching the same feed too often
        self.feed_cache = {}
        self.feed_cache_time = {}
        self.feed_cache_ttl = 1800  # 30 minutes
        
    async def fetch_posts(self, search_query: str, limit: int) -> List[Dict]:
        """
        Fetch AI-related posts from RSS feeds
        
        Args:
            search_query: The search query
            limit: Maximum number of posts to return
            
        Returns:
            List of posts
        """
        try:
            all_entries = []
            search_terms = search_query.lower().split()
            
            # Add search-specific feeds when a specific query is provided
            feeds_to_check = self.ai_feeds.copy()
            if search_query:
                feeds_to_check.append(f"https://hnrss.org/newest?q={quote_plus(search_query)}&count=15")
                feeds_to_check.append(f"https://news.google.com/rss/search?q={quote_plus(search_query+' AI')}&hl=en-US&gl=US&ceid=US:en")
            
            # Fetch from multiple feeds
            for feed_url in feeds_to_check:
                try:
                    # Check if we have a fresh cached version
                    if feed_url in self.feed_cache and time.time() - self.feed_cache_time.get(feed_url, 0) < self.feed_cache_ttl:
                        logger.info(f"Using cached feed: {feed_url}")
                        feed = self.feed_cache[feed_url]
                    else:
                        logger.info(f"Fetching feed: {feed_url}")
                        response = await asyncio.get_event_loop().run_in_executor(
                            self.thread_pool,
                            lambda: requests.get(feed_url, headers=self.headers, timeout=10)
                        )
                        
                        if response.status_code != 200:
                            logger.warning(f"Failed to fetch feed {feed_url}: {response.status_code}")
                            continue
                        
                        feed = feedparser.parse(response.text)
                        
                        # Cache the feed
                        self.feed_cache[feed_url] = feed
                        self.feed_cache_time[feed_url] = time.time()
                    
                    if not feed.entries:
                        logger.warning(f"No entries found in feed {feed_url}")
                        continue
                    
                    # Process each entry
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
                                
                            # Clean content
                            if content:
                                content = strip_html_tags(content)
                            
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
                            elif "deeplearning.ai" in feed_url:
                                source = "DeepLearning.AI"
                            elif "nvidia" in feed_url or "nvidia.com" in str(entry):
                                source = "NVIDIA AI"
                            elif "googleblog" in feed_url:
                                source = "Google AI"
                            elif "lexfridman" in feed_url:
                                source = "Lex Fridman"
                            elif "news.google.com" in feed_url:
                                source = "Google News"
                                
                            # Get timestamp
                            timestamp = time.time()
                            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                                timestamp = time.mktime(entry.published_parsed)
                            
                            # Create post data
                            post_data = {
                                'title': title,
                                'content': content,
                                'url': link,
                                'source': source,
                                'author_name': source,
                                'author_username': source.lower().replace(' ', ''),
                                'timestamp': timestamp,
                                'type': 'rss_post',
                                'raw_engagement_score': 5.0  # Default engagement score for RSS items
                            }
                            
                            # Check relevance to search query if provided
                            if search_query:
                                combined_text = (title + " " + content).lower()
                                # Check if all search terms are present
                                if all(term in combined_text for term in search_terms):
                                    all_entries.append(post_data)
                            else:
                                # If no specific query, include all AI-related content
                                all_entries.append(post_data)
                                
                        except Exception as e:
                            logger.error(f"Error processing feed entry: {str(e)}")
                            continue
                    
                except Exception as e:
                    logger.error(f"Error fetching feed {feed_url}: {str(e)}")
                    continue
            
            logger.info(f"Found {len(all_entries)} entries from RSS feeds")
            
            # Sort by recency
            sorted_entries = sorted(
                all_entries,
                key=lambda x: x['timestamp'],
                reverse=True
            )[:limit]
            
            # Format entries as posts
            formatted_posts = []
            for i, entry in enumerate(sorted_entries):
                formatted_post = {
                    'title': f"{entry['source']}: {entry['title'][:100]}",
                    'url': entry['url'],
                    'author_name': entry['source'],
                    'author_username': entry['author_username'],
                    'content': entry['content'][:2000] if entry['content'] else entry['title'],
                    'timestamp': entry['timestamp'],
                    'type': entry['type'],
                    'raw_engagement_score': entry['raw_engagement_score'],
                    'replies': 0,
                    'retweets': 0,
                    'likes': 0,
                    'hashtags': ['#AI']
                }
                formatted_posts.append(formatted_post)
            
            return formatted_posts
            
        except Exception as e:
            logger.error(f"Error in RSS method: {str(e)}", exc_info=True)
            return []
import feedparser
from typing import List, Dict, Optional
import logging
from cache_manager import CacheManager
from datetime import datetime
import time
import re
from html import unescape
import requests
import trafilatura
import textwrap

logger = logging.getLogger(__name__)

# AI/ML related keywords for filtering
AI_ML_KEYWORDS = {
    'high_relevance': [
        'artificial intelligence', 'machine learning', 'deep learning', 'neural network',
        'ai model', 'llm', 'large language model', 'transformer', 'gpt', 'stable diffusion',
        'training data', 'tensorflow', 'pytorch', 'opencv', 'computer vision'
    ],
    'medium_relevance': [
        'algorithm', 'dataset', 'training', 'inference', 'prediction',
        'classification', 'clustering', 'regression', 'automation',
        'robotics', 'nlp', 'natural language', 'recognition'
    ]
}

def calculate_relevance_score(text: str) -> float:
    """Calculate relevance score based on AI/ML keywords"""
    text = text.lower()
    score = 0.0

    # Check for high relevance keywords (2 points each)
    for keyword in AI_ML_KEYWORDS['high_relevance']:
        if keyword in text:
            score += 2.0

    # Check for medium relevance keywords (1 point each)
    for keyword in AI_ML_KEYWORDS['medium_relevance']:
        if keyword in text:
            score += 1.0

    return score

def strip_html_tags(text: str) -> str:
    """Remove HTML tags while preserving basic text structure"""
    if not text:
        return ""
    try:
        # First unescape HTML entities
        text = unescape(text)

        # Convert HTML line breaks to newlines
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'<p.*?>', '\n', text)
        text = re.sub(r'</p>', '\n', text)

        # Remove HTML tags while preserving content
        clean = re.compile('<.*?>')
        text = re.sub(clean, '', text)

        # Process each line
        formatted_lines = []
        for line in text.split('\n'):
            stripped = line.strip()
            if stripped:
                # Format bullet points
                if stripped.startswith(('*', '-')):
                    formatted_lines.append('• ' + stripped[1:].strip())
                else:
                    formatted_lines.append(stripped)

        # Join with single newlines
        text = '\n'.join(formatted_lines)
        return text.strip()

    except Exception as e:
        logger.error(f"Error cleaning HTML text: {str(e)}")
        return text

class RedditFetcher:
    """Fetches trending posts from AI-related subreddits with content filtering"""
    def __init__(self, default_subreddits: List[str], cache_manager: CacheManager):
        self.default_subreddits = default_subreddits
        self.cache = cache_manager
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.min_relevance_score = 2.0  # Minimum score for a post to be included
        logger.info(f"RedditFetcher initialized with subreddits: {', '.join(default_subreddits)}")

    def extract_post_content(self, entry) -> tuple[str, float]:
        """Extract and clean post content from feed entry, returns (content, relevance_score)"""
        try:
            content = None
            logger.info("Starting post content extraction")

            # First try Reddit API
            if hasattr(entry, 'link'):
                try:
                    post_id = entry.link.split('/comments/')[1].split('/')[0] if '/comments/' in entry.link else None
                    if post_id:
                        api_url = f"https://www.reddit.com/by_id/t3_{post_id}.json"
                        logger.info(f"Fetching from Reddit API: {api_url}")

                        response = requests.get(api_url, headers=self.headers, timeout=10)
                        if response.status_code == 200:
                            data = response.json()
                            post_data = data['data']['children'][0]['data']
                            logger.debug(f"Post data retrieved: {post_data.get('title')}")

                            # Calculate relevance score from title and selftext
                            title_score = calculate_relevance_score(post_data.get('title', ''))
                            content_score = calculate_relevance_score(post_data.get('selftext', ''))
                            relevance_score = title_score + content_score
                            logger.info(f"Title relevance: {title_score}, Content relevance: {content_score}")

                            # For text posts, use selftext
                            if post_data.get('selftext'):
                                content = post_data['selftext']
                                logger.info(f"Got content from selftext (length: {len(content)})")

                except Exception as e:
                    logger.error(f"Error fetching from Reddit API: {str(e)}")
                    relevance_score = 0.0

            # If no API content, try RSS feed fields
            if not content:
                logger.info("Trying RSS feed fields")
                relevance_score = calculate_relevance_score(entry.title if hasattr(entry, 'title') else '')

                for field in ['content', 'summary_detail', 'summary', 'description']:
                    if hasattr(entry, field):
                        try:
                            field_content = getattr(entry, field)
                            if isinstance(field_content, dict) and field_content.get('value'):
                                field_content = field_content['value']
                            elif isinstance(field_content, list) and field_content:
                                field_content = field_content[0].value

                            if field_content and len(str(field_content).strip()) > 10:
                                content = str(field_content)
                                relevance_score += calculate_relevance_score(content)
                                logger.info(f"Got content from {field} (length: {len(content)})")
                                break
                        except Exception as e:
                            logger.error(f"Error with field {field}: {str(e)}")

            if not content:
                logger.warning("No content found in entry")
                return "Content unavailable. Please click the title to read more.", 0.0

            # Clean and format content
            content = strip_html_tags(content)
            logger.info(f"Content after HTML cleaning (length: {len(content)})")

            return content, relevance_score

        except Exception as e:
            logger.error(f"Error extracting content: {str(e)}")
            return "Error loading content. Please click the title to read more.", 0.0

    async def fetch_trending_posts(self, subreddit: Optional[str] = None, limit: int = 5) -> List[Dict]:
        """Fetch trending posts from a subreddit with AI/ML content filtering"""
        subreddit_name = subreddit or self.default_subreddits[0]
        cache_key = f"reddit_{subreddit_name}"

        # Check cache first
        cached_posts = self.cache.get(cache_key)
        if cached_posts:
            logger.info(f"Returning cached posts for {subreddit_name}")
            return cached_posts

        try:
            feed_url = f"https://www.reddit.com/r/{subreddit_name}/.rss"
            logger.info(f"Fetching RSS feed from: {feed_url}")

            response = requests.get(feed_url, headers=self.headers, timeout=10)
            logger.info(f"RSS feed response status: {response.status_code}")

            if response.status_code == 200:
                feed = feedparser.parse(response.text)
                logger.info(f"Found {len(feed.entries)} entries in RSS feed")

                posts = []
                for entry in feed.entries[:limit * 2]:  # Fetch more posts to filter
                    try:
                        # Extract and format post content
                        content, relevance_score = self.extract_post_content(entry)
                        logger.info(f"Post title: {entry.title if hasattr(entry, 'title') else 'No title'}")
                        logger.info(f"Relevance score: {relevance_score}")

                        # Only include posts with sufficient AI/ML relevance
                        if relevance_score >= self.min_relevance_score:
                            post_data = {
                                'title': strip_html_tags(entry.title),
                                'url': entry.link,
                                'author': entry.author if hasattr(entry, 'author') else 'Unknown',
                                'created_utc': time.mktime(entry.published_parsed) if hasattr(entry, 'published_parsed') else time.time(),
                                'description': content,
                                'subreddit': subreddit_name,
                                'relevance_score': relevance_score
                            }

                            logger.info(f"Processed post data - Title: {post_data['title'][:50]}... Content length: {len(post_data['description'])}")
                            posts.append(post_data)

                            # Stop if we have enough relevant posts
                            if len(posts) >= limit:
                                break

                    except Exception as e:
                        logger.error(f"Error processing post in r/{subreddit_name}: {str(e)}")
                        continue

                if posts:
                    # Sort by relevance score
                    posts.sort(key=lambda x: x['relevance_score'], reverse=True)
                    self.cache.set(cache_key, posts)
                    logger.info(f"Cached {len(posts)} relevant posts for r/{subreddit_name}")
                    return posts

            logger.warning(f"Failed to fetch posts from r/{subreddit_name}, status code: {response.status_code}")
            return []

        except Exception as e:
            logger.error(f"Error fetching Reddit posts from r/{subreddit_name}: {str(e)}")
            return []

    def fetch_content_with_trafilatura(self, url: str) -> Optional[str]:
        """Fetch content using trafilatura for external links"""
        try:
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(downloaded)
                if text:
                    logger.info(f"Successfully extracted content with trafilatura, length: {len(text)}")
                    return text
            logger.warning("Trafilatura extraction failed or returned empty content")
            return None
        except Exception as e:
            logger.error(f"Error using trafilatura: {str(e)}")
            return None
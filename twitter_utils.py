import logging
import re
from typing import Dict, List, Tuple, Optional
import time
from bs4 import BeautifulSoup
from html import unescape

logger = logging.getLogger(__name__)

def strip_html_tags(text: str) -> str:
    """Remove HTML tags while preserving text formatting"""
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

def extract_engagement_stats(stats_element) -> Tuple[int, int, int]:
    """
    Extract engagement stats from tweet stats element
    
    Args:
        stats_element: BeautifulSoup element containing stats
        
    Returns:
        Tuple of (replies, retweets, likes)
    """
    replies = retweets = likes = 0
    
    if not stats_element:
        return replies, retweets, likes
    
    try:
        for stat in stats_element.select('.tweet-stat'):
            stat_text = stat.text.strip()
            
            # Extract the number and handle K/M suffixes
            count_match = re.search(r'(\d+(?:\.\d+)?)\s*([KMB])?', stat_text)
            if count_match:
                count = float(count_match.group(1))
                suffix = count_match.group(2)
                
                if suffix == 'K':
                    count *= 1000
                elif suffix == 'M':
                    count *= 1000000
                elif suffix == 'B':
                    count *= 1000000000
                
                if 'repl' in stat_text.lower():
                    replies = int(count)
                elif 'retw' in stat_text.lower():
                    retweets = int(count)
                elif 'like' in stat_text.lower() or 'fav' in stat_text.lower():
                    likes = int(count)
    except Exception as e:
        logger.error(f"Error extracting engagement stats: {str(e)}")
    
    return replies, retweets, likes

def format_post_for_output(post: Dict) -> Dict:
    """
    Format a post for consistent output format
    
    Args:
        post: Raw post data
        
    Returns:
        Formatted post for output
    """
    # Copy only the needed fields to avoid carrying unnecessary data
    formatted_post = {}
    
    # Handle different post types
    if post.get('type') == 'twitter_post':
        # For Twitter posts
        formatted_post = {
            'title': f"{post.get('author_name', '')} (@{post.get('author_username', '')}): {post.get('content', '')[:100]}...",
            'url': post.get('url', ''),
            'author': post.get('author_username', ''),
            'created_utc': post.get('timestamp', int(time.time())),
            'description': post.get('content', ''),
            'subreddit': 'Twitter',  # Use 'Twitter' as source identifier
            'relevance_score': post.get('ai_relevance', 0) or post.get('relevance_score', 0),
            'engagement': {
                'likes': post.get('likes', 0),
                'retweets': post.get('retweets', 0),
                'replies': post.get('replies', 0)
            },
            'hashtags': post.get('hashtags', [])
        }
    elif post.get('type') == 'rss_post':
        # For RSS feed posts
        source = post.get('source', 'Tech News')
        formatted_post = {
            'title': f"{source}: {post.get('title', '')[:100]}...",
            'url': post.get('url', ''),
            'author': post.get('author_username', source.lower().replace(' ', '')),
            'created_utc': post.get('timestamp', int(time.time())),
            'description': post.get('content', ''),
            'subreddit': 'Twitter',  # Use 'Twitter' as source identifier for consistency
            'relevance_score': post.get('ai_relevance', 0) or post.get('relevance_score', 0),
            'engagement': {
                'likes': 0,
                'retweets': 0,
                'replies': 0
            },
            'hashtags': ['#AI']
        }
    else:
        # For any other post type, just copy over common fields
        for field in ['title', 'url', 'author', 'created_utc', 'description', 'relevance_score', 'engagement', 'hashtags']:
            if field in post:
                formatted_post[field] = post[field]
        
        # Ensure required fields have defaults
        formatted_post['subreddit'] = 'Twitter'
        if 'engagement' not in formatted_post:
            formatted_post['engagement'] = {'likes': 0, 'retweets': 0, 'replies': 0}
            
    return formatted_post

def extract_links(html_content: str) -> List[str]:
    """
    Extract links from HTML content
    
    Args:
        html_content: HTML content
        
    Returns:
        List of extracted links
    """
    links = []
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        for link in soup.find_all('a'):
            href = link.get('href')
            if href and href.startswith('http'):
                links.append(href)
    except Exception as e:
        logger.error(f"Error extracting links: {str(e)}")
    
    return links
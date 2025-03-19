import logging
import re
import time
from typing import List, Dict, Set, Tuple
from datetime import datetime, timedelta

from reddit_fetcher import calculate_relevance_score

logger = logging.getLogger(__name__)

# Keywords that indicate high-quality AI content
HIGH_QUALITY_TERMS = {
    'technical': [
        'algorithm', 'model architecture', 'trained on', 'parameters', 'inference',
        'fine-tuning', 'dataset', 'benchmarks', 'paper', 'research', 'published',
        'code', 'implementation', 'open source', 'accuracy', 'performance'
    ],
    'ai_models': [
        'gpt-4', 'llama', 'claude', 'gemini', 'mistral', 'stable diffusion',
        'dall-e', 'midjourney', 'falcon', 'transformers', 'diffusion', 'multimodal'
    ],
    'specific_topics': [
        'alignment', 'safety', 'ethics', 'capabilities', 'reasoning', 'agents',
        'rlhf', 'reinforcement learning', 'supervised learning', 'unsupervised',
        'vision', 'language', 'robotics', 'autonomous', 'optimization'
    ]
}

# Keywords to filter out low-quality content
LOW_QUALITY_INDICATORS = [
    'buy now', 'click here', 'sign up', 'subscribe', 'limited time', 'promo code',
    'get started', 'join our', 'discount', 'offer', 'sale', 'register', 'free trial',
    'followers', 'crypto', 'bitcoin', 'nft', 'binance', 'exchange', 'trading',
    'make money', 'earn', 'marketing', 'seo', 'business opportunity', 'webinar',
    'course', 'masterclass', 'tutorial', 'job posting', 'hiring'
]

def filter_and_score_posts(posts: List[Dict], query: str = None) -> List[Dict]:
    """
    Apply advanced filtering and scoring to posts
    
    Args:
        posts: List of posts to filter
        query: Optional search query for more targeted filtering
        
    Returns:
        Filtered and scored posts, sorted by quality
    """
    if not posts:
        return []
    
    filtered_posts = []
    query_terms = query.lower().split() if query else []
    recent_cutoff = time.time() - (7 * 86400)  # Last 7 days
    
    for post in posts:
        try:
            # Skip posts without content
            if not post.get('content') and not post.get('title'):
                continue
            
            combined_text = f"{post.get('author_name', '')} {post.get('content', '')} {post.get('title', '')}"
            combined_text = combined_text.lower()
            
            # Calculate base relevance score using the reddit_fetcher method
            ai_relevance = calculate_relevance_score(combined_text)
            
            # Skip posts with very low AI relevance
            if ai_relevance < 2.0:
                continue
            
            # Calculate quality score
            quality_score = calculate_quality_score(post, combined_text, query_terms)
            
            # Skip posts with very low quality score or containing spam indicators
            if quality_score < 1.0 or contains_spam(combined_text):
                continue
            
            # Skip old posts unless they have very high engagement
            if post.get('timestamp', 0) < recent_cutoff and post.get('raw_engagement_score', 0) < 100:
                continue
            
            # Calculate final score - combining relevance, quality, and engagement
            final_score = (
                ai_relevance * 5.0 +  # Base AI relevance (0-5 scale)
                quality_score * 3.0 +  # Content quality (0-5 scale)
                min(post.get('raw_engagement_score', 0) / 50, 5.0)  # Capped engagement score (0-5 scale)
            )
            
            # Boost posts that match query terms
            if query_terms and any(term in combined_text for term in query_terms):
                final_score *= 1.5
            
            # Add scores to post
            post['ai_relevance'] = ai_relevance
            post['quality_score'] = quality_score
            post['final_score'] = final_score
            
            # Format post for output
            formatted_post = format_post_for_output(post)
            filtered_posts.append(formatted_post)
            
        except Exception as e:
            logger.error(f"Error processing post during filtering: {str(e)}")
            continue
    
    # Sort by final score
    sorted_posts = sorted(filtered_posts, key=lambda x: x.get('final_score', 0), reverse=True)
    
    # Ensure some content diversity by not having too many posts from the same source
    diverse_posts = ensure_diversity(sorted_posts)
    
    logger.info(f"Filtered {len(posts)} posts down to {len(diverse_posts)} high-quality posts")
    return diverse_posts

def calculate_quality_score(post: Dict, text: str, query_terms: List[str]) -> float:
    """Calculate quality score based on content and metadata"""
    score = 3.0  # Start with neutral score
    
    # Give bonus points for high-quality indicators
    for category, terms in HIGH_QUALITY_TERMS.items():
        for term in terms:
            if term in text:
                score += 0.5
                
    # Boost posts from research accounts
    if post.get('is_research_account', False):
        score += 1.5
    
    # Boost posts with links (often to papers or code)
    if post.get('has_links', False):
        score += 0.5
    
    # Boost posts with media (often visualizations or graphs)
    if post.get('media', {}).get('has_media', False):
        score += 0.5
    
    # Penalize very short posts that lack substance
    if len(text) < 100:
        score -= 1.0
    
    # Bonus for recent content
    seconds_old = time.time() - post.get('timestamp', time.time())
    if seconds_old < 86400:  # Posted in last 24 hours
        score += 0.5
    
    # Cap score between 1 and 5
    return max(1.0, min(5.0, score))

def contains_spam(text: str) -> bool:
    """Check if text contains spam indicators"""
    for indicator in LOW_QUALITY_INDICATORS:
        if indicator in text:
            return True
    
    # Check for excessive hashtags (often spam)
    hashtag_count = text.count('#')
    if hashtag_count > 5:
        return True
    
    # Check for excessive capitalization (often clickbait)
    if sum(1 for c in text if c.isupper()) / max(1, len(text)) > 0.3:
        return True
    
    # Check for suspicious URL patterns
    suspicious_url_patterns = [
        r'bit\.ly', r'tinyurl', r'cutt\.ly', r't\.co', 
        r'goo\.gl', r'amzn\.to', r'buff\.ly'
    ]
    for pattern in suspicious_url_patterns:
        if re.search(pattern, text):
            return True
    
    return False

def ensure_diversity(posts: List[Dict], max_per_source: int = 2) -> List[Dict]:
    """Ensure diversity by limiting posts from the same source"""
    if not posts:
        return []
    
    # Count posts per source
    source_counts = {}
    diverse_posts = []
    
    for post in posts:
        source = post.get('author_username', '')
        
        # If we haven't hit the limit for this source, include the post
        if source_counts.get(source, 0) < max_per_source:
            diverse_posts.append(post)
            source_counts[source] = source_counts.get(source, 0) + 1
    
    return diverse_posts

def enhance_posts(posts: List[Dict]) -> List[Dict]:
    """Add additional context and formatting to posts"""
    enhanced_posts = []
    
    for post in posts:
        # Ensure we have relevance score
        if 'relevance_score' not in post and 'ai_relevance' in post:
            post['relevance_score'] = post['ai_relevance']
        
        # Format engagement metrics
        engagement = {
            'likes': post.get('likes', 0),
            'retweets': post.get('retweets', 0),
            'replies': post.get('replies', 0)
        }
        post['engagement'] = engagement
        
        # Set post type
        if 'type' not in post:
            post['type'] = 'twitter_post'
            
        # Ensure description field is present
        if 'description' not in post and 'content' in post:
            post['description'] = post['content']
            
        # Ensure author field is present
        if 'author' not in post and 'author_username' in post:
            post['author'] = post['author_username']
            
        # Add source name for RSS posts
        if post.get('type') == 'rss_post' and 'source' in post:
            post['title'] = f"{post['source']}: {post.get('title', '')}"
            
        # Set subreddit field to 'Twitter' for consistency with Reddit fetcher
        post['subreddit'] = 'Twitter'
        
        enhanced_posts.append(post)
    
    return enhanced_posts

def format_post_for_output(post: Dict) -> Dict:
    """Format a post for output"""
    # This is a placeholder function that would typically be implemented
    # in twitter_utils.py but we're including it here for completeness
    return post
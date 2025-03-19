import logging
import requests
import feedparser
import trafilatura
import json
from datetime import datetime
from reddit_fetcher import strip_html_tags, RedditFetcher
from cache_manager import CacheManager

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_html_cleaning():
    """Test HTML cleaning functionality with basic formatting"""
    test_cases = [
        ("<a href='https://www.reddit.com'>Link</a>", "Link"),
        ("<span class='score'>Score: 100</span>", "Score: 100"),
        ("<br/> line break", "line break"),
        ("<p>Multiple <b>nested</b> <i>tags</i></p>", "Multiple nested tags"),
        ("Plain text without tags", "Plain text without tags"),
        ("<div class='md'><p>Reddit markdown</p></div>", "Reddit markdown"),
        # Test multi-paragraph content with basic formatting
        ("""<div class='md'>
            <p>First paragraph with some text.</p>
            <p>Second paragraph with more content.</p>
            <p>* Bullet point 1</p>
            <p>* Bullet point 2</p>
            <p>Some code example</p>
            <p>A quoted text example</p>
            </div>""",
         """First paragraph with some text.
Second paragraph with more content.
• Bullet point 1
• Bullet point 2
Some code example
A quoted text example""")
    ]

    logger.info("Starting HTML cleaning tests")

    for html, expected in test_cases:
        cleaned = strip_html_tags(html)
        logger.debug(f"Original HTML length: {len(html)}")
        logger.debug(f"Cleaned content length: {len(cleaned)}")
        logger.debug(f"Expected content length: {len(expected)}")
        logger.debug(f"Cleaned content: {cleaned}")
        logger.debug(f"Expected content: {expected}")
        assert cleaned.strip() == expected.strip(), f"HTML cleaning failed:\nExpected:\n{expected}\nGot:\n{cleaned}"

    logger.info("All HTML cleaning tests passed successfully")

def test_post_content_extraction():
    """Test content extraction from different Reddit post types"""
    reddit_fetcher = RedditFetcher(['test'], CacheManager(cache_ttl_hours=1))

    # Mock a text post entry with various content types
    text_post = type('Entry', (), {
        'link': 'https://www.reddit.com/r/test/comments/abc123/test_post',
        'title': 'Test Post Title'
    })

    # Mock API response for text post with rich content
    text_post_json = {
        'data': {
            'children': [{
                'data': {
                    'selftext': """This is the first paragraph of the post with some interesting content about AI.
This is the second paragraph with more technical details about the implementation.
Here are some key points:
• First important point about the technology
• Second point about the implementation
• Third point about future implications

Some code example

> Quote from a researcher: This technology shows promising results in recent tests.

Final thoughts and conclusions about the topic.""",
                    'title': 'Test Post Title',
                    'url': 'https://i.redd.it/test123.jpg',  # Add test image URL
                    'preview': {
                        'images': [{
                            'source': {
                                'url': 'https://preview.redd.it/test123.jpg'
                            }
                        }]
                    }
                }
            }]
        }
    }

    # Mock requests.get for the API call
    def mock_get(*args, **kwargs):
        class MockResponse:
            def __init__(self, json_data, status_code):
                self.json_data = json_data
                self.status_code = status_code
            def json(self):
                return self.json_data
            def text(self):
                return json.dumps(self.json_data)

        if 'by_id' in args[0]:
            return MockResponse(text_post_json, 200)
        return MockResponse(None, 404)

    # Save original get function and replace with mock
    original_get = requests.get
    requests.get = mock_get

    try:
        # Test content extraction
        content, score, media_url = reddit_fetcher.extract_post_content(text_post)

        logger.info("Extracted content:")
        logger.info(content)
        logger.info(f"Media URL: {media_url}")

        # Verify content structure and media URL
        assert isinstance(content, str), "Content should be a string"
        assert isinstance(score, float), "Score should be a float"
        assert isinstance(media_url, (str, type(None))), "Media URL should be string or None"

        if media_url:
            assert media_url.startswith('http'), "Media URL should start with http"
            assert any(media_url.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.mp4']), \
                "Media URL should end with valid extension"

        # Verify specific content elements
        paragraphs = content.split('\n\n')
        assert len(paragraphs) > 1, "Content should have multiple paragraphs"
        assert any('•' in p for p in paragraphs), "Bullet points should be preserved"
        assert any('>' in p for p in paragraphs), "Quotes should be preserved"
        assert paragraphs[0].startswith("This is the first paragraph"), "First paragraph should match"

        logger.info("Content extraction test passed successfully")

    finally:
        # Restore original get function
        requests.get = original_get

def test_media_extraction():
    """Test media URL extraction from different Reddit post types"""
    reddit_fetcher = RedditFetcher(['test'], CacheManager(cache_ttl_hours=1))

    # Mock API responses for different media types
    gallery_post = {
        'data': {
            'children': [{
                'data': {
                    'title': 'Gallery Test',
                    'media_metadata': {
                        'abc123': {
                            's': {
                                'u': 'https://preview.redd.it/image1.jpg?width=1080&amp;format=jpeg'
                            }
                        }
                    },
                    'gallery_data': {'items': [{'media_id': 'abc123'}]}
                }
            }]
        }
    }

    video_post = {
        'data': {
            'children': [{
                'data': {
                    'title': 'Video Test',
                    'is_video': True,
                    'media': {
                        'reddit_video': {
                            'fallback_url': 'https://v.redd.it/video123.mp4'
                        }
                    }
                }
            }]
        }
    }

    preview_post = {
        'data': {
            'children': [{
                'data': {
                    'title': 'Preview Test',
                    'preview': {
                        'images': [{
                            'source': {
                                'url': 'https://preview.redd.it/preview123.jpg&amp;format=jpeg'
                            }
                        }]
                    }
                }
            }]
        }
    }

    direct_image_post = {
        'data': {
            'children': [{
                'data': {
                    'title': 'Direct Image Test',
                    'url': 'https://i.redd.it/direct123.jpg'
                }
            }]
        }
    }

    # Test gallery post
    def mock_gallery_get(*args, **kwargs):
        class MockResponse:
            def __init__(self, json_data, status_code):
                self.json_data = json_data
                self.status_code = status_code
            def json(self):
                return self.json_data
            def text(self):
                return json.dumps(self.json_data)
        return MockResponse(gallery_post, 200)

    # Save original get function
    original_get = requests.get
    requests.get = mock_gallery_get

    try:
        mock_entry = type('Entry', (), {'link': 'https://reddit.com/r/test/comments/abc/test'})
        content, score, media_url = reddit_fetcher.extract_post_content(mock_entry)
        logger.info(f"Gallery post media URL: {media_url}")
        assert media_url and media_url.startswith('https://') and '.jpg' in media_url
        assert '&amp;' not in media_url  # Check URL cleaning

        # Test video post
        requests.get = lambda *args, **kwargs: type('MockResponse', (), {
            'status_code': 200,
            'json': lambda: video_post,
            'text': lambda: json.dumps(video_post)
        })()
        content, score, media_url = reddit_fetcher.extract_post_content(mock_entry)
        logger.info(f"Video post media URL: {media_url}")
        assert media_url and media_url.endswith('.mp4')

        # Test preview image post
        requests.get = lambda *args, **kwargs: type('MockResponse', (), {
            'status_code': 200,
            'json': lambda: preview_post,
            'text': lambda: json.dumps(preview_post)
        })()
        content, score, media_url = reddit_fetcher.extract_post_content(mock_entry)
        logger.info(f"Preview post media URL: {media_url}")
        assert media_url and media_url.startswith('https://') and '.jpg' in media_url
        assert '&amp;' not in media_url  # Check URL cleaning

        # Test direct image post
        requests.get = lambda *args, **kwargs: type('MockResponse', (), {
            'status_code': 200,
            'json': lambda: direct_image_post,
            'text': lambda: json.dumps(direct_image_post)
        })()
        content, score, media_url = reddit_fetcher.extract_post_content(mock_entry)
        logger.info(f"Direct image post media URL: {media_url}")
        assert media_url and media_url.endswith('.jpg')

        logger.info("All media extraction tests passed successfully")

    except Exception as e:
        logger.error(f"Error in media extraction test: {str(e)}", exc_info=True)
        raise e
    finally:
        # Restore original get function
        requests.get = original_get

def test_reddit_fetch():
    """Test Reddit RSS feed fetching"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        subreddit = "artificial"  # Test with AI subreddit

        # Test RSS feed
        feed_url = f"https://www.reddit.com/r/{subreddit}/.rss"
        logger.info(f"Testing RSS feed from: {feed_url}")

        response = requests.get(feed_url, headers=headers, timeout=10)
        logger.info(f"RSS Response Status: {response.status_code}")

        if response.status_code == 200:
            feed = feedparser.parse(response.text)
            logger.info(f"Feed entries found: {len(feed.entries)}")

            if feed.entries:
                first_entry = feed.entries[0]
                logger.info("Sample entry details:")
                logger.info(f"Title: {first_entry.title}")
                logger.info(f"Link: {first_entry.link}")

                # Test content extraction with real post
                reddit_fetcher = RedditFetcher([subreddit], CacheManager(cache_ttl_hours=1))
                content = reddit_fetcher.extract_post_content(first_entry)
                logger.info("Extracted content preview:")
                logger.info(content[:500])

                # Verify content format
                paragraphs = content.split('\n\n')
                logger.info(f"Number of paragraphs: {len(paragraphs)}")
                for i, p in enumerate(paragraphs):
                    logger.info(f"Paragraph {i+1} length: {len(p)}")

    except Exception as e:
        logger.error(f"Error in reddit fetch test: {str(e)}", exc_info=True)

if __name__ == "__main__":
    test_html_cleaning()
    test_post_content_extraction()
    test_reddit_fetch()
    test_media_extraction()
import logging
from news_fetcher import NewsFetcher
import json

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_news_fetching():
    try:
        fetcher = NewsFetcher()
        logger.info("Initialized NewsFetcher, attempting to fetch news...")
        
        response = fetcher.fetch_ai_news()
        if response:
            logger.info("API Response received:")
            logger.debug(f"Full response: {json.dumps(response, indent=2)}")
            
            content = fetcher.extract_news_content(response)
            if content:
                logger.info("Successfully extracted news content:")
                print("\n=== Extracted News Content ===")
                print(content)
                print("============================")
            else:
                logger.error("Failed to extract content from valid response")
        else:
            logger.error("No response received from API")
    
    except Exception as e:
        logger.error(f"Error during test: {str(e)}", exc_info=True)

if __name__ == "__main__":
    test_news_fetching()

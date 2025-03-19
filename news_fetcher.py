import logging
import requests
from typing import Dict, List, Optional
import json

from config import (
    PERPLEXITY_API_KEY, PERPLEXITY_API_URL, MODEL_NAME, 
    get_category_prompt, NEWS_CATEGORIES
)

logger = logging.getLogger(__name__)

class NewsFetcher:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        logger.debug("NewsFetcher initialized with API configuration")

    def fetch_ai_news(self, category: str = "general") -> Optional[Dict]:
        """
        Fetches AI news using the Perplexity SONAR API

        Args:
            category: The news category to fetch (default: "general")
        """
        if category not in NEWS_CATEGORIES:
            logger.warning(f"Invalid category '{category}', defaulting to 'general'")
            category = "general"

        try:
            payload = {
                "model": MODEL_NAME,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a helpful AI news curator. Be precise and concise."
                    },
                    {
                        "role": "user",
                        "content": get_category_prompt(category)
                    }
                ],
                "temperature": 0.2,
                "top_p": 0.9,
                "search_domain_filter": ["perplexity.ai"],
                "return_images": False,
                "return_related_questions": False,
                "search_recency_filter": "day",
                "frequency_penalty": 1,
                "stream": False
            }

            logger.debug(f"Sending request to Perplexity API for category '{category}'")
            logger.debug(f"Request payload: {json.dumps(payload, indent=2)}")
            logger.info(f"Making API request to Perplexity for {category} news")

            response = requests.post(
                PERPLEXITY_API_URL,
                headers=self.headers,
                json=payload,
                timeout=30  # Add timeout to prevent indefinite waiting
            )

            logger.debug(f"API Response Status Code: {response.status_code}")
            logger.debug(f"API Response Headers: {response.headers}")

            if response.status_code != 200:
                logger.error(f"API request failed with status code {response.status_code}")
                logger.error(f"Response content: {response.text}")
                return None

            response_data = response.json()
            logger.info(f"Successfully received API response for {category} news")
            logger.debug(f"Response data: {json.dumps(response_data, indent=2)}")
            return response_data

        except requests.exceptions.Timeout:
            logger.error("API request timed out after 30 seconds")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}", exc_info=True)
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return None

    def extract_news_content(self, response: Dict) -> Optional[str]:
        """
        Extracts the news content from the API response
        """
        try:
            if not response or 'choices' not in response:
                logger.error(f"Invalid response format: {json.dumps(response, indent=2)}")
                return None

            content = response['choices'][0]['message']['content']
            citations = response.get('citations', [])

            # Append citations if available
            if citations:
                content += "\n\nSources:\n" + "\n".join(citations[:3])  # Limited to first 3 sources

            return content

        except KeyError as e:
            logger.error(f"Key error while extracting content: {str(e)}", exc_info=True)
            logger.error(f"Response structure: {json.dumps(response, indent=2)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error while extracting content: {str(e)}", exc_info=True)
            return None
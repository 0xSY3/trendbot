import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Bot configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY')

# Reddit configuration
DEFAULT_SUBREDDITS = [
    'MachineLearning',      # Premier ML research community
    'artificial',          # High-quality AI discussions
    'MLOps',               # ML deployment and operations
    'DeepLearning',        # Deep learning specific content
    'LocalLLaMA',          # Local LLM discussions and implementations
    'OpenAI',              # OpenAI developments and applications
    'StableDiffusion',     # AI image generation updates
    'AIEngineering',       # Practical AI development
    'computervision'       # Computer vision research and applications
]

if not all([DISCORD_TOKEN, PERPLEXITY_API_KEY]):
    logger.error("Missing required environment variables. Please check your .env file.")
    raise ValueError("Missing required environment variables")

logger.info("Environment variables loaded successfully")

# Perplexity API configuration
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
MODEL_NAME = "llama-3.1-sonar-small-128k-online"

# News Categories
NEWS_CATEGORIES = {
    "general": "latest significant AI news and developments",
    "ml": "machine learning and deep learning advancements",
    "robotics": "robotics and automation developments",
    "ethics": "AI ethics, regulation, and policy updates",
    "research": "academic AI research breakthroughs",
    "industry": "AI industry and business news"
}

# News fetch configuration
NEWS_INTERVAL_HOURS = int(os.getenv('NEWS_INTERVAL_HOURS', 4))

def get_category_prompt(category="general"):
    """Get the appropriate prompt for a given category"""
    category_desc = NEWS_CATEGORIES.get(category, NEWS_CATEGORIES["general"])
    return f"""Please provide the latest {category_desc} from the past day. 
Focus on major announcements, breakthroughs, or significant updates. Format the response as 3-4 
distinct news items with brief summaries."""

# Default prompt for scheduled updates
AI_NEWS_PROMPT = get_category_prompt("general")

# Message configuration
MAX_MESSAGE_LENGTH = 2000  # Discord's message length limit
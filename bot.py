import discord
from discord.ext import commands
import logging
import traceback
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import pytz
import asyncio
from concurrent.futures import ThreadPoolExecutor
from config import DISCORD_TOKEN, NEWS_INTERVAL_HOURS, DEFAULT_SUBREDDITS
from news_fetcher import NewsFetcher
from message_formatter import MessageFormatter
from reddit_fetcher import RedditFetcher
from cache_manager import CacheManager
from direct_twitter_fetcher import DirectTwitterFetcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

# Initialize bot with commands
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize components
news_fetcher = NewsFetcher()
reddit_fetcher = RedditFetcher(DEFAULT_SUBREDDITS, CacheManager(cache_ttl_hours=8))
direct_twitter_fetcher = DirectTwitterFetcher()  # Direct Twitter fetcher for real tweets
message_formatter = MessageFormatter()
scheduler = AsyncIOScheduler()
thread_pool = ThreadPoolExecutor(max_workers=2)

# Add lock for news updates
news_update_lock = asyncio.Lock()
command_locks = {}  # Dictionary to store per-command locks
command_flags = {}  # Dictionary to track command execution

# Define news categories
NEWS_CATEGORIES = {
    "general": "General AI news",
    "ml": "Machine Learning news",
    "robotics": "Robotics and automation news",
    "ethics": "AI ethics and policy news",
    "research": "Academic research breakthroughs",
    "industry": "AI industry and business news"
}


async def fetch_news_async(category: str = "general"):
    """
    Asynchronously fetch news using a thread pool
    """
    logger.info(f"Starting asynchronous news fetch for category: {category}")
    loop = asyncio.get_event_loop()

    logger.debug("Calling fetch_ai_news in thread pool")
    response = await loop.run_in_executor(
        thread_pool, 
        lambda: news_fetcher.fetch_ai_news(category)
    )
    if response:
        logger.debug("Got API response, extracting content")
        content = await loop.run_in_executor(
            thread_pool, 
            news_fetcher.extract_news_content, 
            response
        )
        if content:
            logger.info(f"Successfully fetched {category} news content (length: {len(content)})")
            return content
        logger.error("Failed to extract content from response")
        return None
    logger.error("No response received from API")
    return None

async def post_news_update():
    """
    Fetches and posts AI news to all registered channels
    """
    if news_update_lock.locked():
        logger.info("News update already in progress, skipping")
        return

    async with news_update_lock:
        try:
            content = await fetch_news_async()
            if not content:
                logger.error("Failed to fetch or extract news content")
                return

            embeds = message_formatter.create_news_embed(content)

            # Post to all registered channels
            async for guild in bot.fetch_guilds():
                try:
                    # Find first text channel in each guild
                    for channel in guild.text_channels:
                        if channel.permissions_for(guild.me).send_messages:
                            await channel.send("📰 **Scheduled AI News Update:**")
                            for embed in embeds:
                                await channel.send(embed=embed)
                            break
                except Exception as e:
                    logger.error(f"Error posting to guild {guild.id}: {str(e)}")

        except Exception as e:
            logger.error(f"Error in news update task: {str(e)}")

@bot.event
async def on_ready():
    """
    Called when the bot is ready and connected to Discord
    """
    logger.info(f"Bot logged in as {bot.user.name}")
    logger.info(f"News update interval set to {NEWS_INTERVAL_HOURS} hours")
    logger.info("Environment configuration loaded successfully")
    
    # Log command names to verify they're registered correctly
    all_commands = [cmd.name for cmd in bot.commands]
    logger.info(f"Registered commands: {', '.join(all_commands)}")

    # Start the news scheduler without immediate execution
    scheduler.add_job(
        post_news_update,
        trigger=IntervalTrigger(hours=NEWS_INTERVAL_HOURS),
        id='post_news_update',  # Add ID for easier reference
        coalesce=True,  # Prevent multiple executions
        max_instances=1,  # Only allow one instance
        next_run_time=None  # Don't run immediately on startup
    )
    scheduler.start()

    next_run = scheduler.get_job('post_news_update').next_run_time
    next_run_str = next_run.strftime("%Y-%m-%d %H:%M:%S UTC") if next_run else "4 hours from now"
    logger.info(f"Scheduler started, next update at {next_run_str}")

@bot.command(name='news', description="Fetch the latest AI news")
@commands.cooldown(1, 5, commands.BucketType.user)  # Add cooldown to prevent spam
async def news(ctx, category: str = "general"):
    """
    Manual command to fetch and post latest AI news

    Args:
        category: The news category to fetch (default: "general")
    """
    # Convert category to lowercase and validate
    category = category.lower()
    if category not in NEWS_CATEGORIES:
        categories_list = "\n".join([f"• {cat}: {desc}" for cat, desc in NEWS_CATEGORIES.items()])
        await ctx.send(f"❌ Invalid category. Available categories are:\n{categories_list}")
        return

    command_id = f"news_{ctx.author.id}_{ctx.message.id}"
    if command_id in command_flags:
        logger.debug(f"Duplicate command execution prevented for {command_id}")
        return

    command_flags[command_id] = True
    try:
        if news_update_lock.locked():
            await ctx.send("⏳ A news update is already in progress, please wait a moment...")
            return

        async with news_update_lock:
            status_message = await ctx.send(f"🔍 Fetching latest {category} AI news updates...")
            logger.info(f"Manual news fetch requested by user {ctx.author.id} for category {category}")

            content = await fetch_news_async(category)
            if not content:
                await status_message.edit(content="❌ Unable to fetch news at this time. Please try again later.")
                logger.error("Failed to fetch news - no response received")
                return

            embeds = message_formatter.create_news_embed(content, category)
            logger.info(f"Created {len(embeds)} embeds from news content")
            await status_message.delete()

            # Add a header message before the news
            header = await ctx.send(f"📰 **Here's your {category.upper()} AI news update:**")

            try:
                for embed in embeds:
                    await ctx.send(embed=embed)
                logger.info(f"Successfully posted {category} news update for user {ctx.author.id}")
            except Exception as e:
                await header.delete()
                raise e

    except Exception as e:
        logger.error(f"Error in news command: {str(e)}", exc_info=True)
        await ctx.send("❌ An error occurred while fetching news. Please try again later.")
    finally:
        if command_id in command_flags:
            del command_flags[command_id]

@bot.command(name='reddit')
@commands.cooldown(1, 5, commands.BucketType.user)
async def reddit(ctx, subreddit: str = None):
    """
    Fetch AI-related posts from Reddit
    """
    if subreddit and subreddit.lower() not in [s.lower() for s in DEFAULT_SUBREDDITS]:
        subreddits_list = "\n".join([f"• {sub}" for sub in DEFAULT_SUBREDDITS])
        await ctx.send(f"Available AI subreddits:\n{subreddits_list}")
        return

    status_message = await ctx.send(f"🔍 Fetching AI/ML posts from r/{subreddit or DEFAULT_SUBREDDITS[0]}...")
    logger.info(f"Reddit fetch requested for subreddit {subreddit or DEFAULT_SUBREDDITS[0]}")

    try:
        posts = await reddit_fetcher.fetch_trending_posts(subreddit)

        if not posts:
            logger.error("No relevant AI/ML posts found")
            await status_message.edit(content="No relevant AI/ML posts found at this time. Try again later.")
            return

        await status_message.delete()
        await ctx.send(f"📱 Latest AI/ML Posts from r/{subreddit or DEFAULT_SUBREDDITS[0]}")

        for post in posts:
            try:
                logger.info(f"Processing post: {post['title'][:50]}...")

                # Create embed with post details
                embed = discord.Embed(
                    title=post['title'][:256],
                    url=post['url'],
                    color=discord.Color.blue(),
                    timestamp=datetime.fromtimestamp(post['created_utc'])
                )

                # Add AI relevance indicator
                relevance_score = post.get('relevance_score', 0)
                relevance_emoji = "🔥" if relevance_score >= 4 else "⭐" if relevance_score >= 2 else "ℹ️"
                embed.title = f"{relevance_emoji} {embed.title}"

                # Format and add post content
                content = post.get('description', '')
                if content:
                    logger.info(f"Processing content of total length: {len(content)}")

                    # First try to fit everything in description
                    if len(content) <= 4096:
                        embed.description = content
                        logger.info("Full content fits in description")
                    else:
                        # Split by paragraphs to preserve structure
                        paragraphs = content.split('\n\n')
                        desc_content = []
                        desc_length = 0
                        remaining = []

                        # Use description for initial content (up to 4096 chars)
                        for para in paragraphs:
                            if desc_length + len(para) + 4 <= 4096:
                                desc_content.append(para)
                                desc_length += len(para) + 4
                            else:
                                remaining.append(para)

                        # Set description
                        if desc_content:
                            embed.description = '\n\n'.join(desc_content)
                            logger.info(f"Added description with {desc_length} chars")

                            # Handle remaining content in fields (1024 chars each)
                            if remaining:
                                field_count = 0
                                current_field = []
                                current_length = 0

                                for para in remaining:
                                    # Check if this paragraph would fit in current field
                                    if current_length + len(para) + 4 <= 1024:
                                        current_field.append(para)
                                        current_length += len(para) + 4
                                    else:
                                        # Add current field if not empty
                                        if current_field:
                                            field_count += 1
                                            embed.add_field(
                                                name=f"📄 Content (Part {field_count})",
                                                value='\n\n'.join(current_field),
                                                inline=False
                                            )
                                            logger.info(f"Added field {field_count} with {current_length} chars")
                                            current_field = [para]
                                            current_length = len(para) + 4

                                # Add any remaining content as final field
                                if current_field:
                                    field_count += 1
                                    embed.add_field(
                                        name=f"📄 Content (Part {field_count})",
                                        value='\n\n'.join(current_field),
                                        inline=False
                                    )
                                    logger.info(f"Added final field {field_count} with {current_length} chars")
                else:
                    embed.description = "Click the title to view the full post"

                # Add metadata and relevance info
                metadata = [
                    f"👤 u/{post['author']}",
                    f"📍 r/{post['subreddit']}",
                    f"📊 AI Relevance: {relevance_score:.1f}"
                ]
                embed.add_field(
                    name="ℹ️ Details",
                    value=" • ".join(metadata),
                    inline=False
                )

                # Add footer with link to full post
                embed.set_footer(text="Click title to read the full post on Reddit")

                try:
                    await ctx.send(embed=embed)
                    logger.info(f"Successfully sent embed for post: {post['title'][:50]}")
                except discord.HTTPException as e:
                    logger.error(f"Discord error: {str(e)}")
                    await ctx.send("Error displaying post. Skipping...")
                    continue

            except Exception as e:
                logger.error(f"Error processing post: {str(e)}")
                continue

    except Exception as e:
        logger.error(f"Error in reddit command: {str(e)}")
        await ctx.send("An error occurred while fetching Reddit posts.")

@bot.command(name='twitter')
@commands.cooldown(1, 10, commands.BucketType.user)
async def twitter(ctx, *, query: str = None):
    """
    Fetch AI-related trending posts from Twitter (X)
    """
    logger.info(f"Twitter command invoked by {ctx.author} with query: {query}")
    status_message = await ctx.send(f"🔍 Fetching trending AI posts from Twitter{' about '+query if query else ''}...")
    
    try:
        logger.info("Using direct_twitter_fetcher.fetch_trending_posts")
        posts = await direct_twitter_fetcher.fetch_trending_posts(query)
        
        logger.info(f"Fetcher returned {len(posts) if posts else 0} posts")
        
        if not posts:
            logger.error("No relevant Twitter posts found")
            await status_message.edit(content="❌ No relevant AI/ML Twitter posts found at this time. Try again later.")
            return
            
        await status_message.delete()
        header_message = await ctx.send(f"🐦 Latest AI/ML Trending Posts from Twitter{' about '+query if query else ''}")
        
        post_count = 0
        for post in posts:
            try:
                logger.info(f"Processing post {post_count+1}: {post.get('title', '')[:30]}...")
                
                # Create embed with post details
                embed = discord.Embed(
                    title=post['title'][:256],  # Limit title length
                    url=post['url'],
                    color=discord.Color.blue(),  # Twitter blue
                    timestamp=datetime.fromtimestamp(post['created_utc'])
                )
                
                # Add AI relevance indicator
                relevance_score = post.get('relevance_score', 0)
                relevance_emoji = "🔥" if relevance_score >= 4 else "⭐" if relevance_score >= 2 else "ℹ️"
                embed.title = f"{relevance_emoji} {embed.title}"
                
                # Format and add post content
                content = post.get('description', '')
                if content:
                    # Add content to description
                    if len(content) <= 4096:
                        embed.description = content
                    else:
                        # If too long, truncate and add note
                        embed.description = content[:4000] + "... (content truncated)"
                else:
                    embed.description = "Click the title to view the full post"
                
                # Add engagement metrics
                engagement = post.get('engagement', {})
                metadata = [
                    f"👤 @{post['author']}",
                    f"❤️ {engagement.get('likes', 0):,} likes",
                    f"🔄 {engagement.get('retweets', 0):,} retweets", 
                    f"💬 {engagement.get('replies', 0):,} replies",
                    f"📊 AI Relevance: {relevance_score:.1f}"
                ]
                
                # Add hashtags if available
                hashtags = post.get('hashtags', [])
                if hashtags:
                    metadata.append(f"🏷️ {' '.join(hashtags[:5])}")
                
                embed.add_field(
                    name="ℹ️ Details",
                    value=" • ".join(metadata),
                    inline=False
                )
                
                # Add footer
                embed.set_footer(text="Click title to view the full post on Twitter")
                
                await ctx.send(embed=embed)
                logger.info(f"Successfully sent Twitter post embed from @{post['author']}")
                post_count += 1
                
            except Exception as e:
                logger.error(f"Error processing Twitter post: {str(e)}")
                continue
                
        if post_count == 0:
            await header_message.edit(content="❌ Failed to display any Twitter posts. Please try again later.")
            
    except Exception as e:
        logger.error(f"Error in twitter command: {str(e)}")
        await ctx.send("❌ An error occurred while fetching Twitter posts. Please try again later.")

@bot.command(name='bothelp')
async def bothelp_command(ctx):
    """
    Displays help information about the bot
    """
    embed = discord.Embed(
        title="🤖 AI News Bot Help",
        color=discord.Color.blue(),
        description="I'm your AI News Assistant! I automatically post AI-related news updates and can provide category-specific news on demand."
    )

    # Add available categories
    categories_desc = "\n".join([f"• **{cat}**: {desc}" for cat, desc in NEWS_CATEGORIES.items()])
    embed.add_field(
        name="📚 Available Categories",
        value=categories_desc,
        inline=False
    )

    embed.add_field(
        name="📝 Available Commands",
        value="""
        `!news [category]` - Fetch the latest AI news (optionally specify a category)
        `!reddit [subreddit]` - Fetch posts from AI subreddits
        `!twitter [query]` - Fetch trending AI posts from Twitter (X)
        `!bothelp` - Show this help message with all commands
        `!status` - Check when the next automatic update is scheduled
        """,
        inline=False
    )

    # Add available subreddits
    subreddits_desc = "\n".join([f"• r/{sub}" for sub in DEFAULT_SUBREDDITS])
    embed.add_field(
        name="🌐 Available Subreddits",
        value=subreddits_desc,
        inline=False
    )

    embed.add_field(
        name="ℹ️ Usage Examples",
        value="""
        `!news` - Get general AI news
        `!news ml` - Get Machine Learning news
        `!reddit` - Get posts from r/artificialintelligence
        `!reddit MachineLearning` - Get posts from r/MachineLearning
        `!twitter` - Get trending AI posts from Twitter
        `!twitter llama` - Get Twitter posts about LLaMA models
        """,
        inline=False
    )

    await ctx.send(embed=embed)

@bot.command(name='status')
async def status(ctx):
    """
    Displays bot status information
    """
    embed = discord.Embed(
        title="🤖 Bot Status",
        color=discord.Color.green(),
        description="AI News Bot Status Overview",
        timestamp=datetime.now(pytz.UTC)
    )

    next_run = scheduler.get_job('post_news_update').next_run_time

    embed.add_field(
        name="⏰ Next Update",
        value=next_run.strftime("%Y-%m-%d %H:%M:%S UTC") if next_run else "Not scheduled",
        inline=True
    )

    embed.add_field(
        name="🔄 Update Interval",
        value=f"Every {NEWS_INTERVAL_HOURS} hours",
        inline=True
    )

    # Add connection status
    embed.add_field(
        name="📡 Connection Status",
        value="✅ Connected to Discord\n✅ API Services Active",
        inline=False
    )
    
    # Add command availability
    all_commands = [cmd.name for cmd in bot.commands]
    embed.add_field(
        name="🧰 Available Commands",
        value=", ".join([f"`!{cmd}`" for cmd in all_commands]),
        inline=False
    )

    embed.set_footer(text="Use !bothelp to see available commands")

    await ctx.send(embed=embed)

@bot.event
async def on_command_error(ctx, error):
    """
    Global error handler for bot commands
    """
    if isinstance(error, commands.CommandNotFound):
        logger.warning(f"Command not found: {ctx.message.content}")
        available_commands = ", ".join([f"`!{cmd.name}`" for cmd in bot.commands])
        await ctx.send(f"Command not found. Available commands: {available_commands}")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"This command is on cooldown. Please try again in {error.retry_after:.2f} seconds.")
    else:
        logger.error(f"Command error: {str(error)}")
        logger.error(traceback.format_exc())  # Add full traceback
        await ctx.send(f"An error occurred: {str(error)[:1000]}")

def main():
    """
    Main entry point for the bot
    """
    try:
        logger.info("Starting bot...")
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")
        logger.error(traceback.format_exc())  # Add full traceback

if __name__ == "__main__":
    main()
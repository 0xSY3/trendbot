import logging
from typing import List
from discord import Embed, Color
from datetime import datetime

from config import MAX_MESSAGE_LENGTH, NEWS_CATEGORIES

logger = logging.getLogger(__name__)

class MessageFormatter:
    @staticmethod
    def create_news_embed(content: str, category: str = "general") -> List[Embed]:
        """
        Creates Discord embeds from news content with improved formatting

        Args:
            content: The news content to format
            category: The category of news being displayed (default: "general")
        """
        embeds = []

        try:
            # Split content into news and sources
            parts = content.split("\nSources:")
            news_content = parts[0]
            sources = parts[1] if len(parts) > 1 else None

            # Get category color
            color = MessageFormatter._get_category_color(category)

            # Create main news embed
            main_embed = Embed(
                title=f"🌟 Latest {category.upper()} AI News Update",
                color=color,
                timestamp=datetime.utcnow()
            )
            main_embed.set_author(
                name="AI News Bot",
                icon_url="https://i.imgur.com/XxxXxxx.png"
            )

            # Format news content with emojis and better structure
            formatted_content = news_content
            lines = news_content.split('\n')
            number_emojis = ['🔥', '⚡', '🌐', '💡']

            for i, line in enumerate(lines):
                for num in range(1, 5):
                    if line.strip().startswith(f"{num}."):
                        emoji = number_emojis[num-1]
                        formatted_content = formatted_content.replace(
                            f"{num}.", f"{emoji}"
                        )

            if len(formatted_content) <= 4096:
                main_embed.description = formatted_content
                embeds.append(main_embed)
            else:
                # Split long content into multiple embeds
                sections = formatted_content.split('\n\n')
                current_section = []
                current_length = 0

                for section in sections:
                    if current_length + len(section) + 2 <= 4096:
                        current_section.append(section)
                        current_length += len(section) + 2
                    else:
                        embed = Embed(
                            color=color,
                            timestamp=datetime.utcnow()
                        )
                        embed.description = '\n\n'.join(current_section)
                        embeds.append(embed)
                        current_section = [section]
                        current_length = len(section)

                if current_section:
                    embed = Embed(
                        color=color,
                        timestamp=datetime.utcnow()
                    )
                    embed.description = '\n\n'.join(current_section)
                    embeds.append(embed)

            # Add sources in a separate embed
            if sources:
                sources_embed = Embed(
                    title="📚 Sources",
                    color=color,
                    description=sources.strip(),
                    timestamp=datetime.utcnow()
                )
                embeds.append(sources_embed)

            # Add footer to last embed
            if embeds:
                category_desc = NEWS_CATEGORIES.get(category, "AI news")
                embeds[-1].set_footer(
                    text=f"Stay updated with the latest in {category_desc} • Powered by Perplexity SONAR",
                    icon_url="https://i.imgur.com/XxxXxxx.png"
                )

            return embeds

        except Exception as e:
            logger.error(f"Error formatting message: {str(e)}", exc_info=True)
            error_embed = Embed(
                title="❌ Error Formatting News",
                color=Color.red(),
                description="There was an error formatting the news content."
            )
            return [error_embed]

    @staticmethod
    def _get_category_color(category: str) -> Color:
        """Returns a color based on the news category"""
        colors = {
            "general": Color.blue(),
            "ml": Color.purple(),
            "robotics": Color.orange(),
            "ethics": Color.green(),
            "research": Color.gold(),
            "industry": Color.teal()
        }
        return colors.get(category, Color.blue())
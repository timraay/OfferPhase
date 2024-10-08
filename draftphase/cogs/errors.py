from discord import Interaction
from discord.ext import commands

from draftphase.bot import Bot
from draftphase.discord_utils import handle_error

class ErrorsCog(commands.Cog):
    """A class with most events in it"""

    def __init__(self, bot: Bot):
        self.bot = bot

        @bot.tree.error
        async def on_interaction_error(interaction: Interaction, error: Exception):
            await handle_error(interaction, error)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        await handle_error(ctx, error)

async def setup(bot: Bot):
    await bot.add_cog(ErrorsCog(bot))
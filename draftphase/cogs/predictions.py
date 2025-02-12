import discord
from discord import Member, app_commands, Interaction
from discord.ext import commands

from draftphase.bot import Bot
from draftphase.views.prediction_leaderboard import PredictionLeaderboardView

class PredictionsCog(commands.GroupCog, group_name="predictions"):
    def __init__(self, bot: Bot) -> None:
        super().__init__()
        self.bot = bot
    
    @app_commands.command()
    @app_commands.rename(
        member="user"
    )
    async def leaderboard(self, interaction: Interaction, member: discord.Member | None = None):
        assert isinstance(interaction.user, Member)
        view = PredictionLeaderboardView(member or interaction.user)
        embed = view.get_embed_update_self()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
async def setup(bot: Bot):
    await bot.add_cog(PredictionsCog(bot))

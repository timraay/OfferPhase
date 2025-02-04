import discord
from discord import Member, app_commands, Interaction
from discord.ext import commands
from typing import Callable, NamedTuple

from draftphase.bot import Bot
from draftphase.db import get_cursor
from draftphase.views.prediction_leaderboard import PredictionLeaderboardView

class UserPrediction(NamedTuple):
    user_id: int
    num_guessed: int
    num_correct_winner: int
    num_correct_score: int

def get_user_predictions() -> list[UserPrediction]:
    with get_cursor() as cur:
        cur.execute(
            "SELECT"
            " user_id,"
            " COUNT(id) AS num_guessed,"
            " COUNT((predictions.team1_score > 2) = (games.team1_score > 2)) AS num_correct_winner,"
            " COUNT((predictions.team1_score = games.team1_score)) AS num_correct_score"
            " FROM predictions"
            " INNER JOIN games ON predictions.game_id = games.channel_id"
            " GROUP BY user_id"
        )
        return cur.fetchall()

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

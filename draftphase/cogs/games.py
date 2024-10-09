from discord import Permissions, TextChannel, app_commands, Interaction, Member
from discord.ext import commands

from draftphase.bot import Bot
from draftphase.db import get_cursor
from draftphase.discord_utils import CustomException
from draftphase.emojis import Emojis
from draftphase.game import Game
from draftphase.views.start_draft import StartDraftView

class GamesCog(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    @app_commands.command(name="start-draft-phase")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        opponent="The person to play against",
        max_num_offers="Amount of offers you and your opponent get, combined. Defaults to 10 (5 each).",
    )
    async def start_draft_phase(self, interaction: Interaction, opponent: Member, max_num_offers: int = 10):
        if not isinstance(interaction.channel, TextChannel):
            raise CustomException(
                "Cannot use this here!",
                "Command must not be invoked from within a thread or forum post."
            )

        bot_perms = interaction.channel.permissions_for(opponent.guild.me)
        if not bot_perms.is_superset(Permissions(309237661696)):
            raise CustomException(
                "Bot is missing permissions!",
                (
                    "Make sure the following permissions are added, then try again:"
                    "\n\n"
                    "- View Channel\n"
                    "- Send Messages\n"
                    "- Send Messages in Threads\n"
                    "- Create Public Threads\n"
                    "- Embed Links"
                )
            )

        if not interaction.channel.permissions_for(opponent).read_messages:
            raise CustomException("Opponent must have access to this channel")

        if not (2 <= max_num_offers <= 20):
            raise CustomException(
                "Invalid maximum number of offers!",
                "Number must be between 2 and 20."
            )        

        await interaction.response.send_message((
            f"Starting a new Draft Phase between"
            f" {interaction.user.mention} (Player 1 {Emojis.team1_silhouette.value})"
            f" and {opponent.mention} (Player 2 {Emojis.team2_silhouette.value})"
        ))
        message = await interaction.original_response()

        with get_cursor() as cur:
            cur.execute("SELECT COALESCE((SELECT seq + 1 FROM sqlite_sequence WHERE name = 'games'), 1)")
            game_id = cur.fetchone()[0]
        thread = await message.create_thread(name=f"game-{game_id}")

        game = Game.create(interaction.user.id, opponent.id, thread.id, max_num_offers=max_num_offers)

        view = StartDraftView(game)
        embed = view.get_embed(game)
        await thread.send(view=view, embed=embed)

async def setup(bot: Bot):
    await bot.add_cog(GamesCog(bot))

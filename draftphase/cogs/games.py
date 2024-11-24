from discord import Embed, File, Permissions, Role, TextChannel, app_commands, Interaction, Member
from discord.ext import commands
from discord.utils import format_dt

from draftphase.bot import Bot
from draftphase.discord_utils import CustomException, get_success_embed
from draftphase.game import Game
from draftphase.images import offers_to_image

@app_commands.guild_only()
class GamesCog(commands.GroupCog, group_name="match"):
    def __init__(self, bot: Bot):
        self.bot = bot

    @app_commands.command(name="create")
    @app_commands.default_permissions(manage_guild=True)
    async def start_draft_phase(
        self,
        interaction: Interaction,
        team1: Role,
        team2: Role,
        subtitle: str | None = None,
    ):
        if not isinstance(interaction.channel, TextChannel):
            raise CustomException(
                "Cannot use this here!",
                "Command must not be invoked from within a thread or forum post."
            )

        assert interaction.guild
        bot_perms = interaction.channel.permissions_for(interaction.guild.me)
        if not bot_perms.is_superset(Permissions(309237661696)):
            # TODO: Update perms
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

        game = Game.create(
            channel=interaction.channel,
            team1_id=team1.id,
            team2_id=team2.id,
            subtitle=subtitle,
        )

        await interaction.response.send_message(embed=get_success_embed(
            title="Match created!"
        ))

async def setup(bot: Bot):
    await bot.add_cog(GamesCog(bot))

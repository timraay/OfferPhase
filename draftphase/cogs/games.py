from discord import Permissions, Role, TextChannel, app_commands, Interaction
from discord.ext import commands

from draftphase.bot import Bot
from draftphase.discord_utils import CustomException, get_success_embed
from draftphase.embeds import create_game, get_game_embeds, send_or_edit_game_message
from draftphase.game import Game

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

        await create_game(
            interaction.client,
            interaction.channel,
            team1.id,
            team2.id,
            subtitle,
        )

        await interaction.response.send_message(embed=get_success_embed(
            title="Match created!",
        ), ephemeral=True)

    @app_commands.command(name="resend")
    @app_commands.default_permissions(manage_guild=True)
    async def resend_draft_phase(self, interaction: Interaction):
        assert interaction.channel_id is not None
        game = Game.load(interaction.channel_id)
        await interaction.response.defer(ephemeral=True)
        await send_or_edit_game_message(interaction.client, game)
        await interaction.followup.send(embed=get_success_embed("Resent message!"))

async def setup(bot: Bot):
    await bot.add_cog(GamesCog(bot))

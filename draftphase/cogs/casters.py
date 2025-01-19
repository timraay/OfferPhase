from discord import Member, Permissions, app_commands, Interaction
from discord.ext import commands

from draftphase.bot import Bot
from draftphase.discord_utils import get_success_embed
from draftphase.game import Caster

@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
class CastersCog(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    casters_group = app_commands.Group(
        name="casters",
        guild_only=True,
        default_permissions=Permissions(manage_guild=True),
    )

    @app_commands.command(name="register")
    async def register_as_caster(self, interaction: Interaction, name: str, channel_url: str):
        caster, created = Caster.upsert(interaction.user.id, name, channel_url)
        await interaction.response.send_message(
            embed=get_success_embed(
                "Registered you as caster!" if created else "Updated your caster information!",
            ).add_field(
                name="Name",
                value=caster.name
            ).add_field(
                name="Channel URL",
                value=caster.channel_url
            ),
            ephemeral=True
        )

    @casters_group.command(name="add")
    async def add_caster(self, interaction: Interaction, member: Member, name: str, channel_url: str):
        caster, created = Caster.upsert(interaction.user.id, name, channel_url)
        await interaction.response.send_message(
            embed=get_success_embed(
                "Added new caster!" if created else "Updated information of caster!",
            ).add_field(
                name="User",
                value=member.mention
            ).add_field(
                name="Name",
                value=caster.name
            ).add_field(
                name="Channel URL",
                value=caster.channel_url
            ),
            ephemeral=True
        )

async def setup(bot: Bot):
    await bot.add_cog(CastersCog(bot))
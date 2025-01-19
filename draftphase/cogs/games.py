import asyncio
from datetime import timezone
from dateutil.parser import parse as dt_parse

from discord import AllowedMentions, ChannelType, Interaction, Member, Permissions, Role, SelectOption, TextChannel, app_commands
from discord.ext import commands
from discord.utils import format_dt

from draftphase.bot import Bot
from draftphase.config import get_config
from draftphase.discord_utils import CustomException, get_success_embed
from draftphase.embeds import create_game, send_or_edit_game_message
from draftphase.game import FLAGS, Caster, Game, cached_get_casters, cached_get_streams_for_game
from draftphase.maps import TEAMS
from draftphase.views.open_controls import ControlsManager

LANG_CHOICES = [
    app_commands.Choice(name=f"{langname} ({lang} {flag})", value=lang)
    for lang, (langname, flag) in FLAGS.items()
]

def assert_team_role_validity(role: Role):
    if role.id not in TEAMS:
        raise CustomException(
            "Invalid team!",
            "No team exists in the `config.yaml` file with this Rep role ID."
        )

async def autocomplete_caster(interaction: Interaction, value: str):
    casters = cached_get_casters()
    options = []
    lowered_value = value.lower()
    for caster in casters:
        if lowered_value in caster.name or str(caster.user_id) in lowered_value:
            options.append(SelectOption(
                label=f"{caster.name} ({caster.channel_url})",
                value=str(caster.user_id)
            ))
    return options

async def autocomplete_stream(interaction: Interaction, value: str):
    if not interaction.channel:
        return []

    streams = cached_get_streams_for_game(interaction.channel.id)
    options = []
    lowered_value = value.lower()
    for stream in streams:
        stream_str = stream.to_text()
        if lowered_value in stream.to_text().lower():
            options.append(SelectOption(
                label=stream_str,
                value=str(stream.id)
            ))
    return options


@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
class GamesCog(commands.GroupCog, group_name="match"):
    def __init__(self, bot: Bot):
        self.bot = bot

    set_group = app_commands.Group(
        name="set",
        description="Set a property of a match",
    )

    reset_group = app_commands.Group(
        name="reset",
        description="Reset a property of a match",
    )

    streamers_group = app_commands.Group(
        name="streamers",
        description="Add or remove streamers",
    )

    @app_commands.command(name="create")
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
        if not bot_perms.is_superset(Permissions(343597444096)):
            # TODO: Update perms
            raise CustomException(
                "Bot is missing permissions!",
                (
                    "Make sure the following permissions are added, then try again:"
                    "\n\n"
                    "- View Channel\n"
                    "- Send Messages\n"
                    "- Send Messages in Threads\n"
                    "- Create Private Threads\n"
                    "- Manage Messages\n"
                    "- Attach Files\n"
                    "- Embed Links"
                )
            )
        
        assert_team_role_validity(team1)
        assert_team_role_validity(team2)

        await interaction.response.defer(ephemeral=True)

        await create_game(
            interaction.client,
            interaction.channel,
            team1.id,
            team2.id,
            subtitle,
        )

        thread = await interaction.channel.create_thread(
            name=interaction.channel.name.replace("-", " "),
            auto_archive_duration=10080,
            type=ChannelType.private_thread,
            invitable=False,
        )

        config = get_config()
        if config.bot.organiser_role_id:
            role = interaction.guild.get_role(config.bot.organiser_role_id)
            if role:
                await asyncio.gather(*[
                    thread.add_user(member)
                    for member in role.members
                ])

        await thread.send(
            f"{team1.mention} {team2.mention}",
            allowed_mentions=AllowedMentions(roles=True)
        )

        await interaction.followup.send(embed=get_success_embed(
            title="Match created!",
        ))

    @app_commands.command(name="resend")
    async def resend_draft_phase(self, interaction: Interaction):
        assert interaction.channel_id is not None
        game = Game.load(interaction.channel_id)
        await interaction.response.defer(ephemeral=True)
        await send_or_edit_game_message(interaction.client, game)
        await interaction.followup.send(embed=get_success_embed("Resent message!"))
    
    @app_commands.command(name="undo-action")
    async def undo_draft_action(self, interaction: Interaction, amount: int = 1):
        if amount <= 0:
            raise CustomException("Invalid argument!", "Amount must be greater than 0")

        assert interaction.channel_id is not None
        game = Game.load(interaction.channel_id)

        await interaction.response.defer(ephemeral=True)

        successes = 0
        for _ in range(amount):
            if not game.undo():
                break
            successes += 1

        if successes > 0:
            await ControlsManager().update_for_game(game)
        
        await interaction.followup.send(embed=get_success_embed(
            f"Undone {successes} actions!"
        ))

    @set_group.command(name="team1")
    async def set_team1(self, interaction: Interaction, role: Role):
        assert_team_role_validity(role)

        assert interaction.channel_id is not None
        game = Game.load(interaction.channel_id)
        game.team1_id = role.id
        game.save()

        await interaction.response.send_message(
            embed=get_success_embed(
                "Updated team 1 role!",
                role.mention
            ),
            ephemeral=True,
        )

        await send_or_edit_game_message(interaction.client, game)
        
    @set_group.command(name="team2")
    async def set_team2(self, interaction: Interaction, role: Role):
        assert_team_role_validity(role)

        assert interaction.channel_id is not None
        game = Game.load(interaction.channel_id)
        game.team2_id = role.id
        game.save()

        await interaction.response.send_message(
            embed=get_success_embed(
                "Updated team 2 role!",
                role.mention
            ),
            ephemeral=True,
        )

        await send_or_edit_game_message(interaction.client, game)


    @set_group.command(name="start_time")
    async def set_start_time(self, interaction: Interaction, value: str):
        try:
            start_time = dt_parse(value, fuzzy=True, dayfirst=True)
        except:
            raise CustomException(
                "Couldn't interpret start time!",
                "A few examples of what works:\n• `1/10/42 18:30`\n• `January 10 2042 6:30pm`\n• `6:30pm, 10th day of Jan, 2042`"
            )

        start_time = start_time.replace(microsecond=0, tzinfo=start_time.tzinfo or timezone.utc)

        assert interaction.channel_id is not None
        game = Game.load(interaction.channel_id)
        game.start_time = start_time
        game.save()

        await interaction.response.send_message(
            embed=get_success_embed(
                "Updated team 2 role!",
                f"{format_dt(start_time, 'F')} ({format_dt(start_time, 'R')})"
            ),
            ephemeral=True,
        )

        await send_or_edit_game_message(interaction.client, game)

    @reset_group.command(name="start_time")
    async def reset_start_time(self, interaction: Interaction):
        assert interaction.channel_id is not None
        game = Game.load(interaction.channel_id)
        game.start_time = None
        game.save()

        await interaction.response.send_message(
            embed=get_success_embed(
                "Match start time has been reset!",
            ),
            ephemeral=True,
        )

        await send_or_edit_game_message(interaction.client, game)


    @set_group.command(name="score")
    async def set_score(self, interaction: Interaction, score: str):
        assert interaction.channel_id is not None
        game = Game.load(interaction.channel_id)
        game.score = score
        game.save()

        await interaction.response.send_message(
            embed=get_success_embed(
                "Updated score!",
                score
            ),
            ephemeral=True,
        )

        await send_or_edit_game_message(interaction.client, game)

    @reset_group.command(name="score")
    async def reset_score(self, interaction: Interaction):
        assert interaction.channel_id is not None
        game = Game.load(interaction.channel_id)
        game.score = None
        game.save()

        await interaction.response.send_message(
            embed=get_success_embed(
                "Match score has been reset!",
            ),
            ephemeral=True,
        )

        await send_or_edit_game_message(interaction.client, game)


    @streamers_group.command(name="add")
    @app_commands.autocomplete(
        caster_id=autocomplete_caster
    )
    @app_commands.rename(
        caster_id="caster"
    )
    @app_commands.choices(
        lang=LANG_CHOICES
    )
    async def add_stream(self, interaction: Interaction, caster_id: str, lang: str):
        assert interaction.channel_id is not None
        game = Game.load(interaction.channel_id)

        caster = Caster.load(int(caster_id))
        stream = game.add_stream(caster, lang)

        await interaction.response.send_message(
            embed=get_success_embed(
                "Added stream",
                stream.to_text()
            ),
            ephemeral=True,
        )

        await send_or_edit_game_message(interaction.client, game)

    @streamers_group.command(name="add-manual")
    @app_commands.choices(
        lang=LANG_CHOICES
    )
    async def add_stream_manually(self, interaction: Interaction, member: Member, name: str, channel_url: str, lang: str):
        assert interaction.channel_id is not None
        game = Game.load(interaction.channel_id)
                
        caster, _ = Caster.upsert(member.id, name, channel_url)
        stream = game.add_stream(caster, lang)

        await interaction.response.send_message(
            embed=get_success_embed(
                "Added stream",
                stream.to_text()
            ),
            ephemeral=True,
        )

        await send_or_edit_game_message(interaction.client, game)

    @streamers_group.command(name="remove")
    @app_commands.autocomplete(
        stream_id_str=autocomplete_stream
    )
    @app_commands.rename(
        stream_id_str="stream"
    )
    async def remove_stream(self, interaction: Interaction, stream_id_str: str):
        assert interaction.channel_id is not None
        game = Game.load(interaction.channel_id)
        
        stream_id = int(stream_id_str)

        for stream in game.streams:
            if stream.id == stream_id:
                break
        else:
            raise ValueError("Stream not found")
        
        game.remove_stream(stream)

        await interaction.response.send_message(
            get_success_embed(
                "Removed stream",
                stream.to_text()
            ),
            ephemeral=True,
        )

        await send_or_edit_game_message(interaction.client, game)

async def setup(bot: Bot):
    await bot.add_cog(GamesCog(bot))

from discord import RawMessageDeleteEvent, app_commands, Interaction
import discord
from discord.ext import commands

from draftphase.db import get_cursor
from draftphase.discord_utils import CustomException, get_success_embed
from draftphase.polls import MessageableChannel, Poll, cached_get_polls
from draftphase.views.poll import PollView


async def autocomplete_poll(interaction: Interaction, value: str):
    polls = cached_get_polls()
    choices: list[app_commands.Choice] = []
    lowered_value = value.lower()
    for poll in polls:
        if lowered_value in poll.question.lower() or str(poll.channel_id) in lowered_value:
            choices.append(app_commands.Choice(
                name=poll.question if len(poll.question) < 100 else poll.question[:98]+'..',
                value=str(poll.id)
            ))
    return choices

@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
class PollCog(commands.GroupCog, group_name="poll"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="create", description="Create a poll here")
    async def poll_create(
        self,
        interaction: Interaction,
        question: str,
        choice1: str,
        choice2: str,
        choice3: str | None = None,
        choice4: str | None = None,
        choice5: str | None = None,
        choice6: str | None = None,
        choice7: str | None = None,
        choice8: str | None = None,
        choice9: str | None = None,
        choice10: str | None = None
    ):
        assert isinstance(interaction.channel, MessageableChannel)

        options = [
            choice for choice in
            (choice1, choice2, choice3, choice4, choice5, choice6, choice7, choice8, choice9, choice10)
            if choice is not None
        ]
        
        await Poll.create(interaction.channel, question, options, view_fn=PollView)

        await interaction.response.send_message(
            embed=get_success_embed("Poll created!"),
            ephemeral=True
        )
    
    @app_commands.command(name="end", description="End the poll and show the results")
    @app_commands.autocomplete(poll_id=autocomplete_poll)
    @app_commands.describe(
        anonymous_votes="Whether to anonymize the results"
    )
    @app_commands.rename(
        poll_id="poll"
    )
    async def poll_end(self, interaction: Interaction, poll_id: str, anonymous_votes: bool = False):
        poll = Poll.load(int(poll_id))
        if poll.is_closed:
            raise CustomException("Poll has already been ended!")

        poll.is_closed = True

        view = PollView(poll)
        await view.edit(anonymous_votes=anonymous_votes)

        poll.save()

        embed = poll.get_embed(anonymous_votes=False)
        embed.color = discord.Colour(7844437)
        embed.set_author(name="Poll ended!", icon_url="https://cdn.discordapp.com/emojis/809149148356018256.png")
        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    @app_commands.command(name="interim", description="Silently view the poll's current results")
    @app_commands.autocomplete(poll_id=autocomplete_poll)
    @app_commands.rename(
        poll_id="poll"
    )
    async def poll_interim(self, interaction: Interaction, poll_id: str):
        poll = Poll.load(int(poll_id))
        poll.is_closed = True  # Bit of a hack
        embed = poll.get_embed(anonymous_votes=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: RawMessageDeleteEvent):
        with get_cursor() as cur:
            cur.execute("DELETE FROM polls WHERE message_id = ?", (payload.message_id,))


async def setup(bot):
    await bot.add_cog(PollCog(bot))
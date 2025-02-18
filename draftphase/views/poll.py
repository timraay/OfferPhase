from discord import Colour, Embed, ui
from discord import ButtonStyle, Interaction, Member
from re import Match

from draftphase.discord_utils import CustomException, View, handle_error_wrap
from draftphase.maps import TEAMS
from draftphase.polls import NUMBER_EMOJIS, QUESTION_EMOJI, MessageableChannel, Poll, PollVote

def get_rep_role_of_member(member: Member):
    for role in member.roles:
        if role.id in TEAMS:
            break
    else:
        raise CustomException(
            "Only Team Representatives can vote!",
            "Contact an Admin if you believe this is a mistake."
        )
    
    return role


class PollCastVoteButton(ui.DynamicItem[ui.Button], template=r"poll:cast:(?P<poll_id>\d+):(?P<option_id>\d+)"):
    def __init__(self, item: ui.Button, poll_id: int, option_id: int):
        self.item = item
        self.poll_id = poll_id
        self.option_id = option_id

        self.item.custom_id = f"poll:cast:{self.poll_id}:{self.option_id}"
        super().__init__(item)

    @classmethod
    async def from_custom_id(cls, interaction: Interaction, item: ui.Button, match: Match[str]):
        poll_id = int(match.group("poll_id"))
        option_id = int(match.group("option_id"))
        return cls(item=item, poll_id=poll_id, option_id=option_id)
    
    @handle_error_wrap
    async def callback(self, interaction: Interaction):
        member = interaction.user
        assert isinstance(member, Member)
        assert interaction.message is not None

        role = get_rep_role_of_member(member)
        poll = Poll.load(self.poll_id)
        if poll.is_closed:
            raise CustomException(
                "This poll has ended!"
            )

        option = poll.get_option(self.option_id)

        PollVote.upsert(role.id, option)
        view = PollView(poll)
        await view.edit(interaction=interaction)

class PollSeeVoteButton(ui.DynamicItem[ui.Button], template=r"poll:see:(?P<poll_id>\d+)"):
    def __init__(self, item: ui.Button, poll_id: int):
        self.item = item
        self.poll_id = poll_id

        self.item.custom_id = f"poll:see:{self.poll_id}"
        super().__init__(item)

    @classmethod
    async def from_custom_id(cls, interaction: Interaction, item: ui.Button, match: Match[str]):
        poll_id = int(match.group("poll_id"))
        return cls(item=item, poll_id=poll_id)
    
    @handle_error_wrap
    async def callback(self, interaction: Interaction):
        member = interaction.user
        assert isinstance(member, Member)
        assert interaction.message is not None

        role = get_rep_role_of_member(member)
        poll = Poll.load(self.poll_id)
        if poll.is_closed:
            raise CustomException(
                "This poll has ended!"
            )

        try:
            vote = PollVote.load(role.id, poll.id)
        except ValueError:
            vote = None

        if vote:
            option_idx = poll.get_option_idx(vote.option_id)
            embed = Embed(color=Colour(7844437))
            embed.set_author(name=f"Your current vote is option {option_idx + 1}!", icon_url="https://cdn.discordapp.com/emojis/809149148356018256.png")
            embed.description = "To change your team's vote you can always press one of the buttons."
            embed.set_footer(text="Results will be revealed once the poll has ended.")
        
        else:
            embed = Embed(
                title="Your team has not yet voted!",
                description="As long as the poll is still active you can cast your vote by pressing one of the buttons. You can update your choice later on."
            )
            embed.set_footer(text="Results will be revealed once the poll has ended.")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class PollView(View):
    def __init__(self, poll: Poll):
        super().__init__(timeout=None)
        self.poll = poll

        for i, option in enumerate(self.poll.options):
            self.add_item(PollCastVoteButton(
                ui.Button(style=ButtonStyle.blurple, emoji=NUMBER_EMOJIS[i]),
                poll_id=self.poll.id,
                option_id=option.id
            ))
        
        self.add_item(PollSeeVoteButton(
            ui.Button(style=ButtonStyle.blurple, emoji=QUESTION_EMOJI),
            poll_id=self.poll.id
        ))

    async def send(self, interaction: Interaction, anonymous_votes: bool = False):
        assert isinstance(interaction.channel, MessageableChannel)

        embed = self.poll.get_embed(anonymous_votes=anonymous_votes)

        if self.poll.is_closed:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    async def edit(self, interaction: Interaction | None = None, anonymous_votes: bool = False):
        embed = self.poll.get_embed(anonymous_votes=anonymous_votes)
        view = None if self.poll.is_closed else self

        if interaction:
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            message = await self.poll.get_message()
            await message.edit(embed=embed, view=view)

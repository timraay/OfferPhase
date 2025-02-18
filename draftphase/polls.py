
from sqlite3 import Cursor
from typing import Callable, Self, Union
from cachetools import TTLCache, cached
import discord
from pydantic import BaseModel, Field

from draftphase.bot import DISCORD_BOT
from draftphase.db import get_cursor

NUMBER_EMOJIS = [
    # "0\ufe0f\u20e3",
    "1\ufe0f\u20e3",
    "2\ufe0f\u20e3",
    "3\ufe0f\u20e3",
    "4\ufe0f\u20e3",
    "5\ufe0f\u20e3",
    "6\ufe0f\u20e3",
    "7\ufe0f\u20e3",
    "8\ufe0f\u20e3",
    "9\ufe0f\u20e3",
    "\ud83d\udd1f"
]

QUESTION_EMOJI = "❓"

MessageableChannel = Union[
    discord.TextChannel, discord.VoiceChannel, discord.StageChannel, discord.Thread,
    discord.DMChannel, discord.PartialMessageable, discord.GroupChannel
]

class PollOption(BaseModel):
    id: int
    poll_id: int
    option: str

    @classmethod
    def _load_row(cls, data: tuple):
        return cls(
            id=data[0],
            poll_id=data[1],
            option=data[2],
        )
    
    @classmethod
    def create(cls, poll: 'Poll', option: str):
        with get_cursor() as cur:
            return cls._create(cur, poll, option)
        
    @classmethod
    def _create(cls, cur: Cursor, poll: 'Poll', option: str):
        cur.execute(
            "INSERT INTO poll_options(poll_id, option) VALUES (?,?) RETURNING *",
            (poll.id, option)
        )
        data = cur.fetchone()

        self = cls._load_row(data)
        poll.options.append(self)
        return self

    @classmethod
    def load_for_poll(cls, poll_id: int) -> list[Self]:
        options = []
        with get_cursor() as cur:
            cur.execute("SELECT * FROM poll_options WHERE poll_id = ? ORDER BY id", (poll_id,))
            all_data = cur.fetchall()
            for data in all_data:
                option = cls._load_row(data)
                options.append(option)
        return options
    
    def save(self):
        data = self.model_dump()
        with get_cursor() as cur:
            cur.execute(
                """
                UPDATE poll_options SET
                    poll_id=:poll_id,
                    option=:option
                WHERE id = :id
                """,
                data
            )

    def delete(self):
        with get_cursor() as cur:
            cur.execute("DELETE FROM poll_options WHERE id = ?", (self.id,))

class PollVote(BaseModel):
    role_id: int
    poll_id: int
    option_id: int

    @classmethod
    def _load_row(cls, data: tuple):
        return cls(
            role_id=data[0],
            poll_id=data[1],
            option_id=data[2],
        )
    
    @classmethod
    def create(cls, role_id: int, option: 'PollOption'):
        with get_cursor() as cur:
            cur.execute(
                "INSERT INTO poll_votes(role_id, poll_id, option_id) VALUES (?,?,?) RETURNING *",
                (role_id, option.poll_id, option.id)
            )
            data = cur.fetchone()

            self = cls._load_row(data)
            return self

    @classmethod
    def load(cls, role_id: int, poll_id: int) -> Self:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM poll_votes WHERE role_id = ? AND poll_id = ?", (role_id, poll_id,))
            data = cur.fetchone()
            if not data:
                raise ValueError("No vote exists with role ID %s and user ID %s" % (role_id, poll_id))
            return cls._load_row(data)

    @classmethod
    def load_for_poll(cls, poll_id: int) -> list[Self]:
        options = []
        with get_cursor() as cur:
            cur.execute("SELECT * FROM poll_votes WHERE poll_id = ? ORDER BY ROWID", (poll_id,))
            all_data = cur.fetchall()
            for data in all_data:
                option = cls._load_row(data)
                options.append(option)
        return options
    
    @classmethod
    def upsert(cls, role_id: int, option: 'PollOption') -> tuple[Self, bool]:
        try:
            vote = cls.load(role_id, option.poll_id)
        except ValueError:
            return cls.create(role_id, option), True
        else:
            if vote.option_id != option.id:
                vote.option_id = option.id
                vote.save()
            return vote, False

    def save(self):
        data = self.model_dump()
        with get_cursor() as cur:
            cur.execute(
                """
                UPDATE poll_votes SET
                    option_id=:option_id
                WHERE role_id = :role_id AND poll_id = :poll_id
                """,
                data
            )

    def delete(self):
        with get_cursor() as cur:
            cur.execute(
                "DELETE FROM poll_votes WHERE role_id = ? AND poll_id = ?",
                (self.role_id, self.poll_id)
            )


class PollResult:
    def __init__(self, poll: 'Poll') -> None:
        self.poll = poll
        self.votes: dict[int, set[int]] = {}
        self.highest_votes = 0
        self.recalculate()
    
    def recalculate(self):
        all_votes = PollVote.load_for_poll(self.poll.id)

        self.votes = {
            option.id: set()
            for option in self.poll.options
        }

        for vote in all_votes:
            self.votes[vote.option_id].add(vote.role_id)

        self.highest_votes = 0
        for votes in self.votes.values():
            if len(votes) > self.highest_votes:
                self.highest_votes = len(votes)
    
    @property
    def winning_options(self) -> set[int]:
        return {
            option_id
            for option_id, votes in self.votes.items()
            if len(votes) == self.highest_votes
        }
    
    @property
    def total_votes(self) -> int:
        s = 0
        for votes in self.votes.values():
            s += len(votes)
        return s

class Poll(BaseModel):
    id: int
    guild_id: int
    channel_id: int
    message_id: int | None
    question: str
    is_closed: bool
    options: list[PollOption] = Field(default_factory=list)

    @classmethod
    def _load_row(cls, data: tuple):
        poll_id = int(data[0])
        options = PollOption.load_for_poll(poll_id)
        return cls(
            id=poll_id,
            guild_id=data[1],
            channel_id=data[2],
            message_id=data[3],
            question=data[4],
            is_closed=data[5],
            options=options,
        )
    
    @classmethod
    async def create(cls, channel: MessageableChannel, question: str, options: list[str], view_fn: Callable[[Self], discord.ui.View] | None):
        assert channel.guild is not None

        with get_cursor() as cur:
            cur.execute(
                "INSERT INTO polls(guild_id, channel_id, question) VALUES (?,?,?) RETURNING *",
                (channel.guild.id, channel.id, question)
            )
            data = cur.fetchone()
            poll = cls._load_row(data)

            for option_str in options:
                PollOption._create(cur, poll, option_str)
            
            embed = poll.get_embed()
            if view_fn:
                view = view_fn(poll)
                message = await channel.send(embed=embed, view=view)
            else:
                message = await channel.send(embed=embed)
            
            poll.message_id = message.id
            cur.execute(
                "UPDATE polls SET message_id = ? WHERE id = ?",
                (message.id, poll.id)
            )

            return poll

    @classmethod
    def load(cls, poll_id: int) -> Self:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM polls WHERE id = ?", (poll_id,))
            data = cur.fetchone()
            if not data:
                raise ValueError("No poll exists with ID %s" % poll_id)
            return cls._load_row(data)

    @classmethod
    def from_message_id(cls, message_id: int) -> Self:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM polls WHERE message_id = ?", (message_id,))
            data = cur.fetchone()
            if not data:
                raise ValueError("No poll exists with message ID %s" % message_id)
            return cls._load_row(data)

    @classmethod
    def load_all(cls, active_only: bool) -> list[Self]:
        polls = []
        with get_cursor() as cur:
            if active_only:
                cur.execute("SELECT * FROM polls WHERE NOT is_closed")
            else:
                cur.execute("SELECT * FROM polls")
            all_data = cur.fetchall()
            for data in all_data:
                poll = cls._load_row(data)
                polls.append(poll)
        return polls
    
    def save(self):
        data = self.model_dump(exclude={'options'})

        with get_cursor() as cur:
            cur.execute(
                """
                UPDATE polls SET
                    guild_id=:guild_id,
                    channel_id=:channel_id,
                    message_id=:message_id,
                    question=:question,
                    is_closed=:is_closed
                WHERE id = :id
                """,
                data
            )
    
    def delete(self):
        with get_cursor() as cur:
            cur.execute("DELETE FROM polls WHERE id = ?", (self.id,))

    async def get_message(self):
        if not self.message_id:
            raise Exception("Message ID not set")

        if channel := DISCORD_BOT.get_channel(self.channel_id):
            assert isinstance(channel, MessageableChannel)
            try:
                message = await channel.fetch_message(self.message_id)
                return message
            except:
                pass
        
        raise ValueError("Message cannot be found")

    def get_votes(self):
        return PollVote.load_for_poll(self.id)

    def get_result(self):
        return PollResult(self)

    def get_option(self, option_id: int):
        for option in self.options:
            if option.id == option_id:
                return option
        raise ValueError("Unknown option with ID %s" % option_id)
    
    def get_option_idx(self, option_id: int):
        for i, option in enumerate(self.options):
            if option.id == option_id:
                return i
        raise ValueError("Unknown option with ID %s" % option_id)

    def get_embed(self, anonymous_votes: bool = False):
        result = self.get_result()

        if self.is_closed:
            lines = []
            for option in self.options:
                votes = result.votes[option.id]
                votes_num = len(votes)
                votes_rate = (votes_num / result.total_votes) if result.total_votes else 0.0

                vote_or_votes = "vote" if votes_num == 1 else "votes"
                if votes_num == result.highest_votes:
                    line = f"\\✅ {option.option} | **__{votes_num} {vote_or_votes}__** " + "(__{:.1%}__)".format(votes_rate)
                else:
                    line = f"\\🔳 {option.option} | **{votes_num} {vote_or_votes}** " + "({:.1%})".format(votes_rate)
                lines.append(line)

                if not anonymous_votes:
                    if votes:
                        line = "> " + ", ".join([
                            f"<@&{role_id}>" for role_id in votes
                        ])
                        lines.append(line)
                    lines.append('')

            description = "\n".join(lines)
            footer = f"{result.total_votes} votes"
        
        else:
            description="\n".join(
                f"{NUMBER_EMOJIS[i]} {option.option}"
                for i, option in enumerate(self.options)
            )
            footer = f"{result.total_votes} votes • Only one vote per team. Press {QUESTION_EMOJI} to see your team's vote."

        embed = discord.Embed(
            color=discord.Colour(3315710),
            description=description,
        )
        embed.set_author(
            name=self.question,
            icon_url="https://cdn.discordapp.com/attachments/729998051288285256/924971834343059496/unknown.png"
        )
        embed.set_footer(text=footer)

        return embed


@cached(TTLCache(maxsize=100, ttl=20))
def cached_get_polls():
    return Poll.load_all(active_only=True)

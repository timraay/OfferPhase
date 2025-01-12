from datetime import datetime, timezone
from discord import CategoryChannel, TextChannel
import discord
from pydantic import BaseModel

from draftphase.bot import DISCORD_BOT
from draftphase.db import get_cursor
from draftphase.game import Game
from draftphase.maps import Faction

def get_games_in_category(category: CategoryChannel):
    channel_ids = [channel.id for channel in category.text_channels]
    return Game.load_many(channel_ids)

def games_to_calendar_embed(category: CategoryChannel, games: list[Game]):
    embed = discord.Embed(color=0xFFFFFF)
    embed.set_author(
        name=category.name if len(games) <= 15 else f"{category.name} (First 15 matches)",
        icon_url=category.guild.icon.url if category.guild.icon else None
    )

    max_time = datetime(3000, 1, 1, tzinfo=timezone.utc)
    for game in sorted(games[:15], key=lambda g: g.start_time or max_time):
        lines = list()
        teams = (game.get_team(1), game.get_team(2))
        if game.is_done():
            factions: tuple[Faction, Faction] = (game.get_team_faction(1), game.get_team_faction(2)) # type: ignore
            
            lines.append(f"{factions[0].emojis.default} <@&{teams[0].name}> vs {factions[1].emojis.default} <@&{teams[1].name}>")
        else:
            lines.append(f"<@&{teams[0].public_role_id}> vs <@&{teams[1].public_role_id}>")

        offer = game.get_accepted_offer()
        map_details = offer.get_map_details() if offer else None

        lines += [
            f"> \\📅 " + (f"<t:{int(game.start_time.timestamp())}:f>" if game.start_time else "*No date...*"),
            f"> \\🗺️ " + (f"Map: **{map_details.short_name}**" if map_details else "*No map...*"),
            f"> \\🎯 " + (f"Score: ||**{game.score}**||" if game.score else "*No score...*"),
        ]

        if game.streams:
            lines += [f"\\🎙️ {s.to_text(True)}" for s in game.streams]
            if game.stream_delay:
                lines.append(f"\\🎙️ (+{game.stream_delay} min. delay)")
        
        lines.append(f" → <#{game.channel_id}>")
        
        embed.add_field(name=f"{teams[0].name} vs {teams[1].name}", value="\n".join(lines))
    return embed

class CalendarCategory(BaseModel):
    guild_id: int
    channel_id: int
    message_id: int
    category_id: int

    @classmethod
    async def create(cls, category: CategoryChannel, channel: TextChannel):
        assert category.guild.id == channel.guild.id

        games = get_games_in_category(category)
        embed = games_to_calendar_embed(category, games)

        message = await channel.send(embed=embed)

        with get_cursor() as cur:
            cur.execute(
                "INSERT INTO calendar(guild_id, channel_id, message_id, category_id) VALUES (?,?,?,?) RETURNING *",
                (channel.guild.id, channel.id, message.id, category.id)
            )
            data = cur.fetchone()
            return cls._load_row(data)

    @classmethod
    def _load_row(cls, data: tuple):
        return cls(
            guild_id=data[0],
            channel_id=data[1],
            message_id=data[2],
            category_id=data[3],
        )

    @classmethod
    def load(cls, category_id: int, channel_id: int):
        with get_cursor() as cur:
            cur.execute(
                "SELECT * FROM calandar WHERE category_id = ? AND channel_id = ?",
                (category_id, channel_id)
            )
            data = cur.fetchone()
            if not data:
                raise ValueError("No calendar exists with category ID %s and channel ID %s" % (category_id, channel_id))
            
            return cls._load_row(data)

    @classmethod
    def load_all_in_guild(cls, guild_id: int):
        with get_cursor() as cur:
            cur.execute(
                "SELECT * FROM calendar WHERE guild_id = ?",
                (guild_id,)
            )
            rows = cur.fetchall()
        
            calendars = [cls._load_row(row) for row in rows]
            return calendars
    
    @classmethod
    def load_all(cls):
        with get_cursor() as cur:
            cur.execute("SELECT * FROM calendar")
            rows = cur.fetchall()
        
            calendars = [cls._load_row(row) for row in rows]
            return calendars

    def save(self):
        data = self.model_dump()
        with get_cursor() as cur:
            cur.execute(
                """
                UPDATE games SET
                    guild_id=:guild_id,
                    message_id=:message_id,
                WHERE channel_id = :channel_id AND category_id = :category_id
                """,
                data
            )

    def delete(self):
        with get_cursor() as cur:
            cur.execute(
                "DELETE FROM calendar WHERE channel_id = ? AND category_id = ?",
                (self.channel_id, self.category_id)
            )

    async def get_channel(self) -> TextChannel | None:
        channel = DISCORD_BOT.get_channel(self.channel_id)
        if not channel:
            try:
                channel = DISCORD_BOT.fetch_channel(self.channel_id)
            except discord.NotFound:
                pass
        if channel:
            assert isinstance(channel, TextChannel)
        return channel

    async def get_message(self):
        channel = await self.get_channel()
        if not channel:
            return None
        
        try:
            return await channel.fetch_message(self.message_id)
        except discord.NotFound:
            pass

    async def get_category(self) -> CategoryChannel | None:
        channel = DISCORD_BOT.get_channel(self.category_id)
        if not channel:
            try:
                channel = DISCORD_BOT.fetch_channel(self.category_id)
            except discord.NotFound:
                pass
        if channel:
            assert isinstance(channel, CategoryChannel)
        return channel

    async def get_games(self) -> list[Game]:
        category = await self.get_category()
        if not category:
            return []
        return get_games_in_category(category)

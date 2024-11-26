from datetime import datetime
from typing import Optional, Self
from discord import Member, TextChannel
import discord
from pydantic import BaseModel, Field

from draftphase.db import get_cursor
from draftphase.discord_utils import GameStateError
from draftphase.maps import MAPS, Environment, LayoutType

MAX_OFFERS = 10
STREAM_DELAY = 15

FLAGS = dict(
    UK=("EN", "🇬🇧"),
    US=("EN", "🇺🇸"),
    DE=("DE", "🇩🇪"),
    NL=("NL", "🇳🇱"),
    FR=("FR", "🇫🇷"),
    CN=("CN", "🇨🇳"),
    RU=("RU", "🇷🇺"),
    ES=("ES", "🇪🇸"),
    JP=("JP", "🇯🇵"),
    AU=("EN", "🇦🇺"),
)

class Offer(BaseModel):
    id: int
    game_id: int
    offer_no: int
    player_id: int
    map: str
    environment: Environment
    layout: LayoutType
    accepted: bool | None
    
    @classmethod
    def create(cls, game: 'Game', map: str, environment: Environment, layout: LayoutType):
        offer_no = len(game.offers) + 1
        player_id = game.team_idx_to_id(game.turn())

        if offer_no > game.max_num_offers:
            raise GameStateError("Offer exceeds max offer limit")

        with get_cursor() as cur:
            cur.execute(
                "INSERT INTO offers(game_id, offer_no, player_id, map, environment, layout) VALUES (?,?,?,?,?,?) RETURNING *",
                (game.channel_id, offer_no, player_id, map, environment.value, "".join([str(i) for i in layout]))
            )
            data = cur.fetchone()

            self = cls(
                id=data[0],
                game_id=data[1],
                offer_no=data[2],
                player_id=data[3],
                map=data[4],
                environment=Environment(data[5]),
                layout=tuple(data[6]),
                accepted=None if data[7] is None else bool(data[7]),
            )
            game.offers.append(self)
            return self

    @classmethod
    def load_for_game(cls, game_id: int) -> list[Self]:
        offers = []
        with get_cursor() as cur:
            cur.execute("SELECT * FROM offers WHERE game_id = ? ORDER BY offer_no", (game_id,))
            all_data = cur.fetchall()
            for data in all_data:
                offers.append(cls(
                    id=data[0],
                    game_id=data[1],
                    offer_no=data[2],
                    player_id=data[3],
                    map=data[4],
                    environment=Environment(data[5]),
                    layout=tuple(data[6]),
                    accepted=None if data[7] is None else bool(data[7]),
                ))
        return offers
    
    def save(self):
        data = self.model_dump()
        data["layout"] = "".join([str(i) for i in self.layout])

        with get_cursor() as cur:
            cur.execute(
                """
                UPDATE offers SET
                    offer_no=:offer_no,
                    player_id=:player_id,
                    map=:map,
                    environment=:environment,
                    layout=:layout,
                    accepted=:accepted
                WHERE id = :id
                """,
                data
            )
    
    def get_map_details(self):
        return MAPS[self.map]

class Streamer(BaseModel):
    id: int
    game_id: int
    lang: str
    name: str
    url: str

    @classmethod
    def create(cls, game: 'Game', lang: str, name: str, url: str):
        with get_cursor() as cur:
            cur.execute(
                "INSERT INTO streamers(game_id, lang, name, url) VALUES (?,?,?,?) RETURNING *",
                (game.channel_id, lang, name, url)
            )
            data = cur.fetchone()

            self = cls(
                id=data[0],
                game_id=data[1],
                lang=data[2],
                name=data[3],
                url=data[4],
            )
            game.streamers.append(self)
            return self

    @classmethod
    def load_for_game(cls, game_id: int) -> list[Self]:
        streamers = []
        with get_cursor() as cur:
            cur.execute("SELECT * FROM streamers WHERE game_id = ? ORDER BY id", (game_id,))
            all_data = cur.fetchall()
            for data in all_data:
                streamers.append(cls(
                    id=data[0],
                    game_id=data[1],
                    lang=data[2],
                    name=data[3],
                    url=data[4],
                ))
        return streamers
    
    def save(self):
        data = self.model_dump()
        with get_cursor() as cur:
            cur.execute(
                """
                UPDATE streamers SET
                    lang=:lang,
                    name=:name,
                    url=:url,
                WHERE id = :id
                """,
                data
            )

    @property
    def flag(self):
        lang = self.lang.upper()
        if len(lang) != 2:
            return '❓'
        flags = FLAGS.get(lang, ['??', '❓'])
        return flags[1]
    
    @property
    def displaylang(self):
        lang = self.lang.upper()
        if len(lang) != 2:
            return '??'
        flags = FLAGS.get(lang, ['??', '❓'])
        return flags[0]
        
    def to_text(self, small=False):
        if small:
            return f"[{self.flag}{self.name}]({self.url})"
        else:
            return f"({self.displaylang}) {self.flag} {self.name} - <{self.url}>"

class Game(BaseModel):
    message_id: int | None
    channel_id: int
    guild_id: int
    team1_id: int
    team2_id: int
    subtitle: str | None = None
    start_time: datetime | None = None
    max_num_offers: int = MAX_OFFERS
    flip_sides: Optional[bool] = None
    stream_delay: int = STREAM_DELAY
    offers: list[Offer] = Field(default_factory=list)
    streamers: list[Streamer] = Field(default_factory=list)

    @classmethod
    def create(
        cls,
        channel: TextChannel,
        team1_id: int,
        team2_id: int,
        message_id: int | None = None,
        subtitle: str | None = None,
        max_num_offers: int = MAX_OFFERS,
        stream_delay: int = STREAM_DELAY,
    ):
        with get_cursor() as cur:
            cur.execute(
                "INSERT INTO games(message_id, channel_id, guild_id, team1_id, team2_id, subtitle, max_num_offers, stream_delay) VALUES (?,?,?,?,?,?,?,?) RETURNING *",
                (message_id, channel.id, channel.guild.id, team1_id, team2_id, subtitle, max_num_offers, stream_delay)
            )
            data = cur.fetchone()

            return cls(
                message_id=data[0],
                channel_id=data[1],
                guild_id=data[2],
                team1_id=data[3],
                team2_id=data[4],
                subtitle=data[5],
                start_time=datetime.fromtimestamp(data[6]) if data[6] else None,
                max_num_offers=data[7],
                flip_sides=data[8],
                stream_delay=data[9],
            )
    
    @classmethod
    def load(cls, channel_id: int):
        with get_cursor() as cur:
            cur.execute("SELECT * FROM games WHERE channel_id = ?", (channel_id,))
            data = cur.fetchone()
            if not data:
                raise ValueError("No game exists with ID %s" % channel_id)
            
            channel_id = int(data[1])
            offers = Offer.load_for_game(channel_id)
            streamers = Streamer.load_for_game(channel_id)
            return cls(
                message_id=data[0],
                channel_id=channel_id,
                guild_id=data[2],
                team1_id=data[3],
                team2_id=data[4],
                subtitle=data[5],
                start_time=datetime.fromtimestamp(data[6]) if data[6] else None,
                max_num_offers=data[7],
                flip_sides=data[8],
                stream_delay=data[9],
                offers=offers,
                streamers=streamers,
            )

    def save(self):
        data = self.model_dump()
        if self.start_time:
            data["start_time"] = int(self.start_time.timestamp())
        with get_cursor() as cur:
            cur.execute(
                """
                UPDATE games SET
                    message_id=:message_id,
                    team1_id=:team1_id,
                    team2_id=:team2_id,
                    subtitle=:subtitle,
                    start_time=:start_time,
                    max_num_offers=:max_num_offers,
                    flip_sides=:flip_sides,
                    stream_delay=:stream_delay
                WHERE channel_id = :channel_id
                """,
                data
            )

    def team_idx_to_id(self, team_idx: int):
        if team_idx == 1:
            return self.team1_id
        else:
            return self.team2_id
    
    def team_id_to_idx(self, team_id: int):
        if team_id == self.team1_id:
            return 1
        elif team_id == self.team2_id:
            return 2
        else:
            raise ValueError("Invalid team ID")
        
    def turn(self, *, opponent: bool = False):
        if (len(self.offers) % 2 == 0) != opponent:
            return 1
        else:
            return 2

    def is_user_participating(self, member: Member):
        if member.guild_permissions.administrator:
            return True

        if discord.utils.get(member.roles, id=self.team1_id) is None:
            return False
        if discord.utils.get(member.roles, id=self.team2_id) is None:
            return False

        return True

    def is_users_turn(self, member: Member):
        if member.guild_permissions.administrator:
            return True

        team_id = self.team_idx_to_id(self.turn())
        return discord.utils.get(member.roles, id=team_id) is not None

    def get_offers_for_team_idx(self, team_idx: int):
        offset = (team_idx + 1) % 2
        return self.offers[offset::2]

    def get_max_num_offers_for_team_idx(self, team_idx: int):
        if (team_idx % 2 == 1):
            return (self.max_num_offers // 2) + (self.max_num_offers % 2)
        else:
            return (self.max_num_offers // 2)

    def is_offer_available(self) -> bool:
        return bool(self.offers and self.offers[-1].accepted is None)

    def is_done(self) -> bool:
        return self.get_accepted_offer() is not None
    
    def get_accepted_offer(self) -> Offer | None:
        for offer in self.offers:
            if offer.accepted:
                return offer
        return None

    def create_offer(self, map: str, environment: Environment, layout: LayoutType):
        if self.is_done():
            raise GameStateError("Game is already done")
        if self.is_offer_available():
            raise GameStateError("Most recent offer is still unanswered")
        
        return Offer.create(self, map=map, environment=environment, layout=layout)

    def accept_offer(self, offer: Offer, flip_sides: bool):
        if offer.game_id != self.channel_id:
            raise ValueError("Offer is not part of this game")

        if self.is_done():
            raise GameStateError("Game is already done")
        if not self.is_offer_available():
            raise GameStateError("All offers have been answered already")

        latest_offer = self.offers[-1]
        if offer.id != latest_offer.id:
            latest_offer.accepted = False
            latest_offer.save()

        offer.accepted = True
        self.flip_sides = flip_sides

        offer.save()
        self.save()

    def decline_offer(self):
        if self.is_done():
            raise GameStateError("Game is already done")
        if not self.is_offer_available():
            raise GameStateError("All offers have been answered already")

        self.offers[-1].accepted = False
        self.offers[-1].save()

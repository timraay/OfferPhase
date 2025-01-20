from cachetools import cached, TTLCache
from datetime import datetime, timezone
from random import random
import re
from typing import Literal, Self, Sequence
from discord import Member, TextChannel
import discord
from pydantic import BaseModel, Field

from draftphase.db import get_cursor
from draftphase.discord_utils import GameStateError
from draftphase.maps import ENVIRONMENTS, MAPS, TEAMS, LayoutType, Team, has_middleground

MAX_OFFERS = 12
STREAM_DELAY = 15

RE_SCORES = re.compile(r"(\d+)\s*[-:|/\\]\s*(\d+)")

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
DEFAULT_FLAG = ['??', '❓']

class Offer(BaseModel):
    id: int
    game_id: int
    offer_no: int
    team_id: int
    map: str
    environment: str
    layout: LayoutType
    accepted: bool | None
    
    @classmethod
    def create(cls, game: 'Game', map: str, environment: str, layout: LayoutType):
        offer_no = len(game.offers) + 1
        team_id = game.team_idx_to_id(game.turn())

        if offer_no > game.max_num_offers:
            raise GameStateError("Offer exceeds max offer limit")

        with get_cursor() as cur:
            cur.execute(
                "INSERT INTO offers(game_id, offer_no, team_id, map, environment, layout) VALUES (?,?,?,?,?,?) RETURNING *",
                (game.channel_id, offer_no, team_id, map, environment, "".join([str(i) for i in layout]))
            )
            data = cur.fetchone()

            self = cls(
                id=data[0],
                game_id=data[1],
                offer_no=data[2],
                team_id=data[3],
                map=data[4],
                environment=data[5],
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
                    team_id=data[3],
                    map=data[4],
                    environment=data[5],
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
                    team_id=:team_id,
                    map=:map,
                    environment=:environment,
                    layout=:layout,
                    accepted=:accepted
                WHERE id = :id
                """,
                data
            )
    
    def delete(self):
        with get_cursor() as cur:
            cur.execute("DELETE FROM offers WHERE id = ?", (self.id,))

    def get_map_details(self):
        return MAPS[self.map]
    
    def get_environment(self):
        return ENVIRONMENTS[self.environment]

class Caster(BaseModel):
    user_id: int
    name: str
    channel_url: str

    @classmethod
    def create(cls, user_id: int, name: str, channel_url: str):
        if not channel_url.startswith("https://"):
            raise ValueError("Channel URL must start with \"https://\"")
        with get_cursor() as cur:
            cur.execute(
                "INSERT INTO casters(user_id, name, channel_url) VALUES (?,?,?) RETURNING *",
                (user_id, name, channel_url)
            )
            data = cur.fetchone()

            self = cls(
                user_id=data[0],
                name=data[1],
                channel_url=data[2],
            )
            return self
    
    @classmethod
    def load(cls, user_id: int) -> Self:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM casters WHERE user_id = ?", (user_id,))
            data = cur.fetchone()
            if not data:
                raise ValueError("No caster exists with ID %s" % user_id)

            caster = cls(
                user_id=data[0],
                name=data[1],
                channel_url=data[2],
            )
            return caster

    @classmethod
    def load_all(cls) -> list[Self]:
        casters = []
        with get_cursor() as cur:
            cur.execute("SELECT * FROM casters")
            data = cur.fetchall()
            caster = cls(
                user_id=data[0],
                name=data[1],
                channel_url=data[2],
            )
            casters.append(caster)
        return casters

    @classmethod
    def upsert(cls, user_id: int, name: str, channel_url: str) -> tuple[Self, bool]:
        try:
            caster = cls.load(user_id)
        except ValueError:
            return cls.create(user_id, name, channel_url), True
        else:
            caster.name = name
            caster.channel_url = channel_url
            caster.save()
            return caster, False

    def save(self):
        data = self.model_dump()
        with get_cursor() as cur:
            cur.execute(
                """
                UPDATE casters SET
                    name=:name,
                    channel_url=:channel_url
                WHERE user_id = :user_id
                """,
                data
            )

class Stream(BaseModel):
    id: int
    game_id: int
    caster: Caster
    lang: str

    @classmethod
    def create(cls, game: 'Game', caster: Caster, lang: str):
        with get_cursor() as cur:
            cur.execute(
                "INSERT INTO streams(game_id, caster_id, lang) VALUES (?,?,?) RETURNING *",
                (game.channel_id, caster.user_id, lang)
            )
            data = cur.fetchone()

            self = cls(
                id=data[0],
                game_id=data[1],
                caster=caster,
                lang=data[3],
            )
            game.streams.append(self)
            return self

    @classmethod
    def load_for_game(cls, game_id: int) -> list[Self]:
        streams = []
        with get_cursor() as cur:
            cur.execute("SELECT * FROM streams INNER JOIN casters ON streams.caster_id = casters.user_id WHERE game_id = ? ORDER BY id", (game_id,))
            all_data = cur.fetchall()
            for data in all_data:
                streams.append(cls(
                    id=data[0],
                    game_id=data[1],
                    caster=Caster(
                        user_id=data[4],
                        name=data[5],
                        channel_url=data[6],
                    ),
                    lang=data[3],
                ))
        return streams
    
    def save(self):
        data = self.model_dump(exclude={"caster"})
        data["caster_id"] = self.caster.user_id
        with get_cursor() as cur:
            cur.execute(
                """
                UPDATE streams SET
                    caster_id=:caster_id,
                    lang=:lang,
                WHERE id = :id
                """,
                data
            )

    def delete(self):
        with get_cursor() as cur:
            cur.execute("DELETE FROM streams WHERE id = ?", (self.id,))

    @property
    def flag(self):
        lang = self.lang.upper()
        if len(lang) != 2:
            return '❓'
        flags = FLAGS.get(lang, DEFAULT_FLAG)
        return flags[1]
    
    @property
    def displaylang(self):
        lang = self.lang.upper()
        if len(lang) != 2:
            return '??'
        flags = FLAGS.get(lang, DEFAULT_FLAG)
        return flags[0]
        
    def to_text(self, small=False):
        if small:
            return f"[{self.flag}{self.caster.name}]({self.caster.channel_url})"
        else:
            return f"({self.displaylang}) {self.flag} {self.caster.name} - <{self.caster.channel_url}>"

class Prediction(BaseModel):
    id: int
    game_id: int
    user_id: int
    team1_score: int
    
    @classmethod
    def create(cls, game_id: int, user_id: int, team1_score: int):
        with get_cursor() as cur:
            cur.execute(
                "INSERT INTO predictions(game_id, user_id, team1_score) VALUES (?,?,?) RETURNING *",
                (game_id, user_id, team1_score)
            )
            data = cur.fetchone()

            self = cls(
                id=data[0],
                game_id=data[1],
                user_id=data[2],
                team1_score=data[3],
            )
            return self

    @classmethod
    def load(cls, game_id: int, user_id: int) -> Self:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM predictions WHERE game_id = ? AND user_id = ?", (game_id, user_id,))
            data = cur.fetchone()
            if not data:
                raise ValueError("No prediction exists for user with ID %s of game with ID %s" % (user_id, game_id))

            prediction = cls(
                id=data[0],
                game_id=data[1],
                user_id=data[2],
                team1_score=data[3],
            )
            return prediction

    @classmethod
    def load_for_game(cls, game_id: int) -> list[Self]:
        predictions = []
        with get_cursor() as cur:
            cur.execute("SELECT * FROM predictions WHERE game_id = ?", (game_id,))
            all_data = cur.fetchall()
            for data in all_data:
                predictions.append(cls(
                    id=data[0],
                    game_id=data[1],
                    user_id=data[2],
                    team1_score=data[3],
                ))
        return predictions
    
    def save(self):
        data = self.model_dump()

        with get_cursor() as cur:
            cur.execute(
                """
                UPDATE predictions SET
                    game_id=:game_id,
                    user_id=:user_id,
                    team1_score=:team1_score
                WHERE id = :id
                """,
                data
            )
    
    def delete(self):
        with get_cursor() as cur:
            cur.execute("DELETE FROM predictions WHERE id = ?", (self.id,))

    @classmethod
    def upsert(cls, game_id: int, user_id: int, team1_score: int) -> tuple[Self, bool]:
        try:
            self = cls.load(game_id, user_id)
        except ValueError:
            return cls.create(game_id, user_id, team1_score), True
        else:
            if self.team1_score != team1_score:
                self.team1_score = team1_score
                self.save()
            return self, False

    def get_scores(self) -> tuple[int, int]:
        team1_score = min(max(self.team1_score, 0), 5)
        team2_score = 5 - team1_score
        return (team1_score, team2_score)

    def winner_idx(self) -> Literal[1, 2]:
        return 1 if self.team1_score >= 3 else 2

class Game(BaseModel):
    message_id: int | None
    channel_id: int
    guild_id: int
    team1_id: int
    team2_id: int
    subtitle: str | None = None
    start_time: datetime | None = None
    score: str | None = None
    max_num_offers: int = MAX_OFFERS
    flip_coin: bool
    flip_advantage: bool | None = None
    flip_sides: bool | None = None
    stream_delay: int = STREAM_DELAY
    offers: list[Offer] = Field(default_factory=list)
    streams: list[Stream] = Field(default_factory=list)

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
        flip_coin = random() > 0.5
        with get_cursor() as cur:
            cur.execute(
                "INSERT INTO games(message_id, channel_id, guild_id, team1_id, team2_id, subtitle, max_num_offers, flip_coin, stream_delay) VALUES (?,?,?,?,?,?,?,?,?) RETURNING *",
                (message_id, channel.id, channel.guild.id, team1_id, team2_id, subtitle, max_num_offers, flip_coin, stream_delay)
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
                score=data[7],
                max_num_offers=data[8],
                flip_coin=data[9],
                flip_advantage=data[10],
                flip_sides=data[11],
                stream_delay=data[12],
            )
    
    @classmethod
    def _load_row(cls, data: tuple):
        channel_id = int(data[1])
        offers = Offer.load_for_game(channel_id)
        streams = Stream.load_for_game(channel_id)
        return cls(
            message_id=data[0],
            channel_id=channel_id,
            guild_id=data[2],
            team1_id=data[3],
            team2_id=data[4],
            subtitle=data[5],
            start_time=datetime.fromtimestamp(data[6], tz=timezone.utc) if data[6] else None,
            score=data[7],
            max_num_offers=data[8],
            flip_coin=data[9],
            flip_advantage=data[10],
            flip_sides=data[11],
            stream_delay=data[12],
            offers=offers,
            streams=streams,
        )

    @classmethod
    def load(cls, channel_id: int):
        with get_cursor() as cur:
            cur.execute("SELECT * FROM games WHERE channel_id = ?", (channel_id,))
            data = cur.fetchone()
            if not data:
                raise ValueError("No game exists with ID %s" % channel_id)
            
            return cls._load_row(data)

    @classmethod
    def load_many(cls, channel_ids: Sequence[int]):
        with get_cursor() as cur:
            cur.execute("SELECT * FROM games WHERE channel_id IN ?", (channel_ids,))
            rows = cur.fetchall()
            games: list[Self] = []
            
            for data in rows:
                game = cls._load_row(data)
                games.append(game)
        
        return games

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
                    score=:score,
                    flip_coin=:flip_coin,
                    flip_advantage=:flip_advantage,
                    flip_sides=:flip_sides,
                    stream_delay=:stream_delay
                WHERE channel_id = :channel_id
                """,
                data
            )

    def delete(self):
        with get_cursor() as cur:
            cur.execute("DELETE FROM games WHERE channel_id = ?", (self.channel_id,))

    def get_scores(self) -> tuple[int, int] | None:
        if not self.score:
            return None
        
        match = RE_SCORES.search(self.score)
        if not match:
            return None
        
        groups = match.groups()
        return (int(groups[0]), int(groups[1]))

    def get_predictions(self) -> list[Prediction]:
        return Prediction.load_for_game(self.channel_id)

    def team_idx_to_id(self, team_idx: Literal[1, 2]) -> int:
        if team_idx == 1:
            return self.team1_id
        else:
            return self.team2_id
    
    def team_id_to_idx(self, team_id: int) -> Literal[1, 2]:
        if team_id == self.team1_id:
            return 1
        elif team_id == self.team2_id:
            return 2
        else:
            raise ValueError("Invalid team ID")
    
    def get_team(self, team_idx: Literal[1, 2]):
        team_id = self.team_idx_to_id(team_idx)
        return TEAMS.get(
            team_id,
            Team(
                rep_role_id=team_id,
                public_role_id=team_id,
                region="Unknown",
                emoji="❓",
                name="Unknown Team",
            )
        )
    
    def get_team_faction(self, team_idx: Literal[1, 2]):
        offer = self.get_accepted_offer()
        if not offer:
            return None
        
        map_details = offer.get_map_details()
        is_allies = (team_idx == 1) != self.flip_sides

        return map_details.allies if is_allies else map_details.axis

    def turn(self, *, opponent: bool = False):
        if self.is_choosing_advantage():
            if opponent:
                return 1 if self.flip_coin else 2
            else:
                return 2 if self.flip_coin else 1
        
        if ((len(self.offers) + int(bool(self.flip_advantage) != self.has_middleground())) % 2 == 0) != opponent:
            return 2
        else:
            return 1

    def is_user_participating(self, member: Member):
        if member.guild_permissions.administrator:
            return True

        if (
            discord.utils.get(member.roles, id=self.team1_id)
            or discord.utils.get(member.roles, id=self.team2_id)
        ):
            return True

        return False

    def is_users_turn(self, member: Member):
        if member.guild_permissions.administrator:
            return True

        team_id = self.team_idx_to_id(self.turn())
        return discord.utils.get(member.roles, id=team_id) is not None
    
    def gets_first_offer(self, team_idx: Literal[1, 2]):
        if self.has_middleground():
            i = 2 if self.flip_advantage else 1
        else:
            i = 1 if self.flip_advantage else 2
        return i == team_idx

    def get_offers_for_team_idx(self, team_idx: Literal[1, 2]):
        offset = int(not self.gets_first_offer(team_idx))
        return self.offers[offset::2]

    def get_max_num_offers_for_team_idx(self, team_idx: Literal[1, 2]):
        if self.gets_first_offer(team_idx):
            return (self.max_num_offers // 2) + (self.max_num_offers % 2)
        else:
            return (self.max_num_offers // 2)

    def has_middleground(self):
        return has_middleground(self.team1_id, self.team2_id)

    def is_choosing_advantage(self):
        return self.flip_advantage is None
    
    def can_accept_past_offers(self, team_idx: Literal[1, 2]):
        if self.has_middleground():
            return True
        
        if self.flip_advantage:
            return team_idx == 2
        else:
            return team_idx == 1

    def is_offer_available(self) -> bool:
        return bool(self.offers and self.offers[-1].accepted is None)

    def has_started(self) -> bool:
        if not self.start_time:
            return False
        
        return self.start_time <= datetime.now(tz=timezone.utc)

    def is_done(self) -> bool:
        return self.get_accepted_offer() is not None
    
    def get_accepted_offer(self) -> Offer | None:
        for offer in self.offers:
            if offer.accepted:
                return offer
        return None

    def create_offer(self, map: str, environment: str, layout: LayoutType):
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

    def skip_latest_offer(self):
        if self.is_done():
            raise GameStateError("Game is already done")
        if not self.is_offer_available():
            raise GameStateError("All offers have been answered already")

        self.offers[-1].accepted = False
        self.offers[-1].save()

    def remove_latest_offer(self):
        if not self.offers:
            raise Exception("Cannot remove offer because no offers have been made yet")
        
        offer = self.offers[-1]
        offer.delete()
        del self.offers[-1]

    def take_advantage(self):
        if not self.is_choosing_advantage():
            raise GameStateError("Advantage has already been chosen")
        
        self.flip_advantage = self.turn() == 2
        self.save()
    
    def give_advantage(self):
        if not self.is_choosing_advantage():
            raise GameStateError("Advantage has already been chosen")

        self.flip_advantage = self.turn() == 1
        self.save()

    def add_stream(self, caster: Caster, lang: str):
        return Stream.create(self, caster, lang)

    def remove_stream(self, stream: Stream):
        if stream.game_id != self.channel_id:
            raise ValueError("Stream is not part of this game")
        
        stream.delete()
        self.streams.remove(stream)

    def undo(self):
        if self.is_choosing_advantage():
            return False
        
        if not self.offers:
            self.flip_advantage = None
            self.save()
        
        elif self.is_done():
            offer = self.get_accepted_offer()
            assert offer is not None
            offer.accepted = None
            offer.save()
            self.flip_sides = None
            self.save()
        
        elif self.is_offer_available():
            self.remove_latest_offer()
        
        else:
            offer = self.offers[-1]
            offer.accepted = None
            offer.save()
        
        return True

@cached(TTLCache(maxsize=100, ttl=20))
def cached_get_streams_for_game(game_id: int):
    return Stream.load_for_game(game_id)

@cached(TTLCache(maxsize=100, ttl=20))
def cached_get_casters():
    return Caster.load_all()

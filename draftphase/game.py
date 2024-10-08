from typing import Optional
from pydantic import BaseModel, Field

from draftphase.db import get_cursor
from draftphase.discord_utils import GameStateError
from draftphase.maps import MAPS, LayoutType

MAX_OFFERS = 10

class Offer(BaseModel):
    id: int
    game_id: int
    offer_no: int
    player_id: int
    map: str
    environment: str
    layout: LayoutType
    accepted: Optional[bool]
    
    @classmethod
    def create(cls, game: 'Game', map: str, environment: str, layout: LayoutType):
        offer_no = len(game.offers) + 1
        player_id = game.player_idx_to_id(game.turn())

        if offer_no > game.max_num_offers:
            raise GameStateError("Offer exceeds max offer limit")

        with get_cursor() as cur:

            cur.execute(
                "INSERT INTO offers(game_id, offer_no, player_id, map, environment, layout) VALUES (?,?,?,?,?,?) RETURNING *",
                (game.id, offer_no, player_id, map, environment, "".join([str(i) for i in layout]))
            )
            data = cur.fetchone()

            self = cls(
                id=data[0],
                game_id=data[1],
                offer_no=data[2],
                player_id=data[3],
                map=data[4],
                environment=data[5],
                layout=tuple(data[6]),
                accepted=data[7],
            )
            game.offers.append(self)
            return self

    @classmethod
    def load_for_game(cls, game_id: int):
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
                    environment=data[5],
                    layout=tuple(data[6]),
                    accepted=data[7],
                ))
        return offers
    
    def save(self):
        data = self.model_dump()
        data["layout"] = "".join([str(i) for i in self.layout])

        with get_cursor() as cur:
            cur.execute(
                """
                UPDATE offers SET
                    game_id=:game_id,
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

class Game(BaseModel):
    id: int
    player1_id: int
    player2_id: int
    channel_id: int
    flip_sides: Optional[bool] = None
    max_num_offers: int = MAX_OFFERS
    offers: list[Offer] = Field(default_factory=list)

    @classmethod
    def create(cls, player1_id: int, player2_id: int, channel_id: int, max_num_offers: int = MAX_OFFERS):
        with get_cursor() as cur:
            cur.execute(
                "INSERT INTO games(player1_id, player2_id, channel_id, max_num_offers) VALUES (?,?,?,?) RETURNING *",
                (player1_id, player2_id, channel_id, max_num_offers)
            )
            data = cur.fetchone()

            return cls(
                id=data[0],
                player1_id=data[1],
                player2_id=data[2],
                channel_id=data[3],
                flip_sides=data[4],
                max_num_offers=data[5],
            )
    
    @classmethod
    def load(cls, game_id: int):
        with get_cursor() as cur:
            cur.execute("SELECT * FROM games WHERE id = ?", (game_id,))
            data = cur.fetchone()
            if not data:
                raise ValueError("No game exists with ID %s" % game_id)
            
            offers = Offer.load_for_game(int(data[0]))
            return cls(
                id=data[0],
                player1_id=data[1],
                player2_id=data[2],
                channel_id=data[3],
                flip_sides=data[4],
                max_num_offers=data[5],
                offers=offers,
            )

    def save(self):
        with get_cursor() as cur:
            cur.execute(
                """
                UPDATE games SET
                    player1_id=:player1_id,
                    player2_id=:player2_id,
                    channel_id=:channel_id,
                    flip_sides=:flip_sides,
                    max_num_offers=:max_num_offers
                WHERE id = :id
                """,
                self.model_dump()
            )

    def player_idx_to_id(self, player_idx: int):
        if player_idx == 1:
            return self.player1_id
        else:
            return self.player2_id
    
    def player_id_to_idx(self, player_id: int):
        if player_id == self.player1_id:
            return 1
        elif player_id == self.player2_id:
            return 2
        else:
            raise ValueError("Invalid player ID")
        
    def turn(self, *, opponent: bool = False):
        return 1 if (bool(len(self.offers) % 2) == opponent) else 2

    def get_offers_for_player_idx(self, player_idx: int):
        offset = (player_idx + 1) % 2
        return self.offers[offset::2]

    def get_max_num_offers_for_player_idx(self, player_idx: int):
        if (player_idx % 2 == 1):
            return (self.max_num_offers // 2) + (self.max_num_offers % 2)
        else:
            return (self.max_num_offers // 2)

    def is_done(self):
        return self.offers and self.offers[-1].accepted
    
    def is_offer_available(self):
        return self.offers and self.offers[-1].accepted is None

    def create_offer(self, map: str, environment: str, layout: LayoutType):
        if self.is_done():
            raise GameStateError("Game is already done")
        if self.is_offer_available():
            raise GameStateError("The previous offer is still open")
        
        return Offer.create(self, map=map, environment=environment, layout=layout)

    def accept_offer(self, flip_sides: bool):
        if self.is_done():
            raise GameStateError("Game is already done")
        if not self.is_offer_available():
            raise GameStateError("There is no offer available")

        offer = self.offers[-1]
        offer.accepted = True
        offer.save()

        self.flip_sides = flip_sides
        self.save()

    def decline_offer(self):
        if self.is_done():
            raise GameStateError("Game is already done")
        if not self.is_offer_available():
            raise GameStateError("There is no offer available")
        if len(self.offers) >= self.max_num_offers:
            raise GameStateError("The final offer cannot be declined")

        offer = self.offers[-1]
        offer.accepted = False
        offer.save()

from discord import SelectOption, ui, Interaction
import re

from draftphase.bot import DISCORD_BOT
from draftphase.discord_utils import CustomException, View, get_success_embed, handle_error_wrap
from draftphase.game import Game, Prediction

def assert_game_not_started(game: Game):
    if game.has_started():
        raise CustomException(
            "This game has already started!",
            "No more predictions can be casted."
        )

class CastPredictionSelect(
    ui.DynamicItem[ui.Select],
    template=r"predict:(?P<game_id>\d+)"
):
    def __init__(self, item: ui.Select, game_id: int) -> None:
        self.item = item
        self.game_id = game_id

        item.custom_id = f"predict:{self.game_id}"

        super().__init__(item)
        
    @classmethod
    async def from_custom_id(cls, interaction: Interaction, item: ui.Select, match: re.Match[str]):
        game_id = int(match.group("game_id"))
        return cls(item=item, game_id=game_id)
    
    @handle_error_wrap
    async def callback(self, interaction: Interaction):
        game = Game.load(self.game_id)
        try:
            assert_game_not_started(game)
        except:
            if interaction.message:
                await interaction.message.edit(view=None)
            raise
        
        team1_score = int(self.item.values[0])
        prediction, _ = Prediction.upsert(
            game_id=self.game_id,
            user_id=interaction.user.id,
            team1_score=team1_score,
        )

        winner_idx = prediction.winner_idx()
        winner = game.get_team(winner_idx)

        scores = prediction.get_scores()
        if winner_idx == 2:
            scores = (scores[1], scores[0])
        
        await interaction.response.send_message(embed=get_success_embed(
            "Prediction casted!",
            f"You predicted that **{winner.name}** will win with a **{scores[0]} - {scores[1]}** score."
        ), ephemeral=True)

        from draftphase.embeds import send_or_edit_game_message
        await send_or_edit_game_message(DISCORD_BOT, game)

class CastPredictionView(View):
    def __init__(self, game: Game):
        assert_game_not_started(game)

        super().__init__(timeout=None)

        team1 = game.get_team(1)
        team2 = game.get_team(2)

        offer = game.get_accepted_offer()
        assert offer is not None

        map_details = offer.get_map_details()
        team1_emoji = map_details.axis.emojis.default if game.flip_sides else map_details.allies.emojis.default
        team2_emoji = map_details.allies.emojis.default if game.flip_sides else map_details.axis.emojis.default

        self.add_item(CastPredictionSelect(
            ui.Select(
                placeholder="Predict your winner...",
                options=[
                    SelectOption(label=f"{team1.name} (5 - 0)", value="5", emoji=team1_emoji),
                    SelectOption(label=f"{team1.name} (4 - 1)", value="4", emoji=team1_emoji),
                    SelectOption(label=f"{team1.name} (3 - 2)", value="3", emoji=team1_emoji),
                    SelectOption(label=f"{team2.name} (3 - 2)", value="2", emoji=team2_emoji),
                    SelectOption(label=f"{team2.name} (4 - 1)", value="1", emoji=team2_emoji),
                    SelectOption(label=f"{team2.name} (5 - 0)", value="0", emoji=team2_emoji),
                ]
            ),
            game_id=game.channel_id
        ))
    
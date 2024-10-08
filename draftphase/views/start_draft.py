import re
from discord import Colour, Embed, Interaction, ui
from draftphase.bot import Bot
from draftphase.discord_utils import CustomException, View, handle_error_wrap
from draftphase.emojis import player_idx_to_color, player_idx_to_emoji
from draftphase.game import Game
from draftphase.maps import MAPS
from draftphase.views.create_offer import CreateOfferView

class StartDraftButton(
    ui.DynamicItem[ui.Button],
    template=r"start:(?P<game_id>\d+)"
):
    def __init__(self, item: ui.Button, game_id: int) -> None:
        self.game_id = int(game_id)
        item.custom_id = f"start:{game_id}"
        super().__init__(item)
    
    @classmethod
    async def from_custom_id(cls, interaction: Interaction[Bot], item: ui.Button, match: re.Match[str]):
        return cls(item, **match.groupdict()) # type: ignore
    
    @handle_error_wrap
    async def callback(self, interaction: Interaction[Bot]):
        game = Game.load(self.game_id)
        if interaction.user.id != game.player_idx_to_id(game.turn()):
            raise CustomException("It's not your turn!")

        view = CreateOfferView(game)
        embed = view.get_embed(game)
        await interaction.response.edit_message(view=view, embed=embed)

class StartDraftView(View):
    def __init__(self, game: Game):
        super().__init__(timeout=None)
        self.add_item(
            StartDraftButton(
                ui.Button(
                    label=f"Player {game.turn()}: Create offer..."
                ),
                game.id,
            )
        )

    def get_embed(self, game: Game):
        embed = Embed()
        player_idx = game.turn()
        embed.title = f"{player_idx_to_emoji(player_idx)} Player {player_idx}'s turn to draft an offer!"
        embed.color = player_idx_to_color(player_idx)

        for player_idx in (1, 2):
            offers = game.get_offers_for_player_idx(player_idx)
            used_maps = {offer.map for offer in offers}

            embed.add_field(
                name=f"Player {player_idx} {player_idx_to_emoji(player_idx)} ({len(offers)}/{game.get_max_num_offers_for_player_idx(player_idx)})",
                value="\n".join([
                    f"~~{m}~~" if m in used_maps else f"**{m}**"
                    for m in MAPS
                ]),
                inline=True
            )

        return embed

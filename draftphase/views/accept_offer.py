import re
from discord import ButtonStyle, Embed, Interaction, ui
from discord.abc import Messageable
from draftphase.bot import Bot
from draftphase.discord_utils import CustomException, View, handle_error_wrap
from draftphase.emojis import layout_to_emoji, player_idx_to_emoji
from draftphase.game import Game
from draftphase.maps import MAPS

class AcceptOfferButton(
    ui.DynamicItem[ui.Button],
    template=r"accept:(?P<game_id>\d+):(?P<flip_sides>0|1)"
):
    def __init__(self, item: ui.Button, game_id: int, flip_sides: bool) -> None:
        self.game_id = int(game_id)
        self.flip_sides = bool(flip_sides)
        item.custom_id = f"accept:{game_id}:{int(flip_sides)}"
        super().__init__(item)
    
    @classmethod
    async def from_custom_id(cls, interaction: Interaction[Bot], item: ui.Button, match: re.Match[str]):
        return cls(item, **match.groupdict()) # type: ignore
    
    @handle_error_wrap
    async def callback(self, interaction: Interaction[Bot]):
        game = Game.load(self.game_id)
        player_idx = game.turn()
        if interaction.user.id != game.player_idx_to_id(player_idx):
            raise CustomException("It's not your turn!")
        
        game.accept_offer(self.flip_sides)
        offer = game.offers[-1]

        map_details = offer.get_map_details()
        objectives = map_details.get_objectives(offer.layout)

        embed = Embed(title=f"{player_idx_to_emoji(player_idx)} Player {player_idx} **accepted** the offer!")
        embed.add_field(name="Map", value=f"{offer.map} ({offer.environment})", inline=True)
        embed.add_field(name="Allies", value=f"Player {2 if self.flip_sides else 1}", inline=True)
        embed.add_field(name="Axis", value=f"Player {1 if self.flip_sides else 2}", inline=True)
        embed.add_field(name="Layout", value=f"{layout_to_emoji(offer.layout, map_details.orientation)} `"+"` - `".join(objectives) + "`", inline=True)

        await interaction.response.edit_message(content=None, view=None, embed=embed)

class DeclineOfferButton(
    ui.DynamicItem[ui.Button],
    template=r"decline:(?P<game_id>\d+)"
):
    def __init__(self, item: ui.Button, game_id: int) -> None:
        self.game_id = int(game_id)
        item.custom_id = f"decline:{game_id}"
        super().__init__(item)
    
    @classmethod
    async def from_custom_id(cls, interaction: Interaction[Bot], item: ui.Button, match: re.Match[str]):
        return cls(item, **match.groupdict()) # type: ignore
    
    @handle_error_wrap
    async def callback(self, interaction: Interaction[Bot]):
        game = Game.load(self.game_id)
        player_idx = game.turn()
        if interaction.user.id != game.player_idx_to_id(player_idx):
            raise CustomException("It's not your turn!")

        game.decline_offer()

        embed = Embed(title=f"{player_idx_to_emoji(player_idx)} Player {player_idx} **declined** the offer!")
        await interaction.response.edit_message(content=None, view=None, embed=embed)

        from draftphase.views.start_draft import StartDraftView
        view = StartDraftView(game)
        embed = view.get_embed(game)

        assert isinstance(interaction.channel, Messageable)
        await interaction.channel.send(view=view, embed=embed)

class AcceptOfferView(View):
    def __init__(self, game: Game):
        super().__init__(timeout=None)
        offer = game.offers[-1]
        map = offer.get_map_details()
        self.add_item(
            DeclineOfferButton(
                ui.Button(
                    label=f"Decline offer",
                    style=ButtonStyle.red,
                ),
                game.id,
            )
        )
        self.add_item(
            AcceptOfferButton(
                ui.Button(
                    label=f"Take {map.allies.value}",
                    style=ButtonStyle.blurple,
                ),
                game.id,
                flip_sides=(game.turn() == 2),
            )
        )
        self.add_item(
            AcceptOfferButton(
                ui.Button(
                    label=f"Take {map.axis.value}",
                    style=ButtonStyle.blurple,
                ),
                game.id,
                flip_sides=(game.turn() == 1)
            )
        )

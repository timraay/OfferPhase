import re
from discord import ButtonStyle, Embed, Interaction, SelectOption, ui
from draftphase.bot import Bot
from draftphase.discord_utils import CustomException, View, handle_error_wrap
from draftphase.emojis import environment_to_emoji, layout_to_emoji, player_idx_to_color, player_idx_to_emoji
from draftphase.game import Game
from draftphase.maps import MAPS, get_all_layout_combinations, get_layout_from_filtered_idx
from draftphase.views.accept_offer import AcceptOfferView

class CreateOfferSelect(
    ui.DynamicItem[ui.Select],
    template=r"offer:(?P<game_id>\d+)(?::(?P<map_idx>\d+))?(?::(?P<environment_idx>\d+))?(?::(?P<midpoint_idx>\d+))?"
):
    def __init__(self,
            item: ui.Select,
            game_id: int,
            map_idx: int | None = None,
            environment_idx: int | None = None,
            midpoint_idx: int | None = None,
    ) -> None:
        self.game_id = int(game_id)

        self.map_idx = int(map_idx) if map_idx is not None else None
        self.environment_idx = int(environment_idx) if environment_idx is not None else None
        self.midpoint_idx = int(midpoint_idx) if midpoint_idx is not None else None

        self._args: list[int | None] = []
        for idx in (self.map_idx, self.environment_idx, self.midpoint_idx):
            if idx is None:
                break
            self._args.append(idx)

        item.custom_id = f"offer:{game_id}"
        for idx in self._args:
            item.custom_id += f":{idx}"

        super().__init__(item)
    
    @classmethod
    async def from_custom_id(cls, interaction: Interaction[Bot], item: ui.Select, match: re.Match[str]):
        return cls(item, **match.groupdict()) # type: ignore
    
    @handle_error_wrap
    async def callback(self, interaction: Interaction[Bot]):
        game = Game.load(self.game_id)
        if interaction.user.id != game.player_idx_to_id(game.turn()):
            raise CustomException("It's not your turn!")

        idx = int(self.item.values[0])
        view = CreateOfferView(game, *self._args, idx) # type: ignore
        embed = view.get_embed(game)
        await interaction.response.edit_message(embed=embed, view=view)

class CreateOfferConfirmButton(
    ui.DynamicItem[ui.Button],
    template=r"confirmoffer:(?P<game_id>\d+):(?P<map_idx>\d+):(?P<environment_idx>\d+):(?P<midpoint_idx>\d+):(?P<layout_idx>\d+)"
):
    def __init__(self,
            item: ui.Button,
            game_id: int,
            map_idx: int,
            environment_idx: int,
            midpoint_idx: int,
            layout_idx: int,
    ) -> None:
        self.game_id = int(game_id)
        self.map_idx = int(map_idx)
        self.environment_idx = int(environment_idx)
        self.midpoint_idx = int(midpoint_idx)
        self.layout_idx = int(layout_idx)

        item.custom_id = f"confirmoffer:{game_id}:{map_idx}:{environment_idx}:{midpoint_idx}:{layout_idx}"

        super().__init__(item)

    @classmethod
    async def from_custom_id(cls, interaction: Interaction[Bot], item: ui.Select, match: re.Match[str]):
        return cls(item, **match.groupdict()) # type: ignore

    @handle_error_wrap
    async def callback(self, interaction: Interaction[Bot]):
        game = Game.load(self.game_id)
        if interaction.user.id != game.player_idx_to_id(game.turn()):
            raise CustomException("It's not your turn!")
        
        map_name, map = list(MAPS.items())[self.map_idx]
        environment = map.environments[self.environment_idx]
        layout = get_layout_from_filtered_idx(self.midpoint_idx, self.layout_idx)
        
        game.create_offer(map_name, environment, layout)

        player_idx = game.turn()

        assert interaction.message is not None
        await interaction.message.edit(view=None)
        await interaction.response.send_message(
            content=f"<@{game.player_idx_to_id(player_idx)}> {player_idx_to_emoji(player_idx)} do you accept the offer?",
            view=AcceptOfferView(game),
        )

class CreateOfferView(View):
    def __init__(self,
            game: Game,
            map_idx: int | None = None,
            environment_idx: int | None = None,
            midpoint_idx: int | None = None,
            layout_idx: int | None = None,
    ):
        super().__init__(timeout=None)

        self.map_idx = map_idx or 0
        self.environment_idx = environment_idx or 0
        self.midpoint_idx = midpoint_idx or 0
        self.layout_idx = layout_idx or 0

        self.map_name = None
        self.map = None
        self.environment = None
        self.midpoint = None
        self.layout = None

        if map_idx is not None:
            self.map_name, self.map = list(MAPS.items())[map_idx]
            self.environment = self.map.environments[self.environment_idx]

            if midpoint_idx is not None:
                self.midpoint = self.map.objectives[2][midpoint_idx]
            
                if layout_idx is not None:
                    self.layout = get_layout_from_filtered_idx(midpoint_idx, layout_idx)

        offers = game.get_offers_for_player_idx(game.turn())
        used_maps = {offer.map for offer in offers}
        
        self.add_item(
            CreateOfferSelect(
                ui.Select(
                    placeholder="Map...",
                    options=[
                        SelectOption(
                            label=m, value=str(i),
                            default=(m == self.map_name),
                            emoji="🗺️",
                        )
                        for i, m in enumerate(MAPS.keys())
                        if m not in used_maps
                    ],
                ),
                game.id
            )
        )
        self.add_item(
            CreateOfferSelect(
                ui.Select(
                    placeholder="Environment...",
                    options=[
                        SelectOption(
                            label=e, value=str(i),
                            default=(self.environment_idx == i),
                            emoji=environment_to_emoji(e)
                        )
                        for i, e in enumerate(self.map.environments)
                    ] if self.map else [SelectOption(label="Day", value="0")],
                    disabled=(self.map is None),
                ),
                game.id, self.map_idx
            )
        )
        self.add_item(
            CreateOfferSelect(
                ui.Select(
                    placeholder="Midpoint...",
                    options=[
                        SelectOption(
                            label=m, value=str(i),
                            default=(self.midpoint == m),
                            emoji="🧭"
                        )
                        for i, m in enumerate(self.map.objectives[2])
                    ] if self.map else [SelectOption(label="Unknown", value="0")],
                    disabled=(self.map is None),
                ),
                game.id, self.map_idx, self.environment_idx
            )
        )
        self.add_item(
            CreateOfferSelect(
                ui.Select(
                    placeholder="Layout...",
                    options=[
                        SelectOption(
                            label=", ".join(o)[:100], value=str(i),
                            default=(layout_idx is not None and layout_idx == i),
                            emoji=layout_to_emoji(l, self.map.orientation)
                        )
                        for i, (l, o) in enumerate(
                            (layout, self.map.get_objectives(layout))
                            for layout in get_all_layout_combinations(self.midpoint_idx)
                        )
                    ] if (self.map and self.midpoint) else [SelectOption(label="Unknown", value="0")],
                    disabled=(self.midpoint is None),
                ),
                game.id, self.map_idx, self.environment_idx, self.midpoint_idx
            )
        )
        if layout_idx is not None:
            self.add_item(
                CreateOfferConfirmButton(
                    ui.Button(
                        label="Confirm",
                        style=ButtonStyle.green,
                    ),
                    game_id=game.id,
                    map_idx=self.map_idx,
                    environment_idx=self.environment_idx,
                    midpoint_idx=self.midpoint_idx,
                    layout_idx=self.layout_idx,
                )
            )

    def get_embed(self, game: Game):
        embed = Embed()
        player_idx = game.turn()
        offers = game.get_offers_for_player_idx(player_idx)
        embed.title = f"{player_idx_to_emoji(player_idx)} Player {player_idx} is making an offer ({len(offers) + 1}/{game.get_max_num_offers_for_player_idx(player_idx)})"
        embed.color = player_idx_to_color(player_idx)

        if self.map_name:
            embed.add_field(name="Map", value=self.map_name, inline=True)
        if self.environment:
            embed.add_field(name="Environment", value=self.environment.value, inline=True)
        
        if self.map:
            if self.layout:
                objectives = self.map.get_objectives(self.layout)
                embed.add_field(name="Layout", value=f"{layout_to_emoji(self.layout, self.map.orientation)} `"+"` - `".join(objectives) + "`", inline=False)
            elif self.midpoint:
                embed.add_field(name="Midpoint", value=f"`{self.midpoint}`", inline=True)

        return embed


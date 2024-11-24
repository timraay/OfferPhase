import asyncio
from re import Match
from typing import Literal
from discord import ButtonStyle, Interaction, NotFound, SelectOption, ui, InteractionMessage, Member
from draftphase.discord_utils import GameStateError, MessagePayload, View, handle_error_wrap
from draftphase.emojis import Emojis, environment_to_emoji, layout_to_emoji
from draftphase.game import Game
from draftphase.maps import MAPS, get_all_layout_combinations, get_layout_from_filtered_idx
from draftphase.utils import SingletonMeta, safe_create_task


class ControlsManager(metaclass=SingletonMeta):
    def __init__(self) -> None:
        self.controls: dict[int, dict[int, 'ControlsView']] = {}

    async def add_view(self, view: 'ControlsView'):
        if (old_view := self.get_view(view.game, view.member)):
            await self.delete_view(old_view)

        self.controls[view.game.channel_id][view.member.id] = view

    async def delete_view(self, view: 'ControlsView'):
        controls = self.controls.get(view.game.channel_id)
        if controls:
            self.controls.pop(view.member.id, None)
            
        if view.message:
            try:
                await view.message.delete()
            except:
                pass

    def get_view(self, game: Game, member: Member) -> 'ControlsView':
        return self.controls[game.channel_id][member.id]

    async def update_for_game(self, game: Game):
        controls = self.controls[game.channel_id]
        tasks: list[asyncio.Task] = []
        for member_id, control in list(controls.items()):
            control.game = game
            control.reset()

            def __remove_when_not_found(task: asyncio.Task):
                if task.cancelled():
                    return
                if isinstance(task.exception(), NotFound):
                    controls.pop(member_id, None)

            task = asyncio.create_task(control.edit())
            task.add_done_callback(__remove_when_not_found)
            tasks.append(task)

        await asyncio.gather(*tasks)
    
    async def delete_for_game(self, game: Game):
        controls = self.controls.pop(game.channel_id, None)
        if not controls:
            return

        await asyncio.gather(*[
            control.message.delete()
            for control in controls.values()
            if control.message
        ], return_exceptions=True)
    
class GetControlsButton(ui.DynamicItem[ui.Button], template=r"ctrl:(?P<game_id>\d+)"):
    def __init__(self, item: ui.Button, game_id: int):
        self.item = item
        self.game_id = game_id

        self.item.custom_id = f"ctrl:{self.game_id}"
        super().__init__(item)

    @classmethod
    async def from_custom_id(cls, interaction: Interaction, item: ui.Button, match: Match[str]):
        game_id = int(match.group("game_id"))
        return cls(item=item, game_id=game_id)
    
    @handle_error_wrap
    async def callback(self, interaction: Interaction):
        member = interaction.user
        assert isinstance(member, Member)

        game = Game.load(self.game_id)
        view = ControlsView(game, member)
        await view.send(interaction)

class SelectOfferSelect(ui.DynamicItem[ui.Select], template=r"ctrl:(?P<game_id>\d+):selectoffer"):
    def __init__(self, item: ui.Select, game_id: int):
        self.item = item
        self.game_id = game_id

        self.item.custom_id = f"ctrl:{self.game_id}:selectoffer"
        super().__init__(item)

    @classmethod
    async def from_custom_id(cls, interaction: Interaction, item: ui.Select, match: Match[str]):
        return cls(
            item=item,
            game_id=int(match.group("game_id")),
        )
    
    @handle_error_wrap
    async def callback(self, interaction: Interaction):
        member = interaction.user
        assert isinstance(member, Member)

        game = Game.load(self.game_id)

        view = ControlsManager().get_view(game, member)
        view.reset()
        view.offer_idx = int(self.item.values[0])

        await view.edit(interaction=interaction)

class AcceptOfferButton(ui.DynamicItem[ui.Button], template=r"ctrl:(?P<game_id>\d+):accept:(?P<offer_idx>\d+):(?P<faction_idx>[1-2])(?P<confirm>!)?"):
    def __init__(self, item: ui.Button, game_id: int, offer_idx: int, faction_idx: Literal[1, 2], confirmed: bool = False):
        self.item = item
        self.game_id = game_id
        self.offer_idx = offer_idx
        self.faction_idx: Literal[1, 2] = faction_idx
        self.confirmed = confirmed

        self.item.custom_id = f"ctrl:{self.game_id}:accept:{self.offer_idx}:{self.faction_idx}"
        if self.confirmed:
            self.item.custom_id += "!"

        super().__init__(item)

    @classmethod
    async def from_custom_id(cls, interaction: Interaction, item: ui.Button, match: Match[str]):
        return cls(
            item=item,
            game_id=int(match.group("game_id")),
            offer_idx=int(match.group("offer_idx")),
            faction_idx=int(match.group("faction_idx")), # type: ignore
            confirmed=bool(match.group("confirm")),
        )
    
    @handle_error_wrap
    async def callback(self, interaction: Interaction):
        member = interaction.user
        assert isinstance(member, Member)

        game = Game.load(self.game_id)

        if not game.is_users_turn(member):
            raise GameStateError("It is not your turn")
        if not game.is_offer_available():
            raise GameStateError("The offer has already been rejected")

        cm = ControlsManager()
        view = cm.get_view(game, member)
        view.set_accepted(self.offer_idx, self.faction_idx)

        if self.confirmed:
            turn = game.turn()
            flip_sides = (turn != self.faction_idx)
            game.accept_offer(flip_sides=flip_sides)
            safe_create_task(
                cm.update_for_game(game)
            )

        await view.edit(interaction=interaction)

class DeclineOfferButton(ui.DynamicItem[ui.Button], template=r"ctrl:(?P<game_id>\d+):decline:(?P<offer_idx>\d+)(?P<confirm>!)?"):
    def __init__(self, item: ui.Button, game_id: int, offer_idx: int, confirmed: bool = False):
        self.item = item
        self.game_id = game_id
        self.offer_idx = offer_idx
        self.confirmed = confirmed

        self.item.custom_id = f"ctrl:{self.game_id}:decline:{self.offer_idx}"
        if self.confirmed:
            self.item.custom_id += "!"

        super().__init__(item)
    
    @classmethod
    async def from_custom_id(cls, interaction: Interaction, item: ui.Button, match: Match[str]):
        return cls(
            item=item,
            game_id=int(match.group("game_id")),
            offer_idx=int(match.group("offer_idx")),
            confirmed=bool(match.group("confirm")),
        )
    
    @handle_error_wrap
    async def callback(self, interaction: Interaction):
        member = interaction.user
        assert isinstance(member, Member)

        game = Game.load(self.game_id)

        if not game.is_users_turn(member):
            raise GameStateError("It is not your turn")
        if not game.is_offer_available():
            raise GameStateError("The offer has already been rejected")

        cm = ControlsManager()
        view = cm.get_view(game, member)
        view.set_declined(self.offer_idx)

        if self.confirmed:
            game.decline_offer()
            safe_create_task(
                cm.update_for_game(game)
            )

        await view.edit(interaction=interaction)

class CreateOfferSelect(
    ui.DynamicItem[ui.Select],
    template=r"ctrl:(?P<game_id>\d+):offer(?::(?P<map_idx>\d+))?(?::(?P<environment_idx>\d+))?(?::(?P<midpoint_idx>\d+))?"
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

        item.custom_id = f"ctrl:{game_id}:offer"
        for idx in self._args:
            item.custom_id += f":{idx}"

        super().__init__(item)
    
    @classmethod
    async def from_custom_id(cls, interaction: Interaction, item: ui.Select, match: Match[str]):
        return cls(item, **match.groupdict()) # type: ignore
    
    @handle_error_wrap
    async def callback(self, interaction: Interaction):
        member = interaction.user
        assert isinstance(member, Member)

        game = Game.load(self.game_id)
        view = ControlsManager().get_view(game, member)

        idx = int(self.item.values[0])
        view.set_offer(*self._args, idx) # type: ignore

        await view.edit(interaction=interaction)

class CreateOfferConfirmButton(
    ui.DynamicItem[ui.Button],
    template=r"ctrl:(?P<game_id>\d+):offer:(?P<map_idx>\d+):(?P<environment_idx>\d+):(?P<midpoint_idx>\d+):(?P<layout_idx>\d+)!"
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

        item.custom_id = f"ctrl:{game_id}:offer:{map_idx}:{environment_idx}:{midpoint_idx}:{layout_idx}!"
        super().__init__(item)
    
    @classmethod
    async def from_custom_id(cls, interaction: Interaction, item: ui.Select, match: Match[str]):
        confirmed = bool(match.group("confirm"))
        return cls(item, **match.groupdict(), confirmed=confirmed) # type: ignore
    
    @handle_error_wrap
    async def callback(self, interaction: Interaction):
        member = interaction.user
        assert isinstance(member, Member)

        game = Game.load(self.game_id)
        cm = ControlsManager()
        view = cm.get_view(game, member)

        map_name, map_details = list(MAPS.items())[self.map_idx]
        environment = map_details.environments[self.environment_idx]
        layout = get_layout_from_filtered_idx(self.midpoint_idx, self.layout_idx)

        game.create_offer(
            map=map_name,
            environment=environment,
            layout=layout,
        )
        safe_create_task(
            cm.update_for_game(game)
        )

        await view.edit(interaction=interaction)


class ControlsView(View):
    def __init__(self, game: Game, member: Member):
        self.game = game
        self.member = member
        
        self.message: InteractionMessage | None = None
        self.reset()

    def reset(self):
        self.offer_idx: int = len(self.game.offers) - 1
        self.accepted: bool | None = None
        self.faction_idx: Literal[1, 2] | None = None

        self.map_idx = 0
        self.environment_idx = 0
        self.midpoint_idx = 0
        self.layout_idx = 0

        self.map_name = None
        self.map = None
        self.environment = None
        self.midpoint = None
        self.layout = None

    def set_offer(
        self,
        map_idx: int | None = None,
        environment_idx: int | None = None,
        midpoint_idx: int | None = None,
        layout_idx: int | None = None,
    ):
        self.reset()

        self.map_idx = map_idx or 0
        self.environment_idx = environment_idx or 0
        self.midpoint_idx = midpoint_idx or 0
        self.layout_idx = layout_idx or 0

        if map_idx is not None:
            self.map_name, self.map = list(MAPS.items())[map_idx]
            self.environment = self.map.environments[self.environment_idx]

            if midpoint_idx is not None:
                self.midpoint = self.map.objectives[2][midpoint_idx]
            
                if layout_idx is not None:
                    self.layout = get_layout_from_filtered_idx(midpoint_idx, layout_idx)

    def set_accepted(self, offer_idx: int, faction_idx: Literal[1, 2]):
        self.reset()
        assert 0 <= offer_idx < len(self.game.offers)
        self.offer_idx = offer_idx
        self.accepted = True
        self.faction_idx = faction_idx

    def set_declined(self, offer_idx: int):
        self.reset()
        assert 0 <= offer_idx < len(self.game.offers)
        self.offer_idx = offer_idx
        self.accepted = False
        self.faction_idx = None
    
    def _get_payload_offer_available(self) -> MessagePayload:
        turn = self.game.turn()
        offer_options = []
        for offer in self.game.get_offers_for_team_idx(turn):
            map_details = offer.get_map_details()
            objectives = map_details.get_objectives(offer.layout)
            offer_option = SelectOption(
                label=f"{offer.map} - {objectives[1]} ({offer.environment.value})",
                value=str(self.game.offers.index(offer)),
                emoji=layout_to_emoji(offer.layout, map_details.orientation),
            )
            offer_options.append(offer_option)

        self.add_item(
            SelectOfferSelect(ui.Select(
                placeholder="Offer",
                options=offer_options,
                row=1,
            ), self.game.channel_id)
        )

        self.add_item(
            AcceptOfferButton(ui.Button(
                label="Accept",
                emoji=Emojis.faction_us,
                disabled=self.accepted is not None,
                style=ButtonStyle.green if self.faction_idx == 1 else ButtonStyle.gray,
                row=2,
            ), self.game.channel_id, self.offer_idx, faction_idx=1)
        )
        self.add_item(
            AcceptOfferButton(ui.Button(
                label="Accept",
                emoji=Emojis.faction_ger,
                disabled=self.accepted is not None,
                style=ButtonStyle.green if self.faction_idx == 2 else ButtonStyle.gray,
                row=2,
            ), self.game.channel_id, self.offer_idx, faction_idx=2)
        )
        self.add_item(
            DeclineOfferButton(ui.Button(
                label="Skip",
                disabled=self.accepted is not None,
                style=ButtonStyle.green if self.faction_idx is None else ButtonStyle.gray,
                row=2,
            ), self.game.channel_id, self.offer_idx)
        )

        confirm_button = ui.Button(
            label="Confirm",
            style=ButtonStyle.blurple,
            row=3,
        )
        if self.accepted is True:
            assert self.faction_idx is not None
            self.add_item(AcceptOfferButton(confirm_button, self.game.channel_id, self.offer_idx, self.faction_idx, confirmed=True))
            content = f"Are you sure you want to play **{self.game.offers[-1].map} {'Allies' if self.faction_idx == 1 else 'Axis'}**?"
        elif self.accepted is False:
            self.add_item(DeclineOfferButton(confirm_button, self.game.channel_id, self.offer_idx, confirmed=True))
            content = f"Are you sure you want to skip this offer? You can always accept it at a later turn."
        else:
            confirm_button.disabled = True
            self.add_item(confirm_button)
            content = (
                "**Choose whether you accept any of the available offers.**"
                "\nIf you **accept** an offer, you get to choose which side to play as."
                "\nIf you **skip**, you have to make an offer in return."
            )

        return {
            "content": content,
            "embeds": []
        }

    def _get_payload_draft_offer(self) -> MessagePayload:
        offers = self.game.get_offers_for_team_idx(self.game.turn())
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
                self.game.channel_id
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
                self.game.channel_id, self.map_idx
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
                self.game.channel_id, self.map_idx, self.environment_idx
            )
        )
        self.add_item(
            CreateOfferSelect(
                ui.Select(
                    placeholder="Layout...",
                    options=[
                        SelectOption(
                            label=", ".join(o)[:100], value=str(i),
                            default=(self.layout is not None and self.layout_idx == i),
                            emoji=layout_to_emoji(l, self.map.orientation)
                        )
                        for i, (l, o) in enumerate(
                            (layout, self.map.get_objectives(layout))
                            for layout in get_all_layout_combinations(self.midpoint_idx)
                        )
                    ] if (self.map and self.midpoint) else [SelectOption(label="Unknown", value="0")],
                    disabled=(self.midpoint is None),
                ),
                self.game.channel_id, self.map_idx, self.environment_idx, self.midpoint_idx
            )
        )

        self.add_item(
            CreateOfferConfirmButton(
                ui.Button(
                    label="Confirm",
                    style=ButtonStyle.blurple,
                    disabled=self.layout is None,
                ),
                game_id=self.game.channel_id,
                map_idx=self.map_idx,
                environment_idx=self.environment_idx,
                midpoint_idx=self.midpoint_idx,
                layout_idx=self.layout_idx,
            )
        )

        return {
            "content": "Make an offer.",
            "embeds": []
        }

    def get_payload(self) -> MessagePayload:
        self.clear_items()

        if not self.game.is_users_turn(self.member):
            return {
                "content": "*Waiting for opponent...*",
                "embeds": []
            }
        
        if self.game.is_offer_available():
            return self._get_payload_offer_available()
        else:
            return self._get_payload_draft_offer()
    
    async def send(self, interaction: Interaction):
        payload = self.get_payload()
        await interaction.response.send_message(**payload, ephemeral=True)
        self.message = await interaction.original_response()
        await ControlsManager().add_view(self)

    async def edit(self, *, interaction: Interaction | None = None):
        if not self.message:
            raise Exception("Unknown message")

        payload = self.get_payload()
        if interaction:
            await interaction.response.edit_message(**payload)
        else:
            await self.message.edit(**payload)

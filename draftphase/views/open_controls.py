import asyncio
import random
from re import Match
from typing import Literal, Sequence
from discord import AllowedMentions, ButtonStyle, Embed, File, Interaction, NotFound, SelectOption, TextChannel, ui, InteractionMessage, Member
from draftphase.bot import DISCORD_BOT
from draftphase.discord_utils import CustomException, GameStateError, MessagePayload, View, handle_error_wrap
from draftphase.embeds import get_single_offer_embed
from draftphase.emojis import faction_to_emoji, layout_to_emoji
from draftphase.game import Game
from draftphase.maps import MAPS, get_all_layout_combinations, get_layout_from_filtered_idx
from draftphase.utils import SingletonMeta, safe_create_task

def assert_is_users_turn(game: Game, member: Member):
    if not game.is_users_turn(member):
        raise CustomException(
            "It is not your turn!"
        )

async def send_in_thread(game: Game, content: str):
    channel = DISCORD_BOT.get_channel(game.channel_id)
    if not channel:
        channel = await DISCORD_BOT.fetch_channel(game.channel_id)
    
    assert isinstance(channel, TextChannel)
    assert DISCORD_BOT.user is not None
    for thread in channel.threads:
        if thread.owner_id == DISCORD_BOT.user.id:
            break
    else:
        return
    
    await thread.send(
        embed=Embed(color=0xFFFFFF, description=content),
        allowed_mentions=AllowedMentions(roles=False),
    )

def safe_send_in_thread(game: Game, content: str):
    safe_create_task(
        send_in_thread(game, content),
        err_msg="Failed to send message to game thread"
    )

class ControlsManager(metaclass=SingletonMeta):
    def __init__(self) -> None:
        self.controls: dict[int, dict[int, 'ControlsView']] = {}

    async def add_view(self, view: 'ControlsView'):
        if (old_view := self.get_view(view.game, view.member)):
            await self.delete_view(old_view)

        self.controls.setdefault(view.game.channel_id, {})[view.member.id] = view

    async def delete_view(self, view: 'ControlsView'):
        controls = self.controls.get(view.game.channel_id)
        if controls:
            self.controls.pop(view.member.id, None)
            
        if view.message:
            try:
                await view.message.delete()
            except:
                pass

    def get_view(self, game: Game, member: Member) -> 'ControlsView | None':
        views = self.controls.get(game.channel_id)
        if not views:
            return
        return views.get(member.id)
    
    def safe_get_view(self, game: Game, member: Member) -> 'ControlsView':
        view = self.get_view(game, member)
        if not view:
            raise CustomException(
                "Something went wrong",
                "Please dismiss this message and try again",
                inplace=True,
            )
        return view

    async def update_for_game(self, game: Game):
        controls = self.controls.get(game.channel_id, {})

        from draftphase.embeds import send_or_edit_game_message
        await send_or_edit_game_message(DISCORD_BOT, game)

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
    
    async def delete_for_game(self, game: Game):
        controls = self.controls.pop(game.channel_id, None)

        from draftphase.embeds import send_or_edit_game_message
        await send_or_edit_game_message(DISCORD_BOT, game)

        if controls:
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
        if not game.is_user_participating(member):
            await interaction.response.send_message(
                content=random.choice([
                    "https://tenor.com/view/nuhuh-zazacat-zaza-cat-nuh-uh-gif-5895922515261135563",
                    "https://tenor.com/view/byuntear-meme-reaction-emoji-nops-gif-11371827892803687671",
                    "https://tenor.com/view/not-today-batman-today-not-gif-3191943350122519312",
                    "https://tenor.com/view/no-kanye-west-all-falls-down-song-nope-stop-right-there-gif-20589089",
                    "https://tenor.com/view/you-shall-not-pass-lotr-do-not-enter-not-allowed-scream-gif-16729885",
                    "https://tenor.com/view/no-way-kim-dao-nope-not-allowed-refused-gif-17877789",
                ]),
                ephemeral=True
            )

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
        if not game.can_accept_past_offers(game.turn()):
            raise CustomException(
                "Your opponent has Offer Advantage!",
                "You cannot select any offers made previously."
            )

        view = ControlsManager().safe_get_view(game, member)
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
        assert_is_users_turn(game, member)

        if not game.is_offer_available():
            raise GameStateError("The offer has already been rejected")

        cm = ControlsManager()
        view = cm.safe_get_view(game, member)
        view.set_accepted(self.offer_idx, self.faction_idx)

        if self.confirmed:
            turn = game.turn()
            opponent = game.turn(opponent=True)
            offer = game.offers[self.offer_idx]
            flip_sides = (turn != self.faction_idx)
            game.accept_offer(offer, flip_sides=flip_sides)
            await interaction.response.defer()
            await cm.delete_for_game(game)

            map_details = offer.get_map_details()
            faction = game.get_team_faction(turn)
            faction_opponent = game.get_team_faction(opponent)
            assert faction is not None
            assert faction_opponent is not None
            safe_send_in_thread(game, (
                f"<@&{game.get_team(turn).public_role_id}> accepted **{map_details.name} - {map_details.get_objectives(offer.layout)[1]}**"
                f" ({offer.get_environment().name}) and will be playing as **{faction.name}** {faction.emojis.default}"
                f"\n-# <@&{game.get_team(opponent).public_role_id}> will be playing as **{faction_opponent.name}** {faction_opponent.emojis.default}"
            ))
        else:
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
        assert_is_users_turn(game, member)

        if not game.is_offer_available():
            raise GameStateError("The offer has already been skipped")
        if len(game.offers) >= game.max_num_offers:
            raise GameStateError("The final offer cannot be skipped")

        cm = ControlsManager()
        view = cm.safe_get_view(game, member)
        view.set_declined(self.offer_idx)

        if self.confirmed:
            turn = game.turn()
            game.skip_latest_offer()
            await cm.update_for_game(game)
            await interaction.response.defer()

            safe_send_in_thread(game, f"<@&{game.get_team(turn).public_role_id}> skipped the offer")
        else:
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
        view = ControlsManager().safe_get_view(game, member)

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
        return cls(item, **match.groupdict()) # type: ignore
    
    @handle_error_wrap
    async def callback(self, interaction: Interaction):
        member = interaction.user
        assert isinstance(member, Member)

        game = Game.load(self.game_id)
        assert_is_users_turn(game, member)

        cm = ControlsManager()
        view = cm.safe_get_view(game, member)

        map_name, map_details = list(MAPS.items())[self.map_idx]
        environment = map_details.environments[self.environment_idx]
        layout = get_layout_from_filtered_idx(self.midpoint_idx, self.layout_idx)

        turn = game.turn()
        offer = game.create_offer(
            map=map_name,
            environment=environment.key,
            layout=layout,
        )
        await cm.update_for_game(game)
        await interaction.response.defer()

        safe_send_in_thread(game, (
            f"<@&{game.get_team(turn).public_role_id}> offered **{map_details.name} - {map_details.get_objectives(offer.layout)[1]}**"
            f" ({offer.get_environment().name})"
        ))

class TakeAdvantageButton(ui.DynamicItem[ui.Button], template=r"ctrl:(?P<game_id>\d+):takeadvantage"):
    def __init__(self,
        item: ui.Button,
        game_id: int,
    ) -> None:
        self.game_id = int(game_id)

        item.custom_id = f"ctrl:{game_id}:takeadvantage"
        super().__init__(item)
    
    @classmethod
    async def from_custom_id(cls, interaction: Interaction, item: ui.Select, match: Match[str]):
        return cls(item, **match.groupdict()) # type: ignore
    
    @handle_error_wrap
    async def callback(self, interaction: Interaction):
        member = interaction.user
        assert isinstance(member, Member)

        game = Game.load(self.game_id)
        assert_is_users_turn(game, member)

        cm = ControlsManager()
        view = cm.safe_get_view(game, member)

        turn = game.turn()
        opponent = game.turn(opponent=True)
        game.take_advantage()
        view.reset()
        await cm.update_for_game(game)
        await interaction.response.defer()

        team_mention = f"<@&{game.get_team(turn).public_role_id}>"
        opponent_mention = f"<@&{game.get_team(opponent).public_role_id}>"
        if game.has_middleground():
            safe_send_in_thread(game, (
                f"{team_mention} chose to make the **first offer**."
                f"\n-# {opponent_mention} can offer afterwards."
            ))
        else:
            safe_send_in_thread(game, (
                f"{team_mention} took **Offer Advantage**: {opponent_mention} can no longer accept previous offers."
                f"\n-# {opponent_mention} receives **Server Advantage**: Server location will favor their team."
            ))

class GiveAdvantageButton(ui.DynamicItem[ui.Button], template=r"ctrl:(?P<game_id>\d+):giveadvantage"):
    def __init__(self,
        item: ui.Button,
        game_id: int,
    ) -> None:
        self.game_id = int(game_id)

        item.custom_id = f"ctrl:{game_id}:giveadvantage"
        super().__init__(item)
    
    @classmethod
    async def from_custom_id(cls, interaction: Interaction, item: ui.Select, match: Match[str]):
        return cls(item, **match.groupdict()) # type: ignore
    
    @handle_error_wrap
    async def callback(self, interaction: Interaction):
        member = interaction.user
        assert isinstance(member, Member)

        game = Game.load(self.game_id)
        assert_is_users_turn(game, member)

        cm = ControlsManager()
        view = cm.safe_get_view(game, member)

        turn = game.turn()
        opponent = game.turn(opponent=True)
        game.give_advantage()
        view.reset()
        await cm.update_for_game(game)
        await interaction.response.defer()

        team_mention = f"<@&{game.get_team(turn).public_role_id}>"
        opponent_mention = f"<@&{game.get_team(opponent).public_role_id}>"
        if game.has_middleground():
            safe_send_in_thread(game, (
                f"{team_mention} lets {opponent_mention} make the **first offer**."
                f"\n-# They themselves will offer second."
            ))
        else:
            safe_send_in_thread(game, (
                f"{team_mention} took **Server Advantage**: Server location will favor their team."
                f"\n-# {opponent_mention} receives **Server Advantage**: {opponent_mention} can no longer accept previous offers."
            ))


class ControlsView(View):
    def __init__(self, game: Game, member: Member):
        super().__init__(timeout=None)

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
    
    async def _get_payload_offer_available(self) -> tuple[MessagePayload, Sequence[File]]:
        offer_options = []
        can_accept_past_offers = self.game.can_accept_past_offers(self.game.turn())
        is_final_offer = len(self.game.offers) >= self.game.max_num_offers
        offers = self.game.get_offers_for_team_idx(self.game.turn(opponent=True))
        for offer in offers:
            map_details = offer.get_map_details()
            environment = offer.get_environment()
            objectives = map_details.get_objectives(offer.layout)
            offer_option = SelectOption(
                label=f"{map_details.name} - {objectives[1]} ({environment.name})",
                value=str(self.game.offers.index(offer)),
                emoji=layout_to_emoji(offer.layout, map_details.orientation),
                default=offer.offer_no == self.offer_idx + 1
            )
            offer_options.append(offer_option)

        self.add_item(
            SelectOfferSelect(ui.Select(
                placeholder="Offer",
                options=offer_options,
                row=1,
                disabled=not can_accept_past_offers,
            ), self.game.channel_id)
        )

        disable_accept_allies = self.accepted is True and self.faction_idx == 1
        disable_accept_axis = self.accepted is True and self.faction_idx == 2
        disable_skip = self.accepted is False

        selected_offer = self.game.offers[self.offer_idx]
        map_details = selected_offer.get_map_details()

        self.add_item(
            AcceptOfferButton(ui.Button(
                label=f"Play as {map_details.allies.name}",
                emoji=faction_to_emoji(map_details.allies, selected=disable_accept_allies),
                disabled=disable_accept_allies,
                style=ButtonStyle.green if disable_accept_allies else ButtonStyle.gray,
                row=2,
            ), self.game.channel_id, self.offer_idx, faction_idx=1)
        )
        self.add_item(
            AcceptOfferButton(ui.Button(
                label=f"Play as {map_details.axis.name}",
                emoji=faction_to_emoji(map_details.axis, selected=disable_accept_axis),
                disabled=disable_accept_axis,
                style=ButtonStyle.green if disable_accept_axis else ButtonStyle.gray,
                row=2,
            ), self.game.channel_id, self.offer_idx, faction_idx=2)
        )

        self.add_item(
            DeclineOfferButton(ui.Button(
                label="Skip",
                disabled=disable_skip or is_final_offer,
                style=ButtonStyle.green if disable_skip else ButtonStyle.gray,
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
            content = f"Are you sure you want to play **{map_details.name} {'Allies' if self.faction_idx == 1 else 'Axis'}**?"
        elif self.accepted is False:
            self.add_item(DeclineOfferButton(confirm_button, self.game.channel_id, self.offer_idx, confirmed=True))
            if can_accept_past_offers:
                content = f"Are you sure you want to skip this offer?\nYou can still accept it during a later turn."
            else:
                content = f"Are you sure you want to skip this offer?\nSince your opponent has **Offer Advantage**, you will not be able to accept it during a later turn."
        else:
            confirm_button.disabled = True
            self.add_item(confirm_button)
            content = (
                (
                    "**Choose whether you accept any of the available offers.**"
                    if can_accept_past_offers else
                    "**Choose whether you accept the available offer.**"
                ) +
                "\nIf you **accept** an offer, you get to choose which side to play as."
                "\nIf you **skip**, you have to make an offer in return."
            )

        embed, file = await get_single_offer_embed(
            map_details=map_details,
            environment=selected_offer.get_environment(),
            midpoint_idx=selected_offer.layout[1],
            layout=selected_offer.layout,
            selected_team_id=1 if disable_accept_allies else 2 if disable_accept_axis else None
        )

        return (
            {
                "content": content,
                "embeds": [embed],
                "view": self,
            },
            [file]
        )

    async def _get_payload_draft_offer(self) -> tuple[MessagePayload, Sequence[File]]:
        offers = self.game.get_offers_for_team_idx(self.game.turn())
        used_maps = {offer.map for offer in offers}
        
        self.add_item(
            CreateOfferSelect(
                ui.Select(
                    placeholder="Map...",
                    options=[
                        SelectOption(
                            label=m.name, value=str(i),
                            default=(m.key == self.map_name),
                            emoji="🗺️",
                        )
                        for i, m in enumerate(MAPS.values())
                        if m.key not in used_maps
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
                            label=e.name, value=str(i),
                            default=(self.environment_idx == i),
                            emoji=e.emoji
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

        embed, file = await get_single_offer_embed(
            map_details=self.map,
            environment=self.environment,
            midpoint_idx=self.midpoint_idx if self.midpoint else None,
            layout=self.layout,
        )

        return (
            {
                "content": "Make an offer.",
                "embeds": [embed],
                "view": self,
            },
            [file]
        )

    def _get_payload_choose_advantage(self) -> MessagePayload:
        if self.game.has_middleground():
            self.add_item(TakeAdvantageButton(ui.Button(
                style=ButtonStyle.blurple,
                label="Create first offer",
            ), self.game.channel_id))
            self.add_item(GiveAdvantageButton(ui.Button(
                style=ButtonStyle.blurple,
                label="Let opponent offer first",
            ), self.game.channel_id))
        else:
            self.add_item(TakeAdvantageButton(ui.Button(
                style=ButtonStyle.blurple,
                label="Take Offer Advantage",
            ), self.game.channel_id))
            self.add_item(GiveAdvantageButton(ui.Button(
                style=ButtonStyle.blurple,
                label="Take Server Advantage",
            ), self.game.channel_id))
        
        return {
            "content": "Select which of the two options you want to claim for your team.\nThe remaining option is handed to your opponent.",
            "embeds": [],
            "view": self
        }

    async def get_payload(self) -> tuple[MessagePayload, Sequence[File]]:
        self.clear_items()

        if self.game.is_done():
            return (
                { "content": "*A map has been selected. You can dismiss this message.*" },
                []
            )

        if not self.game.is_users_turn(self.member):
            return (
                { "content": "*Waiting for opponent...*" },
                []
            )
        
        if self.game.is_choosing_advantage():
            return self._get_payload_choose_advantage(), []
        elif self.game.is_offer_available():
            return await self._get_payload_offer_available()
        else:
            return await self._get_payload_draft_offer()
    
    async def send(self, interaction: Interaction):
        payload, files = await self.get_payload()
        await interaction.response.send_message(**payload, files=files, ephemeral=True)
        self.message = await interaction.original_response()
        await ControlsManager().add_view(self)

    async def edit(self, *, interaction: Interaction | None = None):
        if not self.message:
            raise Exception("Unknown message")

        payload, files = await self.get_payload()
        payload.setdefault("view", None) # type: ignore
        if interaction:
            await interaction.response.edit_message(**payload, attachments=files)
        else:
            await self.message.edit(**payload, attachments=files)

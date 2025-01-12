from datetime import datetime, timezone
import itertools
from typing import Literal
from discord import Client, ui, Colour, Embed, File, TextChannel
import discord
from discord.utils import format_dt

from draftphase.discord_utils import MessagePayload, View
from draftphase.game import Game
from draftphase.images import get_single_offer_image, offers_to_image
from draftphase.maps import Environment, LayoutType, MapDetails

FILE_COUNTER = itertools.count()

def get_file_name(name: str):
    timestamp = int(datetime.now(timezone.utc).timestamp())
    count = next(FILE_COUNTER)
    fn = f"{name}_{timestamp}_{count}.png"
    return fn

async def get_game_embeds(client: Client, game: Game) -> tuple[MessagePayload, list[File]]:
    payload: MessagePayload = {}
    embeds: list[Embed] = []
    files: list[File] = []

    channel = client.get_channel(game.channel_id)
    if not channel:
        raise ValueError("Channel not found")
    assert isinstance(channel, TextChannel)

    team1 = game.get_team(1)
    team2 = game.get_team(2)
    team1_role = channel.guild.get_role(team1.public_role_id)
    team2_role = channel.guild.get_role(team2.public_role_id)

    if team1_role:
        team1_name = team1_role.name
        team1_mention = team1_role.mention
    else:
        team1_name = "Unknown"
        team1_mention = "Unknown"

    if team2_role:
        team2_name = team2_role.name
        team2_mention = team2_role.mention
    else:
        team2_name = "Unknown"
        team2_mention = "Unknown"

    if game.is_done():
        map_details = game.offers[-1].get_map_details()
    else:
        map_details = None

    embed = Embed(title=f"{team1_name} vs {team2_name}")
    embed.add_field(
        name="Allies" if game.is_done() else "Team 1",
        value=(f"{map_details.allies.emojis.default} " if map_details else "") + (team2_mention if game.flip_sides else team1_mention),
        inline=True,
    )
    embed.add_field(
        name="Score",
        value="-",
        inline=True,
    )
    embed.add_field(
        name="Axis" if game.is_done() else "Team 2",
        value=(f"{map_details.axis.emojis.default} " if map_details else "") + (team1_mention if game.flip_sides else team2_mention),
        inline=True,
    )

    if game.start_time:
        embed.add_field(
            name="_ _\nStart time",
            value=f"{format_dt(game.start_time, 'F')} ({format_dt(game.start_time, 'R')})",
            inline=True,
        )
    
    if game.streams:
        embed.add_field(
            name=f"Streamers (+{game.stream_delay} mins delay)" if game.stream_delay else "Streamers",
            value="\n".join(
                [streamer.to_text() for streamer in game.streams]
            ),
            inline=True,
        )

    if game.subtitle:
        embed.set_author(name=game.subtitle)
    
    embeds.append(embed)

    team_idx: Literal[1, 2]
    for team_idx, team_name in ((1, team1_name), (2, team2_name)): # type: ignore
        offers = game.get_offers_for_team_idx(team_idx)
        max_num_offers = game.get_max_num_offers_for_team_idx(team_idx)

        im = await offers_to_image(
            offers,
            max_num_offers=max_num_offers,
            grayscaled=(not game.is_done() and team_idx != game.turn(opponent=game.is_offer_available())),
            flip_sides=game.flip_sides or False,
        )
        fn = get_file_name(f"team{team_idx}_offers")
        file = File(im, filename=fn)

        embed = Embed(description=f"Maps offered by **{team_name}** ({len(offers)}/{max_num_offers})")
        embed.set_image(url=f"attachment://{fn}")
        assert embed.description is not None

        if not game.is_done() and team_idx == game.turn():
            embed.color = Colour(0xffffff)
        
        won_coinflip = game.flip_coin == (team_idx == 2)
        if won_coinflip:
            embed.description += " 🪙"
        
        if not game.is_choosing_advantage():
            has_advantage = game.flip_advantage == (team_idx == 2)
            if game.has_middleground():
                if won_coinflip:
                    embed.description += f"\n-# **First offer:** You get to make the first offer"
                else:
                    embed.description += f"\n-# **First offer:** Your opponent let you offer first"
            
            else:
                if has_advantage:
                    embed.description += f"\n-# **Offer advantage:** Opponent can only accept most recent offer"
                else:
                    embed.description += f"\n-# **Server advantage:** Server will be in a preferred location"
                    embed.description += f"\n-# **First offer:** You get to make the first offer"

        embeds.append(embed)
        files.append(file)
    
    team_name = team1_name if game.turn() == 1 else team2_name
    if game.is_choosing_advantage():
        embed = Embed(color=Colour(0xffffff))
        if game.has_middleground():
            embed.add_field(
                name=f"{team_name} won the coinflip!",
                value=f"They get to choose between either of the below two options:\n\n> -# **First offer**\n> You offer first.\n\n> -# **Final offer**\n> Your opponent offers first.",
            )
        else:
            embed.add_field(
                name=f"{team_name} won the coinflip!",
                value=f"They get to choose between either of the below two options:\n\n> -# **Offer advantage**\n> Your opponent cannot accept past offers.\n\n> -# **Server advantage**\n> Your team gets the preferred server location. You offer first.",
            )

        embeds.append(embed)
    elif game.is_done():
        offer = game.get_accepted_offer()
        assert offer is not None
        embed, file = await get_single_offer_embed(
            map_details=offer.get_map_details(),
            environment=offer.get_environment(),
            midpoint_idx=offer.layout[1],
            layout=offer.layout,
            comment=f"Accepted by {team_name}"
        )
        embeds.append(embed)
        files.append(file)
    elif game.is_offer_available():
        offer = game.offers[-1]
        embed, file = await get_single_offer_embed(
            map_details=offer.get_map_details(),
            environment=offer.get_environment(),
            midpoint_idx=offer.layout[1],
            layout=offer.layout,
            comment=f"Offered to {team_name}"
        )
        embeds.append(embed)
        files.append(file)
    else:
        embed, file = await get_single_offer_embed(
            comment=f"{team_name} is offering..."
        )
        embeds.append(embed)
        files.append(file)

    if not game.is_done():
        from draftphase.views.open_controls import GetControlsButton
        view = View(timeout=None)
        view.add_item(GetControlsButton(
            ui.Button(label="Open Team Rep Controls"),
            game_id=game.channel_id
        ))
        payload["view"] = view

    else:
        votes = [0, 0]
        for prediction in game.get_predictions():
            votes[prediction.winner_idx() - 1] += 1

        embed = discord.Embed()
        embed.set_author(name="Match predictions")
        embed.description = f"{team1.emoji} {team1_mention} (**{votes[0]}** votes)\n{team2.emoji} {team2_mention} (**{votes[1]}** votes)"
        embeds.append(embed)

        if not game.has_started():
            from draftphase.views.cast_prediction import CastPredictionView
            view = CastPredictionView(game)
            payload["view"] = view

    payload["embeds"] = embeds
    return payload, files

async def get_single_offer_embed(
    map_details: MapDetails | None = None,
    environment: Environment | None = None,
    midpoint_idx: int | None = None,
    layout: LayoutType | None = None,
    comment: str | None = None,
    selected_team_id: Literal[1, 2] | None = None,
):
    if not map_details:
        im = await get_single_offer_image()
    else:
        im = await get_single_offer_image(
            details=map_details,
            layout=layout,
            environment=environment,
            selected_team_id=selected_team_id,
        )

    if map_details:
        map_name = map_details.name
    else:
        map_name = "-"

    if environment:
        environment_name = environment.name
    else:
        environment_name = "-"
    
    if midpoint_idx is not None and map_details:
        midpoint_name = map_details.objectives[2][midpoint_idx]
    else:
        midpoint_name = "-"
    

    embed = Embed(color=Colour(0xffffff))
    embed.add_field(
        name=comment or "​",
        value=f"-# **Map**\n{map_name}",
    )
    embed.add_field(
        name="​",
        value=f"-# **Environment**\n{environment_name}",
    )
    embed.add_field(
        name="​",
        value=f"-# **Midpoint**\n{midpoint_name}",
    )

    fn = get_file_name("offer")
    file = File(im, filename=fn)
    embed.set_thumbnail(url=f"attachment://{fn}")
    
    return embed, file


async def create_game(client: Client, channel: TextChannel, team1_id: int, team2_id: int, subtitle: str | None = None):
    game = Game.create(
        channel=channel,
        team1_id=team1_id,
        team2_id=team2_id,
        subtitle=subtitle,
    )

    await send_or_edit_game_message(client, game)

    return game

async def send_or_edit_game_message(client: Client, game: Game):
    channel = client.get_channel(game.channel_id)
    if not isinstance(channel, TextChannel):
        raise ValueError("Channel not found")

    payload, files = await get_game_embeds(client, game)
        
    message = None
    if game.message_id:
        try:
            message = await channel.fetch_message(game.message_id)
        except discord.NotFound:
            pass
        
    if message:
        payload.setdefault("view", None) # type: ignore
        await message.edit(**payload, attachments=files)
    else:
        message = await channel.send(**payload, files=files)
        game.message_id = message.id
        game.save()

    return message

from discord import Client, ui, Colour, Embed, File, TextChannel
import discord
from discord.utils import format_dt

from draftphase.discord_utils import MessagePayload, View
from draftphase.game import Game
from draftphase.images import get_single_offer_image, offers_to_image
from draftphase.maps import MAPS, Environment, LayoutType, MapDetails
from draftphase.views.open_controls import GetControlsButton


async def get_game_embeds(client: Client, game: Game) -> tuple[MessagePayload, list[File]]:
    embeds: list[Embed] = []
    files: list[File] = []

    channel = client.get_channel(game.channel_id)
    if not channel:
        raise ValueError("Channel not found")
    assert isinstance(channel, TextChannel)

    team1 = channel.guild.get_role(game.team1_id)
    team2 = channel.guild.get_role(game.team2_id)

    if team1:
        team1_name = team1.name
        team1_mention = team1.mention
    else:
        team1_name = "Unknown"
        team1_mention = "Unknown"

    if team2:
        team2_name = team2.name
        team2_mention = team2.mention
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

    for team_idx, team_name in ((1, team1_name), (2, team2_name)):
        offers = game.get_offers_for_team_idx(team_idx)
        max_num_offers = game.get_max_num_offers_for_team_idx(team_idx)

        im = await offers_to_image(
            offers,
            max_num_offers=max_num_offers,
            grayscaled=(not game.is_done() and team_idx != game.turn(opponent=game.is_offer_available())),
            flip_sides=game.flip_sides or False,
        )
        fn = f"team{team_idx}_offers.png"
        file = File(im, filename=fn)

        embed = Embed(description=f"Maps offered by **{team_name}** ({len(offers)}/{max_num_offers})")
        embed.set_image(url=f"attachment://{fn}")

        if not game.is_done() and team_idx == game.turn():
            embed.color = Colour(0xffffff)

        embeds.append(embed)
        files.append(file)
    
    if game.is_done():
        offer = game.get_accepted_offer()
        assert offer is not None
        embed, file = await get_single_offer_embed(
            map_details=offer.get_map_details(),
            environment=offer.get_environment(),
            midpoint_idx=offer.layout[1],
            layout=offer.layout,
            comment=f"Accepted by {team1_name if game.turn() == 1 else team2_name}"
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
            comment=f"Offered to {team1_name if game.turn() == 1 else team2_name}"
        )
        embeds.append(embed)
        files.append(file)
    else:
        embed, file = await get_single_offer_embed(
            comment=f"{team1_name if game.turn() == 1 else team2_name} is offering..."
        )
        embeds.append(embed)
        files.append(file)

    payload: MessagePayload = {
        "embeds": embeds,
    }

    if not game.is_done():
        view = View(timeout=None)
        view.add_item(GetControlsButton(
            ui.Button(label="Open Team Rep Controls"),
            game_id=game.channel_id
        ))
        payload["view"] = view

    return payload, files

async def get_single_offer_embed(
    map_details: MapDetails | None = None,
    environment: Environment | None = None,
    midpoint_idx: int | None = None,
    layout: LayoutType | None = None,
    comment: str | None = None,
):
    if not map_details:
        im = await get_single_offer_image()
    else:
        im = await get_single_offer_image(
            details=map_details,
            layout=layout,
            environment=environment,
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

    fn = f"offer.png"
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

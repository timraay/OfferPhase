from discord import Colour, Embed, File, Interaction, TextChannel
from discord.utils import format_dt

from draftphase.game import Game
from draftphase.images import get_single_offer_image, offers_to_image
from draftphase.maps import MAPS, Environment, LayoutType


async def get_game_embeds(interaction: Interaction, game: Game):
    embeds: list[Embed] = []
    files: list[File] = []

    channel = interaction.client.get_channel(game.channel_id)
    if not channel:
        raise ValueError("Channel not found")
    assert isinstance(channel, TextChannel)

    team1 = channel.guild.get_role(game.team2_id if game.flip_sides else game.team1_id)
    team2 = channel.guild.get_role(game.team1_id if game.flip_sides else game.team2_id)

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

    embed = Embed(title=f"{team1_name} vs {team2_name}")
    embed.add_field(
        name="Allies" if game.is_done() else "Team 1",
        value=team1_mention,
        inline=True,
    )
    embed.add_field(
        name="Score",
        value="-",
        inline=True,
    )
    embed.add_field(
        name="Axis" if game.is_done() else "Team 2",
        value=team2_mention,
        inline=True,
    )

    if game.start_time:
        embed.add_field(
            name="_ _\nStart time",
            value=f"{format_dt(game.start_time, 'F')} ({format_dt(game.start_time, 'R')})",
            inline=True,
        )
    
    if game.streamers:
        embed.add_field(
            name=f"Streamers (+{game.stream_delay} mins delay)" if game.stream_delay else "Streamers",
            value="\n".join(
                [streamer.to_text() for streamer in game.streamers]
            ),
            inline=True,
        )

    if game.subtitle:
        embed.set_author(name=game.subtitle)
    
    embeds.append(embed)

    for team_idx in (1, 2):
        offers = game.get_offers_for_team_idx(team_idx)
        max_num_offers = game.get_max_num_offers_for_team_idx(team_idx)

        im = await offers_to_image(offers)
        fn = f"team{team_idx}_offers.png"
        file = File(im, filename=fn)

        embed = Embed(description=f"Maps available to **{team1_name}** ({len(offers)}/{max_num_offers})")
        embed.set_image(url=f"attachment://{fn}")

        if team_idx == game.turn(opponent=game.is_offer_available()):
            embed.color = Colour(0xffffff)

        embeds.append(embed)
        files.append(file)
    
    if game.offers:
        offer = game.offers[-1]
        embed, file = await get_single_offer_embed(
            map_name=offer.map,
            environment=offer.environment,
            midpoint_idx=offer.layout[1],
            layout=offer.layout,
        )
        embeds.append(embed)
        files.append(file)

    return embeds, files

async def get_single_offer_embed(
    map_name: str | None = None,
    environment: Environment | None = None,
    midpoint_idx: int | None = None,
    layout: LayoutType | None = None,
):
    if not map_name:
        map_details = None
        im = await get_single_offer_image()
    else:
        map_details = MAPS[map_name]
        im = await get_single_offer_image(
            details=map_details,
            layout=layout,
            environment=environment,
        )

    if environment:
        environment_name = environment.value
    else:
        environment_name = "-"
    
    if midpoint_idx is not None and map_details:
        midpoint_name = map_details.objectives[2][midpoint_idx]
    else:
        midpoint_name = "-"
    

    embed = Embed(color=Colour(0xffffff))
    embed.add_field(
        name="​",
        value=f"-# **Map**\n{map_name or '-'}",
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
    embed.set_image(url=f"attachment://{fn}")
    
    return embed, file


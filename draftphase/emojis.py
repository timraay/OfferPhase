from enum import Enum
from typing import Literal

from discord import Colour

from draftphase.maps import Environment, Faction, LayoutType, Orientation

TEAM1_COLOR = Colour(0x1a4483)
TEAM2_COLOR = Colour(0xad2020)

class Emojis(str, Enum):
    team1_silhouette = "<:team1_silhouette:1293256533597098105>"
    team2_silhouette = "<:team2_silhouette:1293256539741884540>"
    obj_vert_222 = "<:obj_vert_222:1293256527498576037>"
    obj_vert_221 = "<:obj_vert_221:1293256520485572692>"
    obj_vert_212 = "<:obj_vert_212:1293256514492043284>"
    obj_vert_211 = "<:obj_vert_211:1293256507781152851>"
    obj_vert_210 = "<:obj_vert_210:1293256500931854527>"
    obj_vert_122 = "<:obj_vert_122:1293256493852000362>"
    obj_vert_121 = "<:obj_vert_121:1293256487304433685>"
    obj_vert_112 = "<:obj_vert_112:1293256480916504597>"
    obj_vert_111 = "<:obj_vert_111:1293256475002671115>"
    obj_vert_110 = "<:obj_vert_110:1293256468086390846>"
    obj_vert_101 = "<:obj_vert_101:1293256461178245160>"
    obj_vert_100 = "<:obj_vert_100:1293256454089998478>"
    obj_vert_012 = "<:obj_vert_012:1293256447911792831>"
    obj_vert_011 = "<:obj_vert_011:1293256441523867678>"
    obj_vert_010 = "<:obj_vert_010:1293256434401935423>"
    obj_vert_001 = "<:obj_vert_001:1293256429280690217>"
    obj_vert_000 = "<:obj_vert_000:1293256422313951323>"
    obj_hor_222 = "<:obj_hor_222:1293256415552733327>"
    obj_hor_221 = "<:obj_hor_221:1293256409206755339>"
    obj_hor_212 = "<:obj_hor_212:1293256402776887380>"
    obj_hor_211 = "<:obj_hor_211:1293256396439289937>"
    obj_hor_210 = "<:obj_hor_210:1293256389812031488>"
    obj_hor_122 = "<:obj_hor_122:1293256382992089201>"
    obj_hor_121 = "<:obj_hor_121:1293256375987732520>"
    obj_hor_112 = "<:obj_hor_112:1293256369545285686>"
    obj_hor_111 = "<:obj_hor_111:1293256361479635127>"
    obj_hor_110 = "<:obj_hor_110:1293256355666464830>"
    obj_hor_101 = "<:obj_hor_101:1293256349689450586>"
    obj_hor_100 = "<:obj_hor_100:1293256343301656667>"
    obj_hor_012 = "<:obj_hor_012:1293256337622568970>"
    obj_hor_011 = "<:obj_hor_011:1293256331247226994>"
    obj_hor_010 = "<:obj_hor_010:1293256325220012072>"
    obj_hor_001 = "<:obj_hor_001:1293256318345412640>"
    obj_hor_000 = "<:obj_hor_000:1293256308878868531>"
    environment_day = "☀️"
    environment_overcast = "☁️"
    environment_night = "🌙"
    environment_dawn = "🌤️"
    environment_dusk = "🌥️"
    faction_us = "<faction_us:1310943564859179008>"
    faction_us_selected = "<faction_us_selected:1310943572899663872>"
    faction_sov = "<faction_sov:1310943547456880691>"
    faction_sov_selected = "<faction_sov_selected:1310943557091201134>"
    faction_ger = "<faction_ger:1310943529169584139>"
    faction_ger_selected = "<faction_ger_selected:1310943536752889897>"
    faction_cw = "<faction_cw:1310943514452037682>"
    faction_cw_selected = "<faction_cw_selected:1310943522370621483>"

def get_emoji(name: str):
    emoji = Emojis._member_map_.get(name)
    if emoji:
        return emoji.value

def layout_to_emoji(layout: LayoutType, orientation: Orientation):
    orientation_str = "hor" if orientation == Orientation.HORIZONTAL else "vert"
    layout_str = "".join([str(i) for i in layout])
    key = f"obj_{orientation_str}_{layout_str}"
    return get_emoji(key)

def environment_to_emoji(environment: Environment):
    key = f"environment_{environment.value.lower()}"
    return get_emoji(key)

def faction_to_emoji(faction: Faction, selected: bool = False):
    key = f"faction_{faction.name.lower()}"
    if selected:
        key += "_selected"
    return get_emoji(key)

def player_idx_to_emoji(player_idx: Literal[1, 2]):
    if player_idx == 1:
        return Emojis.team1_silhouette.value
    elif player_idx == 2:
        return Emojis.team2_silhouette.value

def player_idx_to_color(player_idx: Literal[1, 2]):
    if player_idx == 1:
        return TEAM1_COLOR
    elif player_idx == 2:
        return TEAM2_COLOR

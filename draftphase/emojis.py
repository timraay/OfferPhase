from draftphase.config import Orientation, get_config
from draftphase.maps import Faction, LayoutType

def get_emoji(name: str):
    config = get_config()
    return config.bot.emojis.get(name)

def layout_to_emoji(layout: LayoutType, orientation: Orientation):
    orientation_str = "hor" if orientation == Orientation.HORIZONTAL else "vert"
    layout_str = "".join([str(i) for i in layout])
    key = f"obj_{orientation_str}_{layout_str}"
    return get_emoji(key)

def faction_to_emoji(faction: Faction, selected: bool = False):
    if selected:
        return faction.emojis.selected
    else:
        return faction.emojis.default

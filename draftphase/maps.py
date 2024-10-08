from enum import Enum
import itertools
from typing import Any, Generator, TypeAlias

from pydantic import BaseModel

LayoutType: TypeAlias = tuple[int, int, int]
ObjectiveRow: TypeAlias = tuple[str, str, str]

class Faction(str, Enum):
    US = "US"
    GER = "GER"
    SOV = "SOV"
    CW = "CW"

class Environment(str, Enum):
    DAY = "Day"
    OVERCAST = "Overcast"
    NIGHT = "Night"
    DAWN = "Dawn"
    DUSK = "Dusk"

class Orientation(Enum):
    HORIZONTAL = 0
    VERTICAL = 1

class MapDetails(BaseModel):
    environments: tuple[Environment, ...]
    objectives: tuple[ObjectiveRow, ObjectiveRow, ObjectiveRow, ObjectiveRow, ObjectiveRow]
    orientation: Orientation
    allies: Faction
    axis: Faction

    def get_objectives(self, layout: LayoutType):
        return [row[i] for i, row in zip(layout, self.objectives[1:4])]

MAPS = {
    "Carentan": MapDetails(
        environments=(
            Environment.DAY,
            Environment.NIGHT,
        ),
        objectives=(
            ("Blactot", "502nd Start", "Farm Ruins"),
            ("Pumping Station", "Ruins", "Derailed Train"),
            ("Canal Crossing", "Town Center", "Train Station"),
            ("Customs", "Rail Crossing", "Mount Halais"),
            ("Canal Locks", "Rail Causeway", "La Maison Des Ormes"),
        ),
        orientation=Orientation.HORIZONTAL,
        allies=Faction.US,
        axis=Faction.GER,
    ),

    "Driel": MapDetails(
        environments=(
            Environment.DAWN,
            Environment.NIGHT,
        ),
        objectives=(
            ("Oosterbeek Approach", "Roseander Polder", "Kasteel Rosande"),
            ("Boatyard", "Bridgeway", "Rijn Banks"),
            ("Brick Factory", "Railway Bridge", "Gun Emplacements"),
            ("Rietveld", "South Railway", "Middel Road"),
            ("Orchards", "Schaduwwolken Farm", "Fields"),
        ),
        orientation=Orientation.VERTICAL,
        allies=Faction.CW,
        axis=Faction.GER,
    ),

    "El Alamein": MapDetails(
        environments=(
            Environment.DAY,
            Environment.DUSK,
        ),
        objectives=(
            ("Vehicle Depot", "Artillery Guns", "Miteiriya Ridge"),
            ("Hamlet Ruins", "El Mreir", "Watchtower"),
            ("Desert Rat Trenches", "Oasis", "Valley"),
            ("Fuel Depot", "Airfield Command", "Airfield Hangars"),
            ("Cliffside Village", "Ambushed Convoy", "Quarry"),
        ),
        orientation=Orientation.VERTICAL,
        allies=Faction.CW,
        axis=Faction.GER,
    ),

    "Foy": MapDetails(
        environments=(
            Environment.DAY,
            Environment.NIGHT,
        ),
        objectives=(
            ("Road To Recogne", "Cobru Approach", "Road To Noville"),
            ("Cobru Factory", "Foy", "Flak Battery"),
            ("West Bend", "Southern Edge", "Dugout Barn"),
            ("N30 Highway", "Bizory Foy Road", "Eastern Ourthe"),
            ("Road To Bastogne", "Bois Jacques", "Forest Outskirts"),
        ),
        orientation=Orientation.HORIZONTAL,
        allies=Faction.US,
        axis=Faction.GER,
    ),

    "Hill 400": MapDetails(
        environments=(
            Environment.DAY,
            # Environment.NIGHT,
        ),
        objectives=(
            ("Convoy Ambush", "Federchecke Junction", "Stuckchen Farm"),
            ("Roer River House", "Bergstein Church", "Kirchweg"),
            ("Flak Pits", "Hill 400", "Southern Approach"),
            ("Eselsweg Junction", "Eastern Slope", "Trainwreck"),
            ("Roer River Crossing", "Zerkall", "PaperMill"),
        ),
        orientation=Orientation.HORIZONTAL,
        allies=Faction.US,
        axis=Faction.GER,
    ),

    "Hurtgen Forest": MapDetails(
        environments=(
            Environment.DAY,
            Environment.NIGHT,
        ),
        objectives=(
            ("The Masbauch Approach", "Reserve Station", "Lumber Yard"),
            ("Wehebach Overlook", "Kall Trail", "The Ruin"),
            ("North Pass", "The Scar", "The Siegfried Line"),
            ("Hill 15", "Jacob's Barn", "Salient 42"),
            ("Grosshau Approach", "Hürtgen Approach", "Logging Camp"),
        ),
        orientation=Orientation.HORIZONTAL,
        allies=Faction.US,
        axis=Faction.GER,
    ),

    "Kharkov": MapDetails(
        environments=(
            Environment.DAY,
            Environment.NIGHT,
        ),
        objectives=(
            ("Marsh Town", "Soviet Vantage Point", "German Fuel Dump"),
            ("Bitter Spring", "Lumber Works", "Windmill Hillside"),
            ("Water Mill", "St Mary", "Distillery"),
            ("River Crossing", "Belgorod Outskirts", "Lumberyard"),
            ("Wehrmacht Overlook", "Hay Storage", "Overpass"),
        ),
        orientation=Orientation.VERTICAL,
        allies=Faction.SOV,
        axis=Faction.GER,
    ),

    "Kursk": MapDetails(
        environments=(
            Environment.DAY,
            Environment.NIGHT,
        ),
        objectives=(
            ("Artillery Position", "Grushki", "Grushki Flank"),
            ("Panzer's End", "Defence In Depth", "Listening Post"),
            ("The Windmills", "Yamki", "Oleg's House"),
            ("Rudno", "Destroyed Battery", "The Muddy Churn"),
            ("Road To Kursk", "Ammo Dump", "Eastern Position"),
        ),
        orientation=Orientation.VERTICAL,
        allies=Faction.SOV,
        axis=Faction.GER,
    ),

    "Mortain": MapDetails(
        environments=(
            Environment.DAY,
            Environment.OVERCAST,
            Environment.DAWN,
        ),
        objectives=(
            ("Hotel De La Poste", "Forward Battery", "Southern Approach"),
            ("Mortain Outskirts", "Forward Medical Aid Station", "Mortain Approach"),
            ("Hill 314", "Petit Chappelle Saint Michel", "U.S. Southern Roadblock"),
            ("Destroyed German Convoy", "German Recon Camp", "Le Hermitage Farm"),
            ("Abandoned German Checkpoint", "German Defensive Camp", "Farm Of Bonovisin"),
        ),
        orientation=Orientation.HORIZONTAL,
        allies=Faction.US,
        axis=Faction.GER,
    ),

    "Omaha Beach": MapDetails(
        environments=(
            Environment.DAY,
            Environment.DUSK,
        ),
        objectives=(
            ("Beaumont Road", "Crossroads", "Les Isles"),
            ("Rear Battery", "Church Road", "The Orchards"),
            ("West Vierville", "Vierville Sur Mer", "Artillery Battery"),
            ("WN73", "WN71", "WN70"),
            ("Dog Green", "The Draw", "Dog White"),
        ),
        orientation=Orientation.HORIZONTAL,
        allies=Faction.US,
        axis=Faction.GER,
    ),

    "Purple Heart Lane": MapDetails(
        environments=(
            Environment.OVERCAST,
            Environment.NIGHT,
        ),
        objectives=(
            ("Bloody Bend", "Dead Man's Corner", "Forward Battery"),
            ("Jourdan Canal", "Douve Bridge", "Douve River Battery"),
            ("Groult Pillbox", "Carentan Causeway", "Flak Position"),
            ("Madeleine Farm", "Madeleine Bridge", "Aid Station"),
            ("Ingouf Crossroads", "Road To Carentan", "Cabbage Patch"),
        ),
        orientation=Orientation.VERTICAL,
        allies=Faction.US,
        axis=Faction.GER,
    ),

    "Remagen": MapDetails(
        environments=(
            Environment.DAY,
            Environment.NIGHT,
        ),
        objectives=(
            ("Alte Liebe Barsch", "Bewaldet Kreuzung", "Dan Radart 512"),
            ("Erpel", "Erpeler Ley", "Kasbach Outlook"),
            ("St Severin Chapel", "Ludendorff Bridge", "Bauernhof Am Rhein"),
            ("Remagen", "Mobelfabrik", "SchlieffenAusweg"),
            ("Waldburg", "Muhlenweg", "Hagelkreuz"),
        ),
        orientation=Orientation.VERTICAL,
        allies=Faction.US,
        axis=Faction.GER,
    ),

    "Ste. Marie Du Mont": MapDetails(
        environments=(
            Environment.DAY,
            Environment.NIGHT,
        ),
        objectives=(
            ("Winters Landing", "Le Grand Chemin", "The Barn"),
            ("Brecourt Battery", "Cattlesheds", "Rue De La Gare"),
            ("The Dugout", "AA Network", "Pierre's Farm"),
            ("Hugo's Farm", "The Hamlet", "Ste Marie Du Mont"),
            ("The Corner", "Hill 6", "The Fields"),
        ),
        orientation=Orientation.VERTICAL,
        allies=Faction.US,
        axis=Faction.GER,
    ),

    "Ste. Mere Eglise": MapDetails(
        environments=(
            Environment.DAY,
            Environment.NIGHT,
        ),
        objectives=(
            ("Flak Position", "Vaulaville", "La Prairie"),
            ("Route Du Haras", "Western Approach", "Rue De Gambosville"),
            ("Hospice", "Ste Mere Eglise", "Checkpoint"),
            ("Artillery Battery", "The Cemetery", "Maison Du Crique"),
            ("Les Vieux Vergers", "Cross Roads", "Russeau De Ferme"),
        ),
        orientation=Orientation.HORIZONTAL,
        allies=Faction.US,
        axis=Faction.GER,
    ),

    "Stalingrad": MapDetails(
        environments=(
            Environment.DAY,
            Environment.NIGHT,
        ),
        objectives=(
            ("Mamayev Approach", "Nail Factory", "City Overlook"),
            ("Dolgiy Ravine", "Yellow House", "Komsomol HQ"),
            ("Railway Crossing", "Carriage Depot", "Train Station"),
            ("House Of The Workers", "Pavlov's House", "The Brewery"),
            ("L Shaped House", "Grudinin's Mill", "Volga Banks"),
        ),
        orientation=Orientation.HORIZONTAL,
        allies=Faction.SOV,
        axis=Faction.GER,
    ),

    "Utah Beach": MapDetails(
        environments=(
            Environment.DAY,
            Environment.NIGHT,
        ),
        objectives=(
            ("Mammut Radar", "Flooded House", "Sainte Marie Approach"),
            ("Sunken Bridge", "La Grande Crique", "Drowned Fields"),
            ("WN4", "The Chapel", "WN7"),
            ("AABattery", "Hill 5", "WN5"),
            ("Tare Green", "Red Roof House", "Uncle Red"),
        ),
        orientation=Orientation.HORIZONTAL,
        allies=Faction.US,
        axis=Faction.GER,
    ),
}


def get_all_layout_combinations(midpoint_idx: int | None = None) -> Generator[LayoutType, Any, None]:
    def _range(o: int):
        # Only allow for adjacent objectives
        return range(max(0, o-1), min(3, o+2))
    
    # for o1 in range(3):
    #     for o2 in _range(o1):
    #         for o3 in _range(o2):
    #             if midpoint_idx is not None and midpoint_idx != o3:
    #                 continue
    #             for o4 in _range(o3):
    #                 for o5 in _range(o4):
    #                     yield (o1, o2, o3, o4, o5)
    
    for o1 in range(3):
        for o2 in _range(o1):
            if midpoint_idx is not None and midpoint_idx != o2:
                continue
            for o3 in _range(o2):
                yield (o1, o2, o3)

def get_layout_from_filtered_idx(midpoint_idx: int, layout_idx: int):
    filtered_layouts = get_all_layout_combinations(midpoint_idx)
    return next(itertools.islice(filtered_layouts, layout_idx, None))

LAYOUT_COMBINATIONS: tuple[LayoutType, ...] = tuple(get_all_layout_combinations())

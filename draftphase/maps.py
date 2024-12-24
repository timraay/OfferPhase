import itertools
from typing import Any, Generator, Iterable

from pydantic import field_validator

from draftphase import config
from draftphase.config import LayoutType, get_config

class Environment(config.Environment, frozen=True):
    key: str

class Faction(config.Faction, frozen=True):
    key: str

class MapDetails(config.Map, frozen=True):
    key: str
    environments: tuple[Environment, ...]
    allies: Faction
    axis: Faction

    def get_objectives(self, layout: LayoutType):
        return [row[i] for i, row in zip(layout, self.objectives[1:4])]
    
    @field_validator('allies', 'axis', mode='before')
    @classmethod
    def resolve_faction(cls, v: Any):
        if isinstance(v, str):
            return Faction(
                key=v,
                **get_config().factions[v].model_dump(),
            )
        return v

    @field_validator('environments', mode='before')
    @classmethod
    def resolve_environments(cls, v: Any):
        if isinstance(v, Iterable):
            config = get_config()
            return [
                Environment(key=k, **config.environments[k].model_dump())
                if isinstance(k, str) else k
                for k in v
            ]
        return v

class Team(config.Team, frozen=True):
    name: str

ENVIRONMENTS = {
    k: Environment(key=k, **v.model_dump())
    for k, v in get_config().environments.items()
}

FACTIONS = {
    k: Faction(key=k, **v.model_dump())
    for k, v in get_config().factions.items()
}

MAPS = {
    k: MapDetails(key=k, **v.model_dump())
    for k, v in get_config().maps.items()
}

TEAMS = {
    v.rep_role_id: Team(name=k, **v.model_dump())
    for k, v in get_config().teams.items()
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

def has_middleground(team1_id: int, team2_id: int):
    team1 = TEAMS.get(team1_id)
    team2 = TEAMS.get(team2_id)
    if not team1 or not team2:
        return True
    
    return team2.region in get_config().middlegrounds.get(team1.region, [])

from enum import Enum
from pathlib import Path
from typing import Any, Self, Sequence, TypeAlias
from pydantic import BaseModel, field_validator, model_validator
from PIL import Image
import yaml

CONFIG_PATH = Path("config.yaml")

LayoutType: TypeAlias = tuple[int, int, int]
ObjectiveRow: TypeAlias = tuple[str, str, str]

def assert_im_size(v: Path, expected_size: tuple[int, int]):
    assert v.exists(), "File not found"
    im_size = Image.open(v).size
    assert im_size == expected_size, f"Image must be of size {expected_size} but got {im_size}"

class Bot(BaseModel, frozen=True):
    token: str
    emojis: dict[str, str]

class Team(BaseModel, frozen=True):
    rep_role_id: int
    public_role_id: int
    region: str
    emoji: str

class Environment(BaseModel, frozen=True):
    name: str
    emoji: str
    image: Path

    @field_validator("image")
    @classmethod
    def validate_path(cls, v: Path):
        assert_im_size(v, (80, 80))
        return v

class FactionEmojis(BaseModel, frozen=True):
    default: str
    selected: str

class FactionImages(BaseModel, frozen=True):
    default: Path
    selected: Path

    @field_validator("default", "selected")
    @classmethod
    def validate_path(cls, v: Path):
        assert_im_size(v, (256, 256))
        return v

class Faction(BaseModel, frozen=True):
    name: str
    emojis: FactionEmojis
    images: FactionImages

class Orientation(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"

class Map(BaseModel, frozen=True):
    name: str
    short_name: str
    environments: tuple[str, ...]
    objectives: tuple[ObjectiveRow, ObjectiveRow, ObjectiveRow, ObjectiveRow, ObjectiveRow]
    orientation: Orientation
    allies: str
    axis: str
    flip_sides: bool = False
    tacmap: Path

    @field_validator("tacmap")
    @classmethod
    def validate_path(cls, v: Path):
        assert_im_size(v, (400, 400))
        return v

class Config(BaseModel):
    bot: Bot
    teams: dict[str, Team]
    middlegrounds: dict[str, list[str]]
    environments: dict[str, Environment]
    factions: dict[str, Faction]
    maps: dict[str, Map]

    @model_validator(mode="after")
    def check_environment_references(self) -> Self:
        for key, map in self.maps.items():
            for environment in map.environments:
                if environment not in self.environments:
                    raise ValueError("Map %s has unknown environment %s, expected one of %s" % (
                        key, environment, list(self.environments.keys())
                    ))
        return self

    @model_validator(mode="after")
    def check_faction_references(self) -> Self:
        for key, map in self.maps.items():
            if map.allies not in self.factions:
                raise ValueError("Map %s has unknown allied faction %s, expected one of %s" % (
                    key, map.allies, list(self.environments.keys())
                ))
            if map.axis not in self.factions:
                raise ValueError("Map %s has unknown axis faction %s, expected one of %s" % (
                    key, map.axis, list(self.environments.keys())
                ))
        return self

    @field_validator("middlegrounds", mode="before")
    @classmethod
    def replace_middleground_wildcards(cls, v: Any):
        if not isinstance(v, dict):
            return
        
        for region, middlegrounds in v.items():
            if middlegrounds == "*":
                v[region] = list(v.keys())
            elif isinstance(middlegrounds, Sequence):
                for m in middlegrounds:
                    if m not in v:
                        raise ValueError("Unknown middleground %s for region %s. Must be one of %s" % (
                            m, region, list(v.keys())
                        ))
        return v

    @model_validator(mode="after")
    def check_team_regions(self) -> Self:
        for team_name, team in self.teams.items():
            if team.region not in self.middlegrounds:
                raise ValueError("Team %s has undefined region %s, expected one of %s" % (
                    team_name, team.region, list(self.middlegrounds.keys())
                ))
        return self

_CONFIG: Config | None = None
def get_config() -> Config:
    global _CONFIG
    if not _CONFIG:
        if not CONFIG_PATH.exists():
            raise Exception("Config file %s is missing" % CONFIG_PATH)

        content = CONFIG_PATH.read_text(encoding="utf-8")
        config_data = yaml.safe_load(content)
        _CONFIG = Config(**config_data)
    return _CONFIG

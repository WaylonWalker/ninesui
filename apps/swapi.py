#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx",
#     "ninesui @ git+https://github.com/waylonwalker/ninesui.git",
# ]
# ///
from typing import Optional
from pydantic import Field
from typing import ClassVar
from pydantic import BaseModel
from ninesui import CommandSet, Command, NinesUI
import httpx
from pydantic import HttpUrl
from typing import List, TypeVar
from textual import log

BASE_URL = "https://swapi.dev/api/"

T = TypeVar("T", bound="SWAPIResource")


class SWAPIResource(BaseModel):
    url: HttpUrl

    nines_config: ClassVar[dict] = {"bindings": {"f": "get_films"}}

    @classmethod
    def fetch(cls, ctx=None):
        endpoint = cls.__name__.lower() + "s"
        if endpoint == "persons":
            endpoint = "people"

        client = httpx.Client(verify=False)
        log(f"Fetching {endpoint}")

        if ctx:
            if hasattr(ctx, endpoint):
                result = []

                for url in getattr(ctx, endpoint):
                    res = client.get(str(url)).json()
                    result.append(cls(**res))
                return result

        url = f"{BASE_URL}{endpoint}/"

        results: List[T] = []
        while url:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
            results.extend(cls(**item) for item in data.get("results", []))
            url = data.get("next")

        return results

    def hover(self):
        return self

    def get_films(self):
        client = httpx.Client(verify=False)
        return_films = []
        for film in self.films:
            result = client.get(str(film)).json()
            return_films.append(Film(**result))

        return return_films

        return [Film(**httpx.get(film, verify=False).json()) for film in self.films]


class Person(SWAPIResource):
    name: str
    height: str
    mass: str
    hair_color: str
    skin_color: str
    eye_color: str
    birth_year: str
    gender: str
    homeworld: HttpUrl
    films: List[HttpUrl]
    species: List[HttpUrl]
    vehicles: List[HttpUrl]
    starships: List[HttpUrl]
    created: str
    edited: str


class Planet(SWAPIResource):
    name: str
    rotation_period: str
    orbital_period: str
    diameter: str
    climate: str
    gravity: str
    terrain: str
    surface_water: str
    population: str
    residents: List[HttpUrl]
    films: List[HttpUrl]
    created: str
    edited: str


class Starship(SWAPIResource):
    name: str
    model: str
    manufacturer: str
    cost_in_credits: str
    length: str
    max_atmosphering_speed: str
    crew: str
    passengers: str
    cargo_capacity: str
    consumables: str
    hyperdrive_rating: str
    MGLT: str
    starship_class: str
    pilots: List[HttpUrl]
    films: List[HttpUrl]
    created: str
    edited: str


class Vehicle(SWAPIResource):
    name: str
    model: str
    manufacturer: str
    cost_in_credits: str
    length: str
    max_atmosphering_speed: str
    crew: str
    passengers: str
    cargo_capacity: str
    consumables: str
    vehicle_class: str
    pilots: List[HttpUrl]
    films: List[HttpUrl]
    created: str
    edited: str


class Species(SWAPIResource):
    name: str
    classification: str
    designation: str
    average_height: str
    skin_colors: str
    hair_colors: str
    eye_colors: str
    average_lifespan: str
    homeworld: Optional[HttpUrl]
    language: str
    people: List[HttpUrl]
    films: List[HttpUrl]
    created: str
    edited: str


class Film(SWAPIResource):
    title: str
    episode_id: int
    opening_crawl: str
    director: str
    producer: str
    release_date: str
    people: List[HttpUrl] = Field(..., alias="characters")
    # characters: List[HttpUrl]
    planets: List[HttpUrl]
    starships: List[HttpUrl]
    vehicles: List[HttpUrl]
    species: List[HttpUrl]
    created: str
    edited: str


commands = CommandSet(
    [
        Command(
            name="person",
            aliases=["p"],
            model=Person,
        ),
        Command(
            name="planet",
            aliases=["pl"],
            model=Planet,
        ),
        Command(
            name="starship",
            aliases=["s"],
            model=Starship,
        ),
        Command(
            name="vehicle",
            aliases=["v"],
            model=Vehicle,
        ),
        Command(
            name="species",
            aliases=["sp"],
            model=Species,
        ),
        Command(
            name="film",
            aliases=["f"],
            model=Film,
            is_default=True,
        ),
    ]
)

metadata = {
    "title": "SWAPI Viewer",
    "subtitle": "Use :list to list files. Enter to drill in. Shift+J to go up.",
}


if __name__ == "__main__":
    ui = NinesUI(metadata=metadata, commands=commands)
    ui.run()

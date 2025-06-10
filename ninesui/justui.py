from pydantic import BaseModel
from typing import Optional, Any, ClassVar
from pathlib import Path
import json
import subprocess
from ninesui import CommandSet, Command, NinesUI

from typing import Dict, List


class Recipe(BaseModel):
    attributes: List[Any]
    body: List[List[str]]
    dependencies: List[str]
    doc: Optional[str]
    name: str
    namepath: str
    parameters: List[Any]
    priors: int
    private: bool
    quiet: bool
    shebang: bool

    nines_config: ClassVar[dict] = {"visible_fields": ["name"]}

    def render(self, ctx=None):
        return self.body

    @classmethod
    def fetch(self, ctx=None):
        from textual import log

        log("Fetching recipe")
        recipes = JUSTFILE.recipes.keys()
        log(f"Recipes values: {list(JUSTFILE.recipes.values())}")
        return list(JUSTFILE.recipes.values())
        return "\n".join(recipes)

    def hover(self, ctx=None):
        from textual import log

        log(f"Hovering over recipe {self.name}")
        log(f"Recipe body: {'\n'.join(self.body[0])}")

        return (
            "\n".join([" ".join(cmd) for cmd in self.body])
            if self.body
            else self.body[0]
        )

    def drill(self, ctx=None):
        from textual import log

        log(f"Drilling into recipe {self.name}")
        return JUSTFILE.recipes[self.name]


class Settings(BaseModel):
    allow_duplicate_recipes: bool
    allow_duplicate_variables: bool
    dotenv_filename: Optional[str]
    dotenv_load: bool
    dotenv_path: Optional[str]
    dotenv_required: bool
    export: bool
    fallback: bool
    ignore_comments: bool
    no_exit_message: bool
    positional_arguments: bool
    quiet: bool
    shell: Optional[str]
    tempdir: Optional[str]
    unstable: bool
    windows_powershell: bool
    windows_shell: Optional[str]
    working_directory: Optional[str]


class Justfile(BaseModel):
    aliases: Dict[str, Any]
    assignments: Dict[str, Any]
    first: Optional[str]
    doc: Optional[str]
    groups: List[Any]
    modules: Dict[str, Any]
    recipes: Dict[str, Recipe]
    settings: Settings
    source: str
    unexports: List[Any]
    warnings: List[Any]


def load_justfile(path: Path = Path(".")) -> Justfile:
    try:
        result = subprocess.run(
            ["just", "--dump", "--dump-format", "json"],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        )
        just_data = json.loads(result.stdout)
        return Justfile(**just_data)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to run `just`: {e.stderr.strip()}") from e
    except json.JSONDecodeError as e:
        raise ValueError("Invalid JSON returned by `just --dump`") from e


JUSTFILE = load_justfile()


# class Recipe(BaseModel):
#     name: str


metadata = {
    "title": "JusTUI",
    "subtitle": "Use :list to list files. Enter to drill in. Shift+J to go up.",
}


commands = CommandSet(
    [
        Command(
            name="recipes",
            aliases=["r", "recipe"],
            model=Recipe,
        ),
    ]
)

if __name__ == "__main__":
    ui = NinesUI(metadata=metadata, commands=commands)
    ui.run()

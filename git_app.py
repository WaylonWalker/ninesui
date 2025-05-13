import psutil
from typing import Optional, Any, Dict
import os
from pydantic import BaseModel
from pathlib import Path
from rich.syntax import Syntax
from ninesui import CommandSet, Command, NinesUI
from git import Repo, HEAD


class Log(BaseModel):
    actor: Any
    message: str
    time: Any
    newhexsha: str


class Branch(BaseModel):
    name: str
    repo: Optional[Any] = None
    branch: Optional[Any] = None

    @classmethod
    def fetch(cls, ctx=None):
        repo = Repo(os.getcwd())
        return [Branch(name=b.name, repo=repo, branch=b) for b in repo.branches]

    def drill(self, entry):
        return "\n".join(message.message for message in entry.branch.log())
        return [
            Log(
                actor=log.actor,
                message=log.message,
                time=log.time,
                newhexsha=log.newhexsha,
            )
            for log in entry.branch.log()
        ]


commands = CommandSet(
    [
        Command(
            name="branch",
            aliases=["br"],
            model=Branch,
            visible_fields=[
                "name",
            ],
        ),
    ]
)

metadata = {
    "title": "Git Viewer",
    "subtitle": "Use :list to list files. Enter to drill in. Shift+J to go up.",
}


if __name__ == "__main__":
    ui = NinesUI(metadata=metadata, commands=commands)
    ui.run()

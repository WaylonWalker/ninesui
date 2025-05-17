#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "gitpython",
#     "ninesui @ git+https://github.com/waylonwalker/ninesui.git",
# ]
# ///
from typing import Optional, Any, ClassVar
from textual import log
import os
from pydantic import BaseModel
from ninesui import CommandSet, Command, NinesUI
from git import Repo, NULL_TREE
from rich.syntax import Syntax
from rich.panel import Panel
from rich.text import Text
from rich.console import Group


class Diff(BaseModel):
    repo: Any
    commit: Any

    nines_config: ClassVar[dict] = {"visible_fields": ["message"]}

    def render(self):
        """
        Return a rich Group renderable showing the commit metadata and diffs as panels.

        :param repo: GitPython Repo object
        :param commit: Commit object or SHA
        :return: rich renderable (Group of Panels)
        """
        repo = self.repo
        commit = self.commit

        commit = repo.commit(commit)  # Accept SHA or Commit object
        panels = []

        # Commit metadata
        header = Text.assemble(
            ("Commit: ", "bold green"),
            f"{commit.hexsha}\n",
            ("Author: ", "bold"),
            f"{commit.author.name} <{commit.author.email}>\n",
            ("Date: ", "bold"),
            f"{commit.committed_datetime}\n",
            ("Message: ", "bold"),
            f"{commit.message.strip()}\n",
        )
        panels.append(Panel(header, title="Commit Info", border_style="green"))

        # Diffs
        parent = commit.parents[0] if commit.parents else NULL_TREE
        # diffs = commit.diff(parent, create_patch=True)
        diffs = parent.diff(commit, create_patch=True)

        for d in diffs:
            try:
                patch = d.diff.decode("utf-8", errors="replace")
                file_label = d.a_path or d.b_path or "unknown file"
                syntax = Syntax(patch, "diff", theme="monokai", line_numbers=False)
                panel = Panel(
                    syntax, title=file_label, title_align="left", border_style="blue"
                )
                panels.append(panel)
            except Exception as e:
                error_panel = Panel(f"Error processing {file_label}: {e}", style="red")
                panels.append(error_panel)

        return Group(*panels)


class Log(BaseModel):
    repo: Optional[Any] = None
    actor: Any
    message: str
    time: Any
    newhexsha: str
    nines_config: ClassVar[dict] = {
        "visible_fields": [
            "actor",
            "message",
            "time",
            "newhexsha",
        ]
    }

    @classmethod
    def fetch(cls, ctx=None):
        messages = []
        repo = Repo(os.getcwd())
        branch = repo.active_branch
        for commit in repo.iter_commits(branch):
            messages.append(
                Log(
                    actor=commit.author.name,
                    message=commit.message,
                    time=commit.committed_datetime,
                    newhexsha=commit.hexsha,
                )
            )

        return messages

    def drill(self):
        repo = Repo(os.getcwd())
        commit = self.newhexsha

        return Diff(repo=repo, commit=commit)

    def hover(self):
        repo = Repo(os.getcwd())
        commit = self.newhexsha

        return Diff(repo=repo, commit=commit)


class Branch(BaseModel):
    name: str
    repo: Optional[Any] = None
    branch: Optional[Any] = None
    nines_config: ClassVar[dict] = {
        "visible_fields": ["name"],
        "bindings": {"b": "test"},
    }

    # @property
    # def nines_config(self):
    #     return {
    #         "visible_fields": ["name"],
    #         "bindings": {"b": self.test},
    #     }

    def test(self):
        log("test")
        return "test"

    @classmethod
    def fetch(cls, ctx=None):
        repo = Repo(os.getcwd())
        return [Branch(name=b.name, repo=repo, branch=b) for b in repo.branches]

    def render(self):
        return "\n".join(message.message for message in self.branch.log())

    def drill(self):
        messages = []
        branch = self.branch
        for commit in self.repo.iter_commits(branch):
            messages.append(
                Log(
                    actor=commit.author.name,
                    message=commit.message,
                    time=commit.committed_datetime,
                    newhexsha=commit.hexsha,
                )
            )

        return messages


commands = CommandSet(
    [
        Command(
            name="branch",
            aliases=["br"],
            model=Branch,
        ),
        Command(
            name="log",
            aliases=["l"],
            model=Log,
            is_default=True,
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

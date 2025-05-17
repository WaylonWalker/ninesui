#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "gitpython",
#     "ninesui @ git+https://github.com/waylonwalker/ninesui.git",
# ]
# ///
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, ClassVar, Any, Literal
from git import Repo
from textual import log
import os
from ninesui import CommandSet, Command, NinesUI
from git import NULL_TREE
from rich.syntax import Syntax
from rich.panel import Panel
from rich.text import Text
from rich.console import Group


def get_file_content_at_commit(path: str, hexsha: str) -> str:
    repo = Repo(os.getcwd())
    if hexsha is None:
        hexsha = repo.head.commit.hexsha

    commit = repo.commit(hexsha)

    # Try this commit first
    try:
        return (commit.tree / path).data_stream.read().decode("utf-8", errors="replace")
    except KeyError:
        # Fallback: try parent commit if the file doesn't exist here (likely deleted)
        if commit.parents:
            parent = commit.parents[0]
            try:
                return (
                    (parent.tree / path)
                    .data_stream.read()
                    .decode("utf-8", errors="replace")
                )
            except Exception:
                pass
    except Exception:
        pass

    return None


class File(BaseModel):
    repo: Any
    path: str = Field(..., description="The file path relative to the repository root")
    size: int = Field(..., description="File size in bytes")
    blob_hexsha: str = Field(..., description="Git object SHA for the file")
    newhexsha: Optional[str] = None
    nines_config: ClassVar[dict] = {"visible_fields": ["path", "size"]}

    @classmethod
    def fetch(cls, ctx=None) -> List["File"]:
        repo = Repo(os.getcwd())

        if ctx and hasattr(ctx, "newhexsha"):
            commit = repo.commit(ctx.newhexsha)
            parent = commit.parents[0] if commit.parents else None

            # Get the diff between this commit and its parent
            diffs = commit.diff(parent, create_patch=False)
            files: List[File] = []

            for diff in diffs:
                if diff.a_blob:  # the file existed before
                    files.append(
                        cls(
                            repo=repo,
                            path=diff.a_path,
                            size=diff.a_blob.size,
                            blob_hexsha=diff.a_blob.hexsha,
                            newhexsha=ctx.newhexsha,
                        )
                    )
                elif diff.b_blob:  # new file added in this commit
                    files.append(
                        cls(
                            repo=repo,
                            path=diff.b_path,
                            size=diff.b_blob.size,
                            blob_hexsha=diff.b_blob.hexsha,
                            newhexsha=ctx.newhexsha,
                        )
                    )
            return files
        commit = repo.head.commit
        log(f"commit: {commit}")
        log(ctx)
        commit = repo.commit(commit)
        tree = commit.tree

        files: List[File] = []
        for blob in tree.traverse():
            if blob.type == "blob":  # Only include files, not trees (directories)
                files.append(
                    cls(
                        repo=repo,
                        path=blob.path,
                        size=blob.size,
                        blob_hexsha=blob.hexsha,
                    )
                )
        return files

    # def hover(self):
    #     try:
    #         syntax = Syntax.from_path(self.path)
    #     except UnicodeDecodeError:
    #         return f"{self.path} is a binary file"
    #     return syntax
    def hover(self):
        """Return syntax-highlighted version of the file *at this specific commit*."""
        content = get_file_content_at_commit(self.path, self.newhexsha)
        if content is None:
            return f"{self.path} is a binary file or could not be decoded"

        return Syntax(content, lexer=Syntax.guess_lexer(self.path), line_numbers=True)

    def drill(self) -> List["Log"]:
        """Return the commit history affecting this file."""
        repo = Repo(os.getcwd())
        commits = repo.iter_commits(paths=self.path)

        return [
            Log(
                actor=commit.author.name,
                message=commit.message,
                time=commit.committed_datetime,
                newhexsha=commit.hexsha,
            )
            for commit in commits
        ]


class DeletedFile(File):
    deleted_in_sha: str
    deleted_in_message: str
    deleted_in_author: str
    deleted_in_time: str
    change_type: Literal["deleted"]
    old_path: str

    nines_config: ClassVar[dict] = {
        "visible_fields": [
            "deleted_in_sha",
            "path",
            "deleted_in_author",
            "deleted_in_message",
        ],
        "bindings": {"r": "restore"},
    }

    @classmethod
    def fetch(cls, ctx=None) -> List["DeletedFile"]:
        repo = Repo(os.getcwd())
        deleted_files = []

        try:
            # log format: sha\nfile\nfile\n\nsha\nfile\n...
            raw = repo.git.log(
                "--diff-filter=D",
                "--name-only",
                "--pretty=format:__DEL__%H",
            )
        except Exception as e:
            print(f"Error running git log: {e}")
            return []

        current_commit = None
        for line in raw.splitlines():
            if line.startswith("__DEL__"):
                current_commit = line.replace("__DEL__", "")
            elif line.strip() == "":
                continue
            else:
                path = line.strip()
                if not current_commit:
                    continue
                try:
                    commit = repo.commit(current_commit)
                    parent = commit.parents[0] if commit.parents else None
                    if not parent:
                        continue

                    blob = parent.tree / path
                    deleted_files.append(
                        cls(
                            repo=repo,
                            path=path,
                            size=blob.size,
                            blob_hexsha=blob.hexsha,
                            newhexsha=commit.hexsha,
                            change_type="deleted",
                            deleted_in_sha=commit.hexsha,
                            deleted_in_message=commit.message.strip(),
                            deleted_in_author=commit.author.name,
                            deleted_in_time=str(commit.committed_datetime),
                            old_path=path,
                        )
                    )
                except Exception as e:
                    print(f"Error processing {path} in {current_commit}: {e}")
                    continue

        return deleted_files

    def restore(self) -> None:
        path = Path(self.path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Use blob_sha to retrieve contents
        blob = self.repo.git.cat_file("blob", self.blob_hexsha)
        path.write_text(blob)


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
        Command(
            name="file",
            aliases=["f"],
            model=File,
        ),
        Command(
            name="deleted",
            aliases=["del"],
            model=DeletedFile,
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

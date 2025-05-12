# =========================== ninesui/core/commands.py ===========================
from typing import Callable, Optional, Type
from pydantic import BaseModel


class Command:
    def __init__(
        self,
        name: str,
        model: Type[BaseModel],
        fetch_fn: Callable[..., list[BaseModel]],
        drill_fn: Optional[Callable[[BaseModel], list[BaseModel] | BaseModel]] = None,
        jump_fn: Optional[Callable[[BaseModel], list[BaseModel] | BaseModel]] = None,
        visible_fields: Optional[list[str]] = None,
    ):
        self.name = name
        self.model = model
        self.fetch_fn = fetch_fn
        self.drill_fn = drill_fn
        self.jump_fn = jump_fn
        self.visible_fields = visible_fields


class CommandSet:
    def __init__(self, commands: list[Command]):
        self.commands = {f":{cmd.name}": cmd for cmd in commands}

    def get(self, command_name: str) -> Optional[Command]:
        return self.commands.get(command_name)


# =========================== ninesui/core/router.py ===========================
from dataclasses import dataclass


@dataclass
class CommandContext:
    command: Command
    data: list[BaseModel]
    selected_index: int = 0


class Router:
    def __init__(self, commands: CommandSet):
        self.commands = commands
        self.stack: list[CommandContext] = []
        self.output = None
        self.highlighted_index = 0

    def set_output_widget(self, widget):
        self.output = widget

    def push_command(self, cmd_str: str):
        cmd = self.commands.get(cmd_str)
        if cmd:
            data = cmd.fetch_fn()
            ctx = CommandContext(command=cmd, data=data)
            self.stack.append(ctx)
            self.refresh_output()

    def refresh_output(self):
        if not self.stack or not self.output:
            return
        ctx = self.stack[-1]
        data = ctx.data
        self.output.clear(columns=True)
        if not data:
            return
        model = ctx.command.model
        fields = ctx.command.visible_fields or model.model_fields.keys()
        self.output.add_columns(*fields)

        for i, item in enumerate(data):
            self.output.add_row(*(str(getattr(item, f, "")) for f in fields), key=i)

    def drill_in(self):
        ctx = self.stack[-1]
        index = self.highlighted_index
        if index >= len(ctx.data):
            return
        item = ctx.data[index]
        if ctx.command.drill_fn:
            result = ctx.command.drill_fn(item)
            if isinstance(result, list):
                self.stack.append(CommandContext(command=ctx.command, data=result))
            else:
                self.stack.append(CommandContext(command=ctx.command, data=[result]))
            self.refresh_output()

    def jump_owner(self):
        ctx = self.stack[-1]
        item = ctx.data[self.highlighted_index]
        if ctx.command.jump_fn:
            result = ctx.command.jump_fn(item)
            if isinstance(result, list):
                self.stack.append(CommandContext(command=ctx.command, data=result))
            else:
                self.stack.append(CommandContext(command=ctx.command, data=[result]))
            self.refresh_output()

    def go_back(self):
        if len(self.stack) > 1:
            self.stack.pop()
            self.refresh_output()
            return True
        return False


# =========================== ninesui/core/views.py ===========================
from textual.widgets import Static


class MetaHeader(Static):
    def __init__(self, metadata: dict):
        title = metadata.get("title", "")
        subtitle = metadata.get("subtitle", "")
        super().__init__(f"{title} — {subtitle}")


# =========================== ninesui/core/app.py ===========================
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Header, Footer, Input, DataTable
from textual.binding import Binding


class NinesUI(App):
    CSS_PATH = "style.css"
    BINDINGS = [
        Binding("escape", "go_back_or_quit", "Back/Quit"),
        Binding(":", "focus_command", "Command"),
    ]

    def __init__(self, metadata: dict, commands: CommandSet, **kwargs):
        super().__init__(**kwargs)
        self.router = Router(commands)
        self.metadata = metadata
        self.command_input = Input(placeholder=":command")
        self.output = DataTable()
        self.meta_header = MetaHeader(metadata)

    def compose(self) -> ComposeResult:
        yield self.meta_header
        yield self.command_input
        yield self.output
        yield Footer()

    def on_mount(self):
        self.command_input.display = False
        self.router.set_output_widget(self.output)
        self.router.push_command(":list")

    def action_focus_command(self):
        self.command_input.display = True
        self.command_input.focus()

    def action_go_back_or_quit(self):
        if self.command_input.has_focus:
            self.command_input.blur()
            self.command_input.display = False
        elif not self.router.go_back():
            self.exit()

    def on_input_submitted(self, message: Input.Submitted):
        cmd = message.value.strip()
        self.command_input.value = ""
        self.command_input.display = False
        self.command_input.blur()
        self.router.push_command(cmd)

    # def on_data_table_row_highlighted(self, message: DataTable.RowHighlighted):
    #     self.router.highlighted_index = message.row_key

    def on_data_table_row_highlighted(self, message: DataTable.RowHighlighted):
        self.router.highlighted_index = int(message.row_key)

    def on_data_table_row_selected(self, message: DataTable.RowSelected):
        self.router.drill_in()

    def on_key(self, event):
        key = event.key
        if key == "J":
            self.router.jump_owner()
        elif key == "enter":
            self.router.drill_in()


# =========================== apps/filesystem/models.py ===========================
from pydantic import BaseModel
from pathlib import Path


class FileEntry(BaseModel):
    name: str
    path: str
    is_dir: bool


# =========================== apps/filesystem/config.py ===========================
import os

current_path = os.getcwd()


def list_dir(path: str = current_path) -> list[FileEntry]:
    return [
        FileEntry(name=e.name, path=str(e), is_dir=e.is_dir())
        for e in Path(path).iterdir()
    ]


def drill(entry: FileEntry):
    if entry.is_dir:
        return list_dir(entry.path)
    return entry  # or maybe open and show content later


def jump(entry: FileEntry):
    parent = str(Path(entry.path).parent)
    return list_dir(parent)


# from ninesui.core.commands import Command, CommandSet
# from apps.filesystem.models import FileEntry

commands = CommandSet(
    [
        Command(
            name="list",
            model=FileEntry,
            fetch_fn=list_dir,
            drill_fn=drill,
            jump_fn=jump,
            visible_fields=["name", "is_dir"],
        )
    ]
)

metadata = {
    "title": "Filesystem Viewer",
    "subtitle": "Use :list to list files. Enter to drill in. Shift+J to go up.",
}

# =========================== __main__.py ===========================
if __name__ == "__main__":
    # from apps.filesystem.config import commands, metadata

    # NinesUI.run(title=metadata["title"], metadata=metadata, commands=commands)
    ui = NinesUI(metadata=metadata, commands=commands)
    ui.run()

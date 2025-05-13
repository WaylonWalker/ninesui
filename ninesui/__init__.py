from typing import Callable, Optional, Type
from pydantic import BaseModel
from pydantic import model_validator
from textual import log
from textual.widgets import Static


class Command:
    def __init__(
        self,
        name: str,
        model: Type[BaseModel],
        fetch_fn: Optional[Callable[..., list[BaseModel]]] = None,
        aliases: Optional[list[str]] = None,
        drill_fn: Optional[Callable[[BaseModel], list[BaseModel] | BaseModel]] = None,
        jump_fn: Optional[Callable[[BaseModel], list[BaseModel] | BaseModel]] = None,
        visible_fields: Optional[list[str]] = None,
    ):
        self.name = name
        self.model = model
        self.aliases = aliases
        self.fetch_fn = fetch_fn
        self.drill_fn = drill_fn
        self.jump_fn = jump_fn
        self.visible_fields = visible_fields


class CommandSet:
    def __init__(self, commands: list[Command]):
        self.commands = {f":{cmd.name}": cmd for cmd in commands}
        for cmd in commands:
            for alias in cmd.aliases:
                self.commands[f":{alias}"] = cmd

    def get(self, command_name: str) -> Optional[Command]:
        return self.commands.get(command_name)

    @model_validator(mode="after")
    def validate_unique_name_and_aliases(self):
        names = [cmd.name for cmd in self.commands.values()]
        aliases = [alias for cmd in self.commands.values() for alias in cmd.aliases]
        names_and_aliases = names + aliases
        if len(set(names_and_aliases)) != len(names_and_aliases):
            raise ValueError("Command names and aliases must be unique")
        return self


# =========================== ninesui/core/router.py ===========================
from dataclasses import dataclass
from textual.widgets import DataTable
from textual.containers import Container


@dataclass
class CommandContext:
    command: Command
    data: list[BaseModel]
    selected_index: int = 0


class Router:
    def __init__(self, app, commands: CommandSet):
        self.app = app
        self.commands = commands
        self.stack: list[CommandContext] = []
        self.highlighted_index = 0

    def set_output_widget(self, container: Container):
        self.output_container = container

    def push_command(self, cmd_str: str):
        cmd = self.commands.get(cmd_str)
        if cmd:
            self.app.notify(f'Running command "{cmd_str}"')
            # Get the current context if we have one
            current_ctx = self.stack[-1] if self.stack else None
            # if current_ctx:
            #     if isinstance(current_ctx.data, list):

            # Pass the current context to the fetch function
            data = cmd.fetch_fn(current_ctx)

            # Create new context
            ctx = CommandContext(command=cmd, data=data)
            self.stack.append(ctx)
            self.refresh_output()
        else:
            self.app.notify(f'Command "{cmd_str}" not found')

    def refresh_output(self):
        if not self.stack:
            return

        ctx = self.stack[-1]
        data = ctx.data
        self.output_container.remove_children()

        if isinstance(data, BaseModel):
            if hasattr(data, "render"):
                detail = Static(data.render(), markup=False, classes="detail")
            else:
                from rich.pretty import Pretty

                detail = Static(Pretty(data), markup=False, classes="detail")

            detail.focus()
            self.output_container.mount(detail)
            return

        if isinstance(data, list):
            if not data:
                return
            model = ctx.command.model
            fields = ctx.command.visible_fields or model.model_fields.keys()

            table = DataTable()
            table.cursor_type = "row"
            table.show_cursor = True
            table.focus()
            table.add_columns(*fields)

            for i, item in enumerate(data):
                table.add_row(*(str(getattr(item, f, "")) for f in fields), key=i)

            self.output_container.mount(table)
            self.app.output = table
            self.app.assign_sort_hotkeys(fields)

    def drill_in(self):
        ctx = self.stack[-1]
        index = self.highlighted_index
        log(f"drilling into {ctx.data[index]} using index {index}")
        if index >= len(ctx.data):
            return
        item = ctx.data[index]
        if ctx.command.drill_fn:
            result = ctx.command.drill_fn(item)
            if isinstance(result, list):
                self.stack.append(CommandContext(command=ctx.command, data=result))
            else:
                self.stack.append(CommandContext(command=ctx.command, data=result))
            self.refresh_output()

    def jump_owner(self):
        ctx = self.stack[-1]
        item = ctx.data[self.highlighted_index]
        if ctx.command.jump_fn:
            result = ctx.command.jump_fn(item)
            if isinstance(result, list):
                self.stack.append(CommandContext(command=ctx.command, data=result))
            else:
                self.stack.append(CommandContext(command=ctx.command, data=result))
            self.refresh_output()

    def go_back(self):
        if len(self.stack) > 1:
            self.stack.pop()
            self.refresh_output()
            return True
        return False


# =========================== ninesui/core/views.py ===========================


class MetaHeader(Static):
    def __init__(self, metadata: dict):
        title = metadata.get("title", "")
        subtitle = metadata.get("subtitle", "")
        super().__init__(f"{title} — {subtitle}")


# =========================== ninesui/core/app.py ===========================
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Input
from textual.binding import Binding


class NinesUI(App):
    CSS_PATH = "styles.css"
    BINDINGS = [
        Binding("escape", "go_back_or_quit", "Back/Quit"),
        Binding(":", "focus_command", "Command"),
    ]

    def __init__(self, metadata: dict, commands: CommandSet, **kwargs):
        super().__init__(**kwargs)
        self.router = Router(self, commands)
        self.metadata = metadata
        self.command_input = Input(placeholder=":command")
        self.output = DataTable()
        self.meta_header = MetaHeader(metadata)
        self.output_container = Container(self.output, id="output-container")
        self._dynamic_sort_keys = {}  # key: sort function
        self._last_sort = {"key": None, "reverse": False}

    def compose(self) -> ComposeResult:
        yield self.meta_header
        yield self.command_input
        yield self.output_container
        yield Footer()

    def on_mount(self):
        self.command_input.display = False
        self.router.set_output_widget(self.output_container)
        self.output.cursor_type = "row"
        self.output.show_cursor = True
        self.output.focus()
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
        cmd = self.command_input.value
        self.command_input.value = ""
        self.command_input.display = False
        self.command_input.blur()
        # Add the : prefix if not present
        if not cmd.startswith(":"):
            cmd = f":{cmd}"
        self.router.push_command(cmd)

    def on_data_table_row_highlighted(self, message: DataTable.RowHighlighted):
        self.router.highlighted_index = message.row_key.value

    def on_data_table_row_selected(self, message: DataTable.RowSelected):
        self.router.drill_in()

    def on_key(self, event):
        key = event.key
        if key == "J":
            self.router.jump_owner()
        elif key == "enter":
            if not self.command_input.has_focus:
                log(
                    f"drilling in with highlighted index: {self.router.highlighted_index}"
                )
                log(
                    f"drilling in with highlighted index: {self.router.highlighted_index}"
                )
                log(
                    f"drilling in with highlighted index: {self.router.highlighted_index}"
                )
                log(
                    f"drilling in with highlighted index: {self.router.highlighted_index}"
                )
                log(
                    f"drilling in with highlighted index: {self.router.highlighted_index}"
                )
                log(
                    f"drilling in with highlighted index: {self.router.highlighted_index}"
                )
                self.router.drill_in()
            else:
                log(f"submitting command: {self.command_input.value}")
                log(f"submitting command: {self.command_input.value}")
                log(f"submitting command: {self.command_input.value}")
                log(f"submitting command: {self.command_input.value}")
                log(f"submitting command: {self.command_input.value}")
                self.on_input_submitted(self.command_input)
        elif key in self._dynamic_sort_keys:
            self._dynamic_sort_keys[key]()

    def assign_sort_hotkeys(self, fields: list[str]):
        taken = set()
        self._dynamic_sort_keys.clear()
        for field in fields:
            for char in field:
                key = char.upper()
                if key not in taken and key.isalpha():
                    taken.add(key)

                    def sorter(field=field):
                        reverse = False
                        if self._last_sort["key"] == field:
                            reverse = not self._last_sort["reverse"]
                        self._last_sort["key"] = field
                        self._last_sort["reverse"] = reverse

                        ctx = self.router.stack[-1]
                        ctx.data.sort(key=lambda x: getattr(x, field), reverse=reverse)
                        self.router.refresh_output()

                    self._dynamic_sort_keys[key] = sorter
                    break

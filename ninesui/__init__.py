from typing import Optional, Type
import inspect
from pydantic import BaseModel
from pydantic import model_validator
from textual import log
from textual.widgets import Static
from textual.suggester import SuggestFromList
import os

SCREENKEY = os.getenv("NINES_SCREENKEY")


class Command:
    def __init__(
        self,
        name: str,
        model: Type[BaseModel],
        is_default: bool = False,
        aliases: Optional[list[str]] = None,
        visible_fields: Optional[list[str]] = None,
    ):
        self.name = name
        self.model = model
        self.aliases = aliases
        self.is_default = is_default
        self.visible_fields = visible_fields
        self.command = f":{name}"


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
from textual.binding import Binding

OPERATION_SYMBOLS = {
    "fetch": "→",
    "drill": "⤵",
    "jump": "⤴",
}


class VimmyDataTable(DataTable):
    BINDINGS = DataTable.BINDINGS + [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    async def action_cursor_down(self) -> None:
        log("cursor down")
        super().action_cursor_down()

    async def action_cursor_up(self) -> None:
        log("cursor up")
        super().action_cursor_up()


@dataclass
class CommandContext:
    command: Command
    data: list[BaseModel]
    item: Optional[BaseModel]
    selected_index: int = 0
    operation: Optional[str] = None

    @property
    def operation_symbol(self):
        return OPERATION_SYMBOLS.get(self.operation)


class Router:
    def __init__(self, app, commands: CommandSet):
        self.app = app
        self.commands = commands
        self.stack: list[CommandContext] = []
        self.highlighted_index = 0

    def set_output_widget(self, container: Container):
        self.output_container = container

    def set_hover_widget(self, container: Container):
        self.hover_container = container

    def set_popup_widget(self, container: Container):
        self.popup_container = container

    def set_header_widget(self, container: Container):
        self.header_container = container

    def push_search(self, query: str):
        self.hover_container.remove_children()
        self.app.notify(f'Searching for "{query}"')
        # self.app.search(query)
        ctx = self.stack[-1]
        import copy

        ctx = copy.deepcopy(ctx)
        ctx.data = [item for item in ctx.data if query in str(item)]

        self.stack.append(ctx)
        self.app.notify(f'Searching for "{query}"')
        self.app.breadcrumbs_text.append(f"/{query}")
        self.app.breadcrumbs.update(" ".join(self.app.breadcrumbs_text))
        self.refresh_output()

    async def push_command(self, cmd_str: str):
        log(f"pushing command: {cmd_str}")
        if not cmd_str.startswith(":"):
            cmd_str = f":{cmd_str}"

        if cmd_str[1].isupper():
            is_global = True
        else:
            is_global = False

        cmd_str = cmd_str.lower()

        if cmd_str in [":command", ":commands"]:
            commands = [
                f"{name}\[{','.join([alias for alias in command.aliases])}]"
                for name, command in self.commands.commands.items()
                if name == command.command
            ]
            self.app.notify(
                f"Available commands: {', '.join(commands)}",
                title="Commands",
                severity="command",
                timeout=10,
            )
            return
        cmd = self.commands.get(cmd_str)
        if cmd:
            self.app.notify(f'Running command "{cmd_str}"')
            # Get the current context if we have one
            current_ctx = self.stack[-1] if self.stack else None
            item = current_ctx.data[self.highlighted_index] if current_ctx else None
            self.output_container.remove_children()
            if is_global:
                log("Command is being ran as a global command")
                if inspect.iscoroutinefunction(cmd.model.fetch):
                    log("refreshing current context in worker")
                    data = await current_ctx.command.model.fetch()
                    log(f"Got {len(data)} items")
                else:
                    log("refreshing current context synchronously")
                    data = current_ctx.command.model.fetch()
                    log(f"Got {len(data)} items")
            else:
                log("Command is being ran as a local command")
                if inspect.iscoroutinefunction(cmd.model.fetch):
                    log("refreshing current context in worker")
                    data = await cmd.model.fetch(item)
                    log(f"Got {len(data)} items")
                else:
                    log("refreshing current context synchronously")
                    data = cmd.model.fetch(item)

            # Create new context
            log(f'creating new context for "{cmd_str}" with {len(data)} items')
            ctx = CommandContext(command=cmd, data=data, item=item, operation="fetch")
            if is_global:
                self.stack = [ctx]
                cmd_text = f"{cmd_str[0:2].upper()}{cmd_str[2:]}"
                self.app.breadcrumbs_text = [f"{cmd_text}"]
                self.app.breadcrumbs.update(" ".join(self.app.breadcrumbs_text))
            else:
                self.stack.append(ctx)
                self.app.breadcrumbs_text.append(f"{cmd_str}")
                self.app.breadcrumbs.update(" ".join(self.app.breadcrumbs_text))

            self.refresh_output()
            await self.refresh_current_context()
        else:
            self.app.notify(f'Command "{cmd_str}" not found')

    # TODO: deduplicate output/hover
    def refresh_output(self):
        log("refreshing output")
        if not self.stack:
            return

        ctx = self.stack[-1]
        data = ctx.data
        self.output_container.remove_children()
        if isinstance(data, str):
            detail = Static(data, markup=False, classes="detail")
            detail.focus()
            self.output_container.mount(detail)
            return

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
            if isinstance(data[0], BaseModel):
                # model = ctx.command.model
                # fields = ctx.command.visible_fields or model.model_fields.keys()
                # fields = ctx.command.visible_fields or model.model_fields.keys()

                model = data[0].__class__
                # fields = ctx.command.visible_fields or model.model_fields.keys()
                if hasattr(model, "nines_config"):
                    fields = model.nines_config.get(
                        "visible_fields", model.model_fields.keys()
                    )
                else:
                    fields = model.model_fields.keys()

                table = VimmyDataTable()
                table.cursor_type = "row"
                table.show_cursor = True
                table.focus()
                table.add_columns(*fields)

                for i, item in enumerate(data):
                    table.add_row(*(str(getattr(item, f, "")) for f in fields), key=i)

                self.output_container.mount(table)
                self.app.output = table
                self.app.assign_sort_hotkeys(fields)
            if isinstance(data[0], str):
                self.output_container.mount(Static("\n".join(data), classes="detail"))
                self.app.output = self.output_container
                return

    def refresh_hover(self, data=None):
        self.hover_container.remove_children()

        if not data:
            self.hover_container.display = False
            self.app.action_hide_hover()
            return

        from rich.console import RenderableType

        if isinstance(data, RenderableType):
            detail = Static(data, markup=False, classes="hover-detail")
            self.hover_container.mount(detail)
            return

        if isinstance(data, str):
            detail = Static(data, markup=False, classes="hover-detail")
            detail.focus()
            self.hover_container.mount(detail)
            # self.hover_container.display = True
            return

        if isinstance(data, BaseModel):
            if hasattr(data, "render") and callable(data.render):
                detail = Static(data.render(), markup=False, classes="hover-detail")
            else:
                from rich.pretty import Pretty

                detail = Static(Pretty(data), markup=False, classes="hover-detail")

            self.hover_container.mount(detail)
            # self.hover_container.display = True
            return

        if isinstance(data, list):
            if isinstance(data[0], BaseModel):
                model = data[0].__class__
                # fields = ctx.command.visible_fields or model.model_fields.keys()
                if hasattr(model, "nines_config"):
                    fields = model.nines_config.get(
                        "visible_fields", model.model_fields.keys()
                    )
                else:
                    fields = model.model_fields.keys()

                table = VimmyDataTable()
                table.cursor_type = "row"
                table.show_cursor = True
                table.focus()
                table.add_columns(*fields)

                for i, item in enumerate(data):
                    table.add_row(*(str(getattr(item, f, "")) for f in fields), key=i)

                self.hover_container.mount(table)
            if isinstance(data[0], str):
                self.hover_container.mount(Static("\n".join(data), classes="detail"))
                # self.hover_container.display = True
                return

    def drill_in(self):
        ctx = self.stack[-1]
        index = self.highlighted_index
        if hasattr(ctx.data, "__len__") and index >= len(ctx.data):
            return
        if hasattr(ctx, "data") and hasattr(ctx.data, "__len__"):
            item = ctx.data[index]
        else:
            item = ctx.data
        if not hasattr(item, "drill"):
            if hasattr(ctx, "data") and hasattr(ctx.data, "__len__"):
                ctx = CommandContext(command=ctx.command, data=item, operation="drill")
                self.stack.append(ctx)

                self.app.breadcrumbs_text.append(
                    f"{ctx.operation_symbol}{item.__class__.__name__}"
                )
                self.app.breadcrumbs.update(" ".join(self.app.breadcrumbs_text))

                self.app.action_show_hover()
                self.refresh_output()
                self.refresh_hover()
            else:
                self.app.notify(f"{item.__class__.__name__} has no drill")
            return
        if ctx.command.model.drill:
            log(f"drilling into {item}:{type(item)}")
            # result = ctx.command.drill_fn(item)
            result = item.drill()
            ctx = CommandContext(
                command=ctx.command, data=result, item=item, operation="drill"
            )
            self.stack.append(ctx)

            self.app.breadcrumbs_text.append(
                f"{ctx.operation_symbol}{item.__class__.__name__}"
            )
            self.app.breadcrumbs.update(" ".join(self.app.breadcrumbs_text))
            self.refresh_output()
            self.refresh_hover()

    async def on_key(self, event):
        log(f"event.key: {event.key}")
        key = event.key
        if len(self.stack) == 0:
            log("no stack")
            return
        ctx = self.stack[-1]
        index = self.highlighted_index
        if (
            hasattr(ctx, "data")
            and hasattr(ctx.data, "__len__")
            and index >= len(ctx.data)
        ):
            log("index out of range")
            return
        try:
            log(f"index: {index}")
            item = ctx.data[index]
            log(f"item: {item}")
        except TypeError:
            item = ctx.data
            log(f"got TypeError, item: {item}")

        if hasattr(item, "nines_config"):
            if key in item.nines_config.get("bindings", {}):
                log(f"binding {key} to {item.nines_config['bindings'][key]}")
                func = item.nines_config["bindings"][key]
                result = getattr(item, func)()
                if result is None:
                    await self.refresh_current_context()
                    return
                ctx = CommandContext(
                    command=ctx.command, data=result, operation="drill"
                )
                self.stack.append(ctx)

                self.app.breadcrumbs_text.append(
                    f"{ctx.operation_symbol}{item.__class__.__name__}"
                )
                self.app.breadcrumbs.update(" ".join(self.app.breadcrumbs_text))
                self.refresh_output()
        else:
            log(f"no binding for {key}")

    async def refresh_current_context(self):
        ctx = self.stack[-1]
        from hashlib import md5

        original_data_hash = md5(str(ctx.data).encode("utf-8")).hexdigest()
        if ctx.operation == "fetch":
            if inspect.iscoroutinefunction(ctx.command.model.fetch):
                log("refreshing current context in worker")
                # data = self.app.run_worker(ctx.command.model.fetch, ctx.item)
                data = await ctx.command.model.fetch(ctx.item)
            else:
                log("refreshing current context synchronously")
                data = ctx.command.model.fetch(ctx.item)
            self.stack[-1].data = data
            current_data_hash = md5(str(data).encode("utf-8")).hexdigest()
            if current_data_hash != original_data_hash:
                self.refresh_output()

    def jump_owner(self):
        ctx = self.stack[-1]
        item = ctx.data[self.highlighted_index]
        if ctx.command.jump_fn:
            result = ctx.command.jump_fn(item)
            self.stack.append(
                CommandContext(command=ctx.command, data=result, operation="jump")
            )
            self.app.breadcrumbs_text.append(
                f"{ctx.operation_symbol}{item.__class__.__name__}"
            )
            self.app.breadcrumbs.update(" ".join(self.app.breadcrumbs_text))
            self.refresh_output()
            self.refresh_output()

    async def go_back(self):
        self.refresh_hover()
        if len(self.stack) > 1:
            self.stack.pop()
            self.refresh_output()
            self.app.breadcrumbs_text.pop()
            self.app.breadcrumbs.update(" ".join(self.app.breadcrumbs_text))
            await self.refresh_current_context()
            return True

        return False


# =========================== ninesui/core/views.py ===========================


class Header(Static):
    def __init__(self, metadata: dict):
        title = metadata.get("title", "")
        subtitle = metadata.get("subtitle", "")
        hotkeys = metadata.get("hotkeys", "")
        super().__init__(f"{title} | {subtitle} | {hotkeys}")


class MetaHeader(Static):
    def __init__(self, metadata: dict):
        title = metadata.get("title", "")
        subtitle = metadata.get("subtitle", "")
        hotkeys = metadata.get("hotkeys", "")
        super().__init__(f"{title} — {subtitle} | {hotkeys}")


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
        Binding("/", "focus_search", "Command"),
        Binding("h", "toggle_hover", "Hover"),
        Binding("a", "layout_wide", "Layout wide"),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(
        self,
        metadata: dict,
        commands: CommandSet,
        command_bindings: Optional[dict] = None,
        refresh_interval: Optional[int] = 10,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.router = Router(self, commands)
        default_commands = [
            command.name for command in commands.commands.values() if command.is_default
        ]
        if default_commands:
            self.default_command = default_commands[0]
        else:
            self.default_command = None

        self.metadata = metadata
        self.breadcrumbs = Static()
        self.breadcrumbs_text = []
        # self.command_input = Input(placeholder=":command")
        self.command_input = Input(
            placeholder=":command",
            suggester=SuggestFromList(
                [
                    *commands.commands.keys(),
                    *[command.strip(":") for command in commands.commands.keys()],
                ],
                case_sensitive=False,
            ),
        )
        self.command_mode = "command"
        self.output = VimmyDataTable()
        self.hover = Static()

        self.meta_header = MetaHeader(metadata)
        self.body_container = Container(id="body-container")
        self.output_container = Container(self.output, id="output-container")
        self.hover_container = Container(self.hover, id="hover-container")
        self.popup_container = Container(Static(), id="popup-container")
        self.header_container = Container(Static(), id="header-container")
        self._dynamic_sort_keys = {}  # key: sort function
        self._last_sort = {"key": None, "reverse": False}
        self.dynamic_bindings = command_bindings or {}
        self.refresh_interval = refresh_interval

    def compose(self) -> ComposeResult:
        yield self.meta_header
        yield self.breadcrumbs
        yield self.command_input
        with self.body_container:
            yield self.output_container
            yield self.hover_container
        yield Footer()

    def action_toggle_hover(self):
        self.hover_container.display = not self.hover_container.display
        self.output_container.toggle_class("span-2")

    def action_hide_hover(self):
        self.hover_container.display = False
        self.output_container.add_class("span-2")

    def action_show_hover(self):
        self.hover_container.display = True
        self.output_container.remove_class("span-2")

    def action_layout_wide(self):
        self.body_container.toggle_class("layout-wide")

    async def action_refresh(self):
        await self.router.refresh_current_context()

    async def on_mount(self):
        self.theme = "tokyo-night"
        self.command_input.display = False
        self.router.set_output_widget(self.output_container)
        self.router.set_hover_widget(self.hover_container)
        self.router.set_popup_widget(self.popup_container)
        self.router.set_header_widget(self.header_container)
        # self.hover_container.display = False
        self.output.cursor_type = "row"
        self.output.show_cursor = True
        self.output.focus()
        await self.router.push_command(":commands")
        if self.default_command:
            await self.router.push_command(self.default_command)
        self.set_interval(self.refresh_interval, self.refresh_current_context)

    async def refresh_current_context(self):
        if self.command_input.has_focus:
            return
        await self.router.refresh_current_context()

    def action_focus_command(self):
        self.command_input.display = True
        self.command_input.placeholder = ":command"
        self.command_mode = "command"
        self.command_input.focus()

    def action_focus_search(self):
        self.command_input.display = True
        self.command_input.placeholder = "/search"
        self.command_mode = "search"
        self.command_input.focus()

    async def action_go_back_or_quit(self):
        if self.command_input.has_focus:
            self.command_input.blur()
            self.command_input.display = False
        back = await self.router.go_back()
        if not back:
            self.exit()

    async def on_input_submitted(self, message: Input.Submitted):
        if self.command_mode == "search":
            query = message.value
            self.command_input.value = ""
            self.command_input.display = False
            self.command_input.blur()
            self.router.push_search(query)
            return
        cmd = self.command_input.value
        self.command_input.value = ""
        self.command_input.display = False
        self.command_input.blur()
        # Add the : prefix if not present
        if not cmd.startswith(":"):
            cmd = f":{cmd}"
        await self.router.push_command(cmd)

    def on_data_table_row_highlighted(self, message: VimmyDataTable.RowHighlighted):
        if message.row_key is None:
            self.app.notify("no data to iterate over")
            return
        self.router.highlighted_index = message.row_key.value

        ctx = self.router.stack[-1]
        item = ctx.data[self.router.highlighted_index]

        if hasattr(item, "hover"):
            if callable(item.hover):
                import inspect

                if inspect.iscoroutinefunction(item.hover):
                    self.run_worker(self.update_hover(item))
                else:
                    result = item.hover()
                    self.router.refresh_hover(result)

    async def update_hover(self, item):
        log("updating hover")
        result = await item.hover()
        log(f"result: {result}")
        self.router.refresh_hover(result)

    def on_data_table_row_selected(self, message: VimmyDataTable.RowSelected):
        self.router.drill_in()

    async def on_key(self, event):
        key = event.key
        if SCREENKEY:
            self.notify(f"key: {key}", timeout=2, severity="key")

        if key == "J":
            self.router.jump_owner()
        elif key == "enter":
            if not self.command_input.has_focus:
                log("enter pressed without command input focus")
                self.router.drill_in()
            else:
                log("enter pressed with command input focus")
                await self.on_input_submitted(self.command_input)
        elif key in self._dynamic_sort_keys:
            self._dynamic_sort_keys[key]()
        else:
            await self.router.on_key(event)

        if key in self.dynamic_bindings:
            await self.router.push_command(self.dynamic_bindings[key])

        # await self.router.refresh_current_context()

    def search(self, query):
        ctx = self.router.stack[-1]
        import copy

        ctx = copy.deepcopy(ctx)
        ctx.data = [item for item in ctx.data if query in str(item)]
        self.router.stack.append(ctx)
        self.notify(f'Searching for "{query}"')
        self.breadcrumbs_text.append(f"/{query}")
        self.breadcrumbs.update(" ".join(self.breadcrumbs_text))
        self.router.refresh_output()

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

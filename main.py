# =========================== apps/filesystem/models.py ===========================
import os
from pydantic import BaseModel
from pathlib import Path
from rich.syntax import Syntax
from ninesui import CommandSet, Command, NinesUI
from textual import log


class FileEntry(BaseModel):
    name: str
    path: str
    is_dir: bool

    def render(self):
        syntax = Syntax.from_path(self.path)
        return syntax
        # return Path(self.path).read_text()


class DiskEntry(BaseModel):
    device: str  # e.g. /dev/sda1
    mountpoint: str  # e.g. / or /home
    fstype: str  # e.g. ext4, vfat
    total: int  # in bytes
    used: int
    free: int
    percent: float

    def render(self):
        import shutil
        from rich.table import Table

        table = Table(title=f"Disk Info for {self.device}")
        table.add_column("Field")
        table.add_column("Value")
        table.add_row("Device", self.device)
        table.add_row("Mountpoint", self.mountpoint)
        table.add_row("Filesystem", self.fstype)
        table.add_row(
            "Total",
            shutil._ntuple_diskusage(
                (self.total, self.used, self.free)
            ).total.__str__(),
        )
        table.add_row("Used", f"{self.used} bytes")
        table.add_row("Free", f"{self.free} bytes")
        table.add_row("Used %", f"{self.percent:.1f}%")
        return table


import psutil
# from .models import DiskEntry


def list_disks(ctx=None) -> list[DiskEntry]:
    entries = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except PermissionError:
            continue
        entries.append(
            DiskEntry(
                device=part.device,
                mountpoint=part.mountpoint,
                fstype=part.fstype,
                total=usage.total,
                used=usage.used,
                free=usage.free,
                percent=usage.percent,
            )
        )
    return entries


# =========================== apps/filesystem/config.py ===========================

current_path = os.getcwd()


def list_dir(path: str = None) -> list[FileEntry]:
    target_path = path if path is not None else current_path
    return [
        FileEntry(name=e.name, path=str(e), is_dir=e.is_dir())
        for e in Path(target_path).iterdir()
    ]


def drill(entry: FileEntry):
    if entry.is_dir:
        log("entry is a dir")
        return list_dir(entry.path)
    try:
        content = Path(entry.path).read_text(errors="ignore")
    except Exception as e:
        content = f"<< ERROR: {e} >>"
    return FileEntry(name=entry.name, path=entry.path, is_dir=False)


def jump(entry: FileEntry):
    parent = str(Path(entry.path).parent)
    return list_dir(parent)


def get_current_path(ctx=None) -> str:
    log(f"Getting current path with context: {ctx}")
    if ctx and ctx.data:
        # If we're viewing a single file, use its parent directory
        if isinstance(ctx.data, FileEntry):
            path = ctx.data.path
            result = str(Path(path).parent)
            log(f"Using file's parent directory: {result}")
            return result
        # If we have a list of items, use their directory
        elif isinstance(ctx.data, list) and ctx.data:
            if isinstance(ctx.data[0], DiskEntry):
                path = ctx.data[0].mountpoint
            elif isinstance(ctx.data[0], FileEntry):
                path = ctx.data[0].path
            else:
                path = os.getcwd()
            result = str(Path(path).parent)
            log(f"Using list context path: {result}")
            return result
        elif isinstance(ctx.data, DiskEntry):
            return ctx.data.mountpoint
    log(f"Using default current_path: {current_path}")
    return current_path


def list_with_context(ctx=None) -> list[FileEntry]:
    path = get_current_path(ctx)
    log(f"Listing directory with path: {path}")
    return list_dir(path)


def drill_disk(entry: DiskEntry):
    # Treat as a folder view
    return list_dir(entry.mountpoint)


def jump_disk(entry: DiskEntry):
    # Return to list of disks
    return list_disks()


class DiskUsageEntry(BaseModel):
    name: str
    path: str
    size_bytes: int
    is_dir: bool


def get_disk_usage(path: str) -> int:
    total = 0
    for root, dirs, files in os.walk(path, onerror=lambda e: None):
        for f in files:
            try:
                fp = os.path.join(root, f)
                total += os.path.getsize(fp)
            except Exception:
                continue
    return total


def drill_du(entry: DiskUsageEntry):
    if entry.is_dir:
        return list_du(entry.path)
    return entry  # show size info


def jump_du(entry: DiskUsageEntry):
    return list_du(str(Path(entry.path).parent))


def list_du(ctx=None) -> list[DiskUsageEntry]:
    path = os.getcwd()
    entries = []
    for entry in Path(path).iterdir():
        try:
            size = (
                get_disk_usage(str(entry)) if entry.is_dir() else entry.stat().st_size
            )
            entries.append(
                DiskUsageEntry(
                    name=entry.name,
                    path=str(entry),
                    size_bytes=size,
                    is_dir=entry.is_dir(),
                )
            )
        except Exception:
            continue
    return entries


class DiskUsage(Command):
    def __init__(self):
        super().__init__(
            name="disk-usage",
            aliases=["du"],
            model=DiskUsageEntry,
            # fetch_fn=list_du,
            # drill_fn=drill_du,
            # jump_fn=jump_du,
            visible_fields=["name", "size_bytes", "is_dir"],
        )

    def fetch_fn(self, ctx=None):
        return list_du(ctx)

    def drill_fn(self, entry: DiskUsageEntry):
        if entry.is_dir:
            return list_du(entry.path)
        return entry

    def jump_fn(self, entry: DiskUsageEntry):
        return list_du(str(Path(entry.path).parent))


commands = CommandSet(
    [
        Command(
            name="list",
            aliases=["ls"],
            model=FileEntry,
            fetch_fn=list_with_context,
            drill_fn=drill,
            jump_fn=jump,
            visible_fields=["name", "path", "is_dir"],
        ),
        Command(
            name="disks",
            aliases=["disk", "ld"],
            model=DiskEntry,
            fetch_fn=list_disks,
            drill_fn=drill_disk,
            jump_fn=jump_disk,
            visible_fields=["device", "mountpoint", "fstype", "percent"],
        ),
        Command(
            name="disk-usage",
            aliases=["du"],
            model=DiskUsageEntry,
            fetch_fn=list_du,
            drill_fn=drill_du,
            jump_fn=jump_du,
            visible_fields=["name", "size_bytes", "is_dir"],
        ),
    ]
)


metadata = {
    "title": "Filesystem Viewer",
    "subtitle": "Use :list to list files. Enter to drill in. Shift+J to go up.",
}


# =========================== __main__.py ===========================
if __name__ == "__main__":
    ui = NinesUI(metadata=metadata, commands=commands)
    ui.run()

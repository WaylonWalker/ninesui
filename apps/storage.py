import psutil
from typing import ClassVar
import os
from pydantic import BaseModel
from pathlib import Path
from rich.syntax import Syntax
from ninesui import CommandSet, Command, NinesUI
from textual import log

current_path = os.getcwd()


class FileEntry(BaseModel):
    name: str
    path: str
    is_dir: bool

    nines_config: ClassVar[dict] = {
        "visible_fields": [
            "name",
            "is_dir",
            "path",
        ]
    }

    def render(self):
        syntax = Syntax.from_path(self.path)
        return syntax
        # return Path(self.path).read_text()

    @classmethod
    def drill(cls, entry):
        if entry.is_dir:
            log("entry is a dir")
            log(entry.path)
            return cls.list_dir(entry.path)
        try:
            content = Path(entry.path).read_text(errors="ignore")
        except Exception as e:
            content = f"<< ERROR: {e} >>"
        return FileEntry(name=entry.name, path=entry.path, is_dir=False)

    @classmethod
    def jump(cls, entry):
        log(f"Jumping to parent of {entry.path}")
        parent = str(Path(entry.path).parents[1])
        return cls.list_dir(parent)

    def get_current_path(self, ctx=None) -> str:
        if ctx and ctx.data:
            # If we're viewing a single file, use its parent directory
            if isinstance(ctx.data, FileEntry):
                path = ctx.data.path
                result = str(Path(path).parent)
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
                return result
            elif isinstance(ctx.data, DiskEntry):
                return ctx.data.mountpoint
        return current_path

    @classmethod
    def fetch(cls, ctx=None):
        path = cls.get_current_path(ctx)
        log(f"Listing directory with path: {path}")
        return cls.list_dir(path)

    @classmethod
    def list_dir(self, path: str = None):
        target_path = path if path is not None else current_path
        return [
            FileEntry(name=e.name, path=str(e), is_dir=e.is_dir())
            for e in Path(target_path).iterdir()
        ]


class DiskEntry(BaseModel):
    device: str  # e.g. /dev/sda1
    mountpoint: str  # e.g. / or /home
    fstype: str  # e.g. ext4, vfat
    total: int  # in bytes
    used: int
    free: int
    percent: float

    nines_config: ClassVar[dict] = {
        "visible_fields": [
            "device",
            "mountpoint",
            "fstype",
            "total",
            "used",
            "free",
            "percent",
        ]
    }

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

    def fetch(self, ctx=None):
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

    @classmethod
    def drill(cls, entry):
        # Treat as a folder view
        return FileEntry().fetch(entry.mountpoint)


class DiskUsageEntry(BaseModel):
    name: str
    path: str
    size_bytes: int
    is_dir: bool

    def get_disk_usage(self, path: str) -> int:
        total = 0
        if path is None:
            path = self.path
        for root, dirs, files in os.walk(path, onerror=lambda e: None):
            for f in files:
                try:
                    fp = os.path.join(root, f)
                    total += os.path.getsize(fp)
                except Exception:
                    continue
        return total

    def jump_disk(entry: DiskEntry):
        # Return to list of disks
        return list_disks()

    def drill(self):
        if self.is_dir:
            return list_du(self.path)
        return self

    def jump(self):
        return self.list(str(Path(self.path).parent))

    def fetch(ctx=None):
        path = os.getcwd()
        entries = []
        for entry in Path(path).iterdir():
            try:
                size = (
                    self.get_disk_usage(str(entry))
                    if entry.is_dir()
                    else entry.stat().st_size
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


commands = CommandSet(
    [
        Command(
            name="list",
            aliases=["ls"],
            model=FileEntry,
        ),
        Command(
            name="disks",
            aliases=["disk", "ld"],
            model=DiskEntry,
        ),
        Command(
            name="disk-usage",
            aliases=["du"],
            model=DiskUsageEntry,
        ),
    ]
)


metadata = {
    "title": "Filesystem Viewer",
    "subtitle": "Use :list to list files. Enter to drill in. Shift+J to go up.",
}


if __name__ == "__main__":
    ui = NinesUI(metadata=metadata, commands=commands)
    ui.run()

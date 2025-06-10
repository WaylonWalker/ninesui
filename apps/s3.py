#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "boto3",
#     "ninesui @ git+https://github.com/waylonwalker/ninesui.git",
# ]
# ///
from typing import Optional
from pydantic import BaseModel
from ninesui import CommandSet, NinesUI
from ninesui import Command
from typing import List
from datetime import datetime
from typing import Any
import boto3
from botocore.exceptions import BotoCoreError, ClientError


class S3Object(BaseModel):
    key: str
    size: int
    last_modified: datetime
    storage_class: Optional[str] = None


class Object(BaseModel):
    name: str

    @classmethod
    def fetch(
        cls,
        name: str,
        ctx: Optional[Any] = None,
        aws_region: Optional[str] = None,
        aws_profile: Optional[str] = None,
    ) -> List[S3Object]:
        """
        List objects in the given bucket.
        If ctx is provided and has a .path attribute, use that as the prefix.
        """
        session_kwargs = {}
        if aws_profile:
            session_kwargs["profile_name"] = aws_profile
        session = boto3.Session(**session_kwargs)
        s3 = session.client("s3", region_name=aws_region)

        prefix = getattr(ctx, "path", None) or ""
        paginator = s3.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=name, Prefix=prefix)

        objects: List[S3Object] = []
        try:
            for page in page_iterator:
                for obj in page.get("Contents", []):
                    objects.append(
                        S3Object(
                            key=obj["Key"],
                            size=obj["Size"],
                            last_modified=obj["LastModified"],
                            storage_class=obj.get("StorageClass"),
                        )
                    )
        except (BotoCoreError, ClientError) as e:
            raise RuntimeError(f"Error listing objects in bucket {name}: {e}")

        return objects


class Bucket(BaseModel):
    name: str

    @classmethod
    def fetch(cls, ctx=None):
        session = boto3.Session()
        s3 = session.client("s3")
        buckets = s3.list_buckets()["Buckets"]
        return [Bucket(name=b["Name"]) for b in buckets]


commands = CommandSet(
    [
        Command(
            name="bucket",
            aliases=["b"],
            model=Bucket,
            is_default=True,
        ),
    ]
)

command_bindings = {
    "b": "Person",
}

metadata = {
    "title": "S3 Viewer",
    "subtitle": "Use :bucket to list buckets. Enter to drill in. Shift+J to go up.",
}


if __name__ == "__main__":
    ui = NinesUI(
        metadata=metadata, commands=commands, command_bindings=command_bindings
    )
    ui.run()

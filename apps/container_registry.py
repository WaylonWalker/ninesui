from typing import List, Optional
from httpx import BasicAuth
from pydantic import BaseModel
import os
from ninesui import CommandSet, Command, NinesUI
import httpx


class Image(BaseModel):
    name: str
    latest: str

    @classmethod
    def fetch(
        cls,
        registry_url: Optional[str] = None,
    ) -> List["Image"]:
        """
        Fetches the list of repositories (images) in the registry.
        """
        registry_url = (
            registry_url or os.environ.get("REGISTRY_URL") or "http://localhost:5000"
        )
        url = f"{registry_url}/v2/_catalog"
        username = os.environ.get("REGISTRY_USERNAME")
        password = os.environ.get("REGISTRY_PASSWORD")
        auth = BasicAuth(username=username, password=password)
        response = httpx.get(url, auth=auth)
        response.raise_for_status()
        data = response.json()
        repo_names = data.get("repositories", [])
        repos = []

        for name in repo_names:
            tags = Tag.fetch(name)
            versions = [t.tag for t in tags]
            semver_versions = [v for v in versions if v.replace(".", "").isnumeric()]
            if semver_versions:
                sorted_versions = sorted(semver_versions, reverse=True)
            else:
                sorted_versions = versions

            repos.append(cls(name=name, latest=sorted_versions[0]))
        return repos

    def drill(self, ctx=None):
        return Tag.fetch(self.name)


class Tag(BaseModel):
    image: str
    tag: str

    @classmethod
    def fetch(
        cls,
        image_name: str,
        registry_url: Optional[str] = None,
    ) -> List["Tag"]:
        """
        Fetches list of tags for a given image (repository).
        """
        registry_url = (
            registry_url or os.environ.get("REGISTRY_URL") or "http://localhost:5000"
        )
        url = f"{registry_url}/v2/{image_name}/tags/list"
        username = os.environ.get("REGISTRY_USERNAME")
        password = os.environ.get("REGISTRY_PASSWORD")
        auth = BasicAuth(username=username, password=password)
        response = httpx.get(url, auth=auth)
        response.raise_for_status()
        data = response.json()
        tag_names = data.get("tags") or []
        # return [name=image_name, tags=[cls(name=t) for t in tag_names]]
        return [cls(tag=t, image=image_name) for t in tag_names]

    def drill(self, ctx=None):
        return Manifest.fetch(self.image, self.tag)


class Layer(BaseModel):
    mediaType: str
    size: int
    digest: str


class Manifest(BaseModel):
    schemaVersion: int
    mediaType: Optional[str]
    config: Optional[dict]
    layers: List[Layer]

    @classmethod
    def fetch(
        cls,
        image_name: str,
        tag: str,
        registry_url: Optional[str] = None,
    ) -> "Manifest":
        """
        Fetches and parses the manifest for a specific image:tag.
        """
        registry_url = (
            registry_url or os.environ.get("REGISTRY_URL") or "http://localhost:5000"
        )
        url = f"{registry_url}/v2/{image_name}/manifests/{tag}"
        headers = {"Accept": "application/vnd.docker.distribution.manifest.v2+json"}
        response = httpx.get(url, headers=headers)
        username = os.environ.get("REGISTRY_USERNAME")
        password = os.environ.get("REGISTRY_PASSWORD")
        auth = BasicAuth(username=username, password=password)
        response = httpx.get(url, auth=auth, headers=headers)
        response.raise_for_status()
        data = response.json()
        return cls(**data)


commands = CommandSet(
    [
        Command(
            name="images",
            aliases=["i", "image"],
            model=Image,
            is_default=True,
        ),
    ]
)

metadata = {
    "title": "Git Viewer",
    "subtitle": "Use :list to list files. Enter to drill in. Shift+J to go up.",
}


if __name__ == "__main__":
    ui = NinesUI(
        metadata=metadata,
        commands=commands,
        command_bindings={"i": "Images"},
    )
    ui.run()

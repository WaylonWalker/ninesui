#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx",
#     "ninesui @ git+https://github.com/waylonwalker/ninesui.git",
#     "beautifulsoup4",
#     "rich",
#     "pydantic",
#     "dateparser",
# ]
# ///
from datetime import datetime
from typing import List, Optional

from ninesui import CommandSet, Command, NinesUI
import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, HttpUrl
from rich.console import RenderableType
from rich.markdown import Markdown
from rich.panel import Panel
import dateparser


class Article(BaseModel):
    title: str
    link: Optional[HttpUrl] = None
    date: datetime
    excerpt: str
    image: Optional[HttpUrl] = None

    @classmethod
    def fetch(
        cls,
        ctx=None,
        # feed_url: str = "https://reader.waylonwalker.com/",
    ) -> List["Article"]:
        """
        Scrape the RSS‐reader landing page and return a list of Article models.
        """
        feed_url: str = "https://reader.waylonwalker.com/"
        resp = httpx.get(feed_url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        articles: List[Article] = []
        for li in soup.select("ul.feed > li"):
            # pull out the bits
            title_el = li.select_one("h2")
            link_el = li.select_one("a[href]")
            date_el = li.select_one("time")
            # excerpt_el = li.select_one("section.excerpt")
            excerpt_el = li.select_one("section")
            img_el = li.select_one("figure img")

            if not (title_el and link_el and date_el and excerpt_el):
                continue

            try:
                date = datetime.fromisoformat(date_el["datetime"])
            except ValueError:
                date = dateparser.parse(date_el.get_text(strip=True))

            articles.append(
                cls(
                    title=title_el.get_text(strip=True),
                    link=link_el["href"],
                    date=date,
                    excerpt=excerpt_el.get_text(" ", strip=True),
                    image=img_el["src"] if img_el else None,
                )
            )

        return articles

    def drill(self):
        import webbrowser

        webbrowser.open(str(self.link))

    async def hover(self) -> RenderableType:
        """
        Fetch the full article page and return a Rich renderable
        that includes images, blockquotes, codeblocks, and paragraphs.
        """
        async with httpx.AsyncClient() as client:
            resp = await client.get(str(self.link))
            resp.raise_for_status()
        page = BeautifulSoup(resp.text, "html.parser")

        body = page.select_one("article") or page
        parts: list[str] = []

        # walk through relevant tags in document order
        for el in body.find_all(["p", "img", "blockquote", "pre"], recursive=True):
            if el.name == "p":
                text = el.get_text(strip=True)
                if text:
                    parts.append(text)

            elif el.name == "img":
                src = el.get("src")
                alt = el.get("alt", "")
                parts.append(f"![{alt}]({src})")

            elif el.name == "blockquote":
                quote = el.get_text(strip=True).splitlines()
                for line in quote:
                    parts.append(f"> {line}")

            elif el.name == "pre":
                # assume a <code> child
                code_tag = el.code or el
                code_text = code_tag.get_text()
                # if there's a class like language-python, use it
                cls = ""
                if code_tag.has_attr("class"):
                    langs = [c for c in code_tag["class"] if c.startswith("language-")]
                    if langs:
                        cls = langs[0].split("-", 1)[1]
                fence = f"```{cls}" if cls else "```"
                parts.append(f"{fence}\n{code_text.rstrip()}\n```")

        markdown_source = f"# {self.title}\n\n" + "\n\n".join(parts)
        md = Markdown(markdown_source)

        return Panel(
            md,
            title=self.date.strftime("%Y-%m-%d"),
            subtitle=str(self.link),
            expand=True,
        )


commands = CommandSet(
    [
        Command(
            name="feed",
            aliases=["article"],
            model=Article,
            is_default=True,
        ),
    ]
)

metadata = {
    "title": "Reader",
    "subtitle": "Use :list to list files. Enter to drill in. Shift+J to go up.",
}


if __name__ == "__main__":
    ui = NinesUI(
        metadata=metadata,
        commands=commands,
    )
    ui.run()

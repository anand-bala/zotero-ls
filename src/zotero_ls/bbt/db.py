"""Access the sqlite database created by BetterBibTeX"""

import dataclasses
import urllib.parse
from collections.abc import AsyncIterable
from dataclasses import dataclass
from pathlib import Path

import pydantic
from sqlalchemy import Index, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column
from typing_extensions import final


class Base(  # pyright: ignore[reportUnsafeMultipleInheritance]
    MappedAsDataclass,
    DeclarativeBase,
    dataclass_callable=pydantic.dataclasses.dataclass,
):
    pass


@final
class _CitationKeyEntry(Base):
    """
    ```sql
    CREATE TABLE citationkey (
        itemID NOT NULL PRIMARY KEY,
        itemKey NOT NULL,
        libraryID NOT NULL,
        citationKey NOT NULL CHECK (citationKey <> ''),
        pinned CHECK (pinned in (0, 1)),
        UNIQUE (libraryID, itemKey)
    )
    ```
    """

    item_id: Mapped[int] = mapped_column("itemID", primary_key=True)
    key: Mapped[str] = mapped_column("itemKey", unique=True)
    library_id: Mapped[str] = mapped_column("libraryID", unique=True)
    citation_key: Mapped[str] = mapped_column("citationKey")
    pinned: Mapped[bool] = mapped_column()

    __tablename__ = "citationkey"
    __table_args__ = (
        # CREATE INDEX citationkey_citationkey ON citationkey(citationKey)
        Index("citationkey_citationkey", "citationKey"),
        # CREATE INDEX citationkey_itemKey ON citationkey(itemKey)
        Index("citationkey_itemKey", "itemKey"),
        # CREATE INDEX citationkey_libraryID_itemKey ON citationkey(libraryID, itemKey)
        Index("citationkey_libraryID_itemKey", "libraryID", "itemKey"),
    )


@dataclass
class CitationKey:
    key: str
    zotero_key: str
    library_id: int | str = 1


@dataclass
class Database:
    path: Path
    engine: AsyncEngine = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        db_path = Path(self.path)
        db_args = urllib.parse.urlencode(dict(mode="ro", nolock=1, uri="true"))

        db_uri = f"file:{db_path.absolute()}?{db_args}"
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{db_uri}", echo=True)

    async def fetch_citekeys(self, *, buffer_size: int = 200) -> AsyncIterable[tuple[str, CitationKey]]:
        async with AsyncSession(self.engine) as session:
            statement = select(_CitationKeyEntry).execution_options(yield_per=buffer_size)
            rows = await session.stream_scalars(statement)
            async for row in rows:
                yield (row.key, CitationKey(row.citation_key, row.key, row.library_id))


if __name__ == "__main__":
    import asyncio

    import rich

    loop = asyncio.new_event_loop()

    async def main() -> None:
        db_path = Path.home() / "Zotero/better-bibtex.sqlite"
        db = Database(db_path)

        results = {key: val async for (key, val) in db.fetch_citekeys()}
        rich.print(results)

    loop.run_until_complete(main())

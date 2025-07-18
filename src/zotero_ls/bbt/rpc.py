"""Fetch information from a running intance of Better BibTeX"""

from __future__ import annotations

import asyncio
import enum
from dataclasses import dataclass, field

import aiohttp
from pydantic import BaseModel, JsonValue, TypeAdapter

from zotero_ls.json_rpc import JsonRpcClient


class Translators(enum.StrEnum):
    BIBTEX = "Better BibTeX"
    BIBLATEX = "Better BibLaTeX"
    BIBTEX_CITATION_KEY = "Better BibTeX Citation Key Quick Copy"
    CSL_JSON = "Better CSL JSON"
    CSL_YAML = "Better CSL YAML"
    JSON = "BetterBibTeX JSON"


class ReadyResponse(BaseModel):
    """The Zotero and BetterBibTeX version to show the JSON-RPC API is ready."""

    betterbibtex: str
    zotero: str


class ScanAuxResponse(BaseModel): ...


ExportItemsAdapter: TypeAdapter = TypeAdapter(tuple[list[str], Translators, None | str] | tuple[list[str], Translators])  # pyright: ignore[reportMissingTypeArgument]


@dataclass
class Client:
    """Client for the BetterBibTeX JSON-RPC API"""

    rpc: JsonRpcClient = field(
        default_factory=lambda: JsonRpcClient(
            aiohttp.ClientSession(
                base_url="http://127.0.0.1:23119/",
            )
        )
    )

    @classmethod
    def make_juris_m(cls) -> Client:
        return Client(
            JsonRpcClient(
                aiohttp.ClientSession(
                    base_url="http://127.0.0.1:24119/",
                )
            )
        )

    async def _send(self, method: str, data: None | list[JsonValue] = None) -> JsonValue | None:
        return await self.rpc.send_request("/better-bibtex/json-rpc", method=method, data=data)

    async def is_ready(self) -> ReadyResponse:
        response = await self._send("api.ready", None)
        return ReadyResponse.model_validate(response)

    async def export_items(self, citekeys: list[str], translator: Translators, library_id: str | None = None) -> str:
        if library_id is not None:
            data = ExportItemsAdapter.dump_python((citekeys, translator, library_id))
        else:
            data = ExportItemsAdapter.dump_python((citekeys, translator))
        response = await self._send("item.export", data)
        assert isinstance(response, str)
        return response

    async def close(self) -> None:
        await self.rpc.close()


if __name__ == "__main__":
    import atexit

    loop = asyncio.new_event_loop()

    async def start() -> Client:
        print("starting TCP connection")
        return Client()

    client = loop.run_until_complete(start())

    @atexit.register
    def close_client() -> None:
        loop.run_until_complete(client.close())
        loop.close()

    async def main() -> None:
        rpc = client.rpc
        print(f"{rpc.closed=}")
        print("client.is_ready = ", await client.is_ready())
        print("exported items = ", await client.export_items(["balakrishnan2025monitoring"], Translators.BIBLATEX))

    loop.run_until_complete(main())

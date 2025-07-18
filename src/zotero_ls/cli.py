# pyright: reportUnusedFunction=false
from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass, field
from pathlib import Path

import click
import rich
from lsprotocol import types
from pygls.lsp.server import LanguageServer

import zotero_ls.bbt as bbt
from zotero_ls import __version__


@dataclass
class InitOptions:
    zotero_dir: Path = field(default_factory=lambda: Path.home() / "Zotero")
    """Path to the Zotero directory."""

    juris_m: bool = False
    """Flag to let the language server know if it should assume the Juris-M port for Better BibTeX"""


@dataclass
class App:
    langserver: LanguageServer = field(default_factory=lambda: LanguageServer("zotero-ls", __version__))
    bbt_db: bbt.Database | None = None
    bbt_rpc: bbt.RpcClient | None = None

    async def close(self) -> None:
        logging.info("Shutting down Better BibTeX connection")
        if self.bbt_rpc is not None:
            await self.bbt_rpc.close()

    def register_langserver(self) -> None:
        server = self.langserver

        @server.feature(types.INITIALIZE)
        async def _initialize(params: types.InitializeParams) -> None:
            args = dataclasses.replace(InitOptions(), **(params.initialization_options or {}))
            bbt_db_path = args.zotero_dir / "better-bibtex.sqlite"
            try:
                assert bbt_db_path.is_file()
            except AssertionError as e:
                rich.print("better-bibtex.sqlite file not found in ", args.zotero_dir)
                raise e
            self.bbt_db = bbt.Database(bbt_db_path)

            if args.juris_m:
                self.bbt_rpc = bbt.RpcClient.make_juris_m()
            else:
                self.bbt_rpc = bbt.RpcClient()

        @server.feature(types.SHUTDOWN)
        async def _shutdown(_params: None) -> None:
            await self.close()

        pass


@click.command()
@click.version_option()
@click.help_option("-h", "--help")
@click.option("-v", "--verbose", count=True)
def main(*, verbose: int = 0) -> None:
    """A language server for Zotero that uses the Better BibTeX sqlite database along with the JSON-RPC."""
    match verbose:
        case 0:
            log_level = logging.WARNING
        case 1:
            log_level = logging.INFO
        case _:
            log_level = logging.DEBUG

    logging.basicConfig(format="[%(levelname)s]: %(message)s", level=log_level)

    app = App()
    app.register_langserver()
    app.langserver.start_io()


if __name__ == "__main__":
    main()

# pyright: reportUnusedFunction=false
from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import click
import lsprotocol.types as lsp
from pygls.lsp.server import LanguageServer

import zotero_ls.bbt as bbt
from zotero_ls import __version__


@dataclass
class InitOptions:
    zotero_dir: Path = field(default_factory=lambda: Path.home() / "Zotero")
    """Path to the Zotero directory."""

    juris_m: bool = False
    """Flag to let the language server know if it should assume the Juris-M port for Better BibTeX"""


CITE_PATTERNS: re.Pattern = re.compile(
    "|".join(  # alternation between patterns
        map(
            lambda pat: f"(?:{pat})",  # non-capture group for the sub-pattern
            [r"\\(?:[a-zA-Z]*cite|Cite)[a-zA-Z]*\*?(?:\s*\[[^]]*\]|\s*\<[^>]*\>){0,2}\s*\{[^}]*$"],
        )
    )
)
"""Compiled regex pattern for potential citation triggers"""


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

        @server.feature(lsp.INITIALIZE)
        async def _initialize(params: lsp.InitializeParams) -> None:
            logging.debug(params)
            init_options = params.initialization_options or {}
            if "zotero_dir" in init_options:
                zotero_dir = Path(str(init_options["zotero_dir"]).strip()).expanduser().absolute()
            else:
                zotero_dir = Path.home() / "Zotero"
            try:
                assert zotero_dir.exists()
            except AssertionError as e:
                logging.critical(f"{zotero_dir} does not exist")
                raise e

            juris_m = init_options.get("juris_m", False)

            args = InitOptions(zotero_dir, juris_m)
            bbt_db_path = args.zotero_dir / "better-bibtex.sqlite"
            try:
                assert bbt_db_path.is_file()
            except AssertionError as e:
                logging.critical(f"better-bibtex.sqlite file not found in {args.zotero_dir}")
                raise e
            logging.info("Loading database at ", bbt_db_path)
            self.bbt_db = bbt.Database(bbt_db_path)

            if args.juris_m:
                self.bbt_rpc = bbt.RpcClient.make_juris_m()
            else:
                self.bbt_rpc = bbt.RpcClient()

        @server.feature(lsp.SHUTDOWN)
        async def _shutdown(_params: None) -> None:
            await self.close()
            if self.bbt_rpc is not None:
                assert self.bbt_rpc.rpc.closed

        @server.feature(
            lsp.TEXT_DOCUMENT_COMPLETION,
            lsp.CompletionOptions(trigger_characters=["{", ","], all_commit_characters=["}"], resolve_provider=True),
        )
        async def _completions(
            params: lsp.CompletionParams,
        ) -> lsp.CompletionList | list[lsp.CompletionItem] | None:
            # To verify if the current trigger is a citation command, we will first have to check if the line matches the pattern
            document = server.workspace.get_text_document(params.text_document.uri)
            current_line = document.lines[params.position.line].strip()
            if CITE_PATTERNS.search(current_line) is not None:
                # Query the database for new items
                assert self.bbt_db is not None, "BetterBibTeX database connection not initialized"
                items = [
                    lsp.CompletionItem(key, kind=lsp.CompletionItemKind.Operator)
                    async for (key, _) in self.bbt_db.fetch_citekeys()
                ]
                return items
            return None

        @server.feature(lsp.COMPLETION_ITEM_RESOLVE)
        async def _resolve_completion_item(item: lsp.CompletionItem) -> lsp.CompletionItem:
            if self.bbt_rpc is None:
                return item
            # If the JSON-RPC is connected, make a query to it to export the given citation item
            export = await self.bbt_rpc.export_items([item.label], bbt.Translators.BIBTEX)
            # Format as markdown
            documentation = f"```bibtex\n{export}\n```"
            item.documentation = lsp.MarkupContent(
                kind=lsp.MarkupKind.Markdown,
                value=documentation,
            )
            return item

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

    logging.basicConfig(format="[%(levelname)s]: %(message)s", level=log_level, stream=sys.stderr)

    app = App()

    app.register_langserver()
    app.langserver.start_io()


if __name__ == "__main__":
    main()

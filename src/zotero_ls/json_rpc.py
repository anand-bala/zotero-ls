# pyright: reportMissingTypeArgument=false
import uuid
from dataclasses import dataclass
from typing import Literal

import aiohttp
import rich
from pydantic import BaseModel, Field, JsonValue, model_validator
from typing_extensions import Self, final, override

type JsonRpcVersion = Literal[
    # "1.0",
    "2.0"
]

type Params = None | list[JsonValue] | dict[str, JsonValue]


class JsonRpcRequest(BaseModel):
    jsonrpc: JsonRpcVersion = "2.0"
    id: str | int = Field(default_factory=lambda: str(uuid.uuid4()))
    method: str
    params: Params = None


class JsonRpcNotification(BaseModel):
    jsonrpc: JsonRpcVersion = "2.0"
    method: str
    params: Params = None


class JsonRpcErrorPayload(BaseModel):
    code: int
    message: str
    data: JsonValue | None = None


@final
class JsonRpcError(Exception):
    def __init__(self, error: JsonRpcErrorPayload) -> None:
        super().__init__(error.message)
        self._rpc_err = error

    @override
    def __str__(self) -> str:
        return f"{self._rpc_err.message} (Error Code: {self._rpc_err.code})"


class JsonRpcResponse(BaseModel):
    jsonrpc: JsonRpcVersion
    id: str | int | None = None
    result: JsonValue | None = None
    error: JsonRpcErrorPayload | None = None

    @model_validator(mode="after")
    def _result_or_error(self) -> Self:
        if self.result is None and self.error is None:
            raise ValueError("Either result or error must be present in JsonRpcResponse")
        if self.result is not None and self.error is not None:
            raise ValueError("Only one of result or error must be in JsonRpcResponse")
        return self


@dataclass
class JsonRpcClient:
    session: aiohttp.ClientSession

    def __post_init__(self) -> None:
        self.session.headers.update({"Content-Type": "application/json", "Accept": "application/json"})

    @property
    def closed(self) -> bool:
        return self.session.closed

    async def send_request(self, url: str, method: str, data: Params = None) -> JsonValue | None:
        request = JsonRpcRequest(method=method, params=data)
        async with self.session.post(url, data=request.model_dump_json().encode(), raise_for_status=True) as resp:
            assert resp.ok
            response = JsonRpcResponse.model_validate_json(await resp.read())

        if response.error is not None:
            assert response.result is None
            assert response.id is None
            raise JsonRpcError(response.error)
        assert response.result is not None
        assert request.id == response.id, rich.print(request.model_dump(), response.model_dump(), sep="\n")
        return response.result

    async def notify(self, url: str, method: str, data: Params = None) -> None:
        _ = self.send_request(url, method, data)

    async def close(self) -> None:
        await self.session.close()

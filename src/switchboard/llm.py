"""Single LLM entry point. Structured outputs via messages.parse(); validation
failures retry once and then raise. Never coerces an invalid generation to a
nearby valid value (README §4.2, last row).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import TypeVar

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

load_dotenv()

MODEL = os.environ.get("SWITCHBOARD_MODEL", "claude-opus-5")
EFFORT = os.environ.get("SWITCHBOARD_EFFORT", "low")

# USD per million tokens, Claude Opus 5.
PRICE_IN, PRICE_OUT = 5.00, 25.00

T = TypeVar("T", bound=BaseModel)


class SchemaFailure(Exception):
    """Model output did not validate twice, or the request was refused."""


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0

    @property
    def cost_usd(self) -> float:
        return (self.input_tokens * PRICE_IN + self.output_tokens * PRICE_OUT) / 1_000_000

    def add(self, other: "Usage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.latency_ms += other.latency_ms


_client: anthropic.Anthropic | None = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def call(schema: type[T], system: str, user: str, *, max_tokens: int = 1024, effort: str | None = None) -> tuple[T, Usage]:
    """One structured call. Retries once on validation failure with the error appended."""
    messages = [{"role": "user", "content": user}]
    usage = Usage()
    last_err: Exception | None = None
    for attempt in range(2):
        t0 = time.perf_counter()
        try:
            resp = client().messages.parse(
                model=MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                output_format=schema,
                output_config={"effort": effort or EFFORT},
            )
        except ValidationError as e:
            last_err = e
            usage.latency_ms += int((time.perf_counter() - t0) * 1000)
            messages = messages + [
                {"role": "assistant", "content": "(invalid output)"},
                {"role": "user", "content": f"Your previous output failed schema validation:\n{e}\nEmit only a valid object."},
            ]
            continue
        usage.input_tokens += resp.usage.input_tokens
        usage.output_tokens += resp.usage.output_tokens
        usage.latency_ms += int((time.perf_counter() - t0) * 1000)
        if resp.stop_reason == "refusal":
            raise SchemaFailure(f"refused: {getattr(resp, 'stop_details', None)}")
        if resp.parsed_output is None:
            last_err = RuntimeError("no parsed output")
            continue
        return resp.parsed_output, usage
    raise SchemaFailure(str(last_err))

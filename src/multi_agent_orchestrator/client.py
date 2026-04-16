from __future__ import annotations

import json
import re
import time
from typing import TypeVar

from openai import AzureOpenAI
from pydantic import BaseModel

from .config import Settings
from .models import ChatMessage, CompletionRecord


T = TypeVar("T", bound=BaseModel)


def extract_json_document(text: str) -> str:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate)

    for opener, closer in (("{", "}"), ("[", "]")):
        start = candidate.find(opener)
        if start < 0:
            continue
        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(candidate)):
            char = candidate[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    return candidate[start : index + 1]
    raise ValueError("Could not extract JSON document from model output.")


class AzureChatClient:
    def __init__(self, settings: Settings) -> None:
        settings.validate_for_azure()
        self._client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
            max_retries=2,
            timeout=settings.request_timeout_seconds,
        )

    def complete_text(
        self,
        *,
        role: str,
        deployment: str,
        messages: list[ChatMessage],
        max_output_tokens: int,
    ) -> CompletionRecord:
        started = time.perf_counter()
        response = self._client.chat.completions.create(
            model=deployment,
            messages=[message.model_dump() for message in messages],
            max_completion_tokens=max_output_tokens,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        usage = getattr(response, "usage", None)
        output_text = (response.choices[0].message.content or "").strip()
        return CompletionRecord(
            role=role,
            deployment=deployment,
            output_text=output_text,
            finish_reason=response.choices[0].finish_reason,
            latency_ms=latency_ms,
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
        )

    def complete_json(
        self,
        *,
        role: str,
        deployment: str,
        messages: list[ChatMessage],
        max_output_tokens: int,
        response_model: type[T],
    ) -> tuple[T, CompletionRecord]:
        record = self.complete_text(
            role=role,
            deployment=deployment,
            messages=messages,
            max_output_tokens=max_output_tokens,
        )
        try:
            payload = extract_json_document(record.output_text)
            return response_model.model_validate_json(payload), record
        except Exception:
            repair_record = self.complete_text(
                role=f"{role}:json-repair",
                deployment=deployment,
                messages=[
                    ChatMessage(
                        role="system",
                        content="Convert the source content into strict JSON that matches the provided schema. Return JSON only.",
                    ),
                    ChatMessage(
                        role="user",
                        content=(
                            "Schema:\n"
                            f"{json.dumps(response_model.model_json_schema(), indent=2)}\n\n"
                            "Source content:\n"
                            f"{record.output_text}"
                        ),
                    ),
                ],
                max_output_tokens=max_output_tokens,
            )
            payload = extract_json_document(repair_record.output_text)
            combined_record = CompletionRecord(
                role=role,
                deployment=deployment,
                output_text=repair_record.output_text,
                finish_reason=repair_record.finish_reason,
                latency_ms=record.latency_ms + repair_record.latency_ms,
                prompt_tokens=record.prompt_tokens + repair_record.prompt_tokens,
                completion_tokens=record.completion_tokens + repair_record.completion_tokens,
                total_tokens=record.total_tokens + repair_record.total_tokens,
            )
            return response_model.model_validate_json(payload), combined_record

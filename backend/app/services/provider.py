from dataclasses import dataclass
import json
from time import perf_counter
from typing import Protocol

import openai
from openai import OpenAI

from backend.app.core.config import ROOT
from backend.app.core.errors import ProviderError
from backend.app.models.schemas import ModelAnswer


PROMPT_VERSION = "2.4.0"
PROMPT_DIR = ROOT / "prompts"
SYSTEM_PROMPT = (PROMPT_DIR / "system_prompt.txt").read_text(encoding="utf-8")
ANSWER_PROMPT = (PROMPT_DIR / "answer_prompt.txt").read_text(encoding="utf-8")
RESPONSE_SCHEMA = json.loads((PROMPT_DIR / "response_schema.json").read_text(encoding="utf-8"))
VERIFICATION_PROMPT = (PROMPT_DIR / "verification_prompt.txt").read_text(encoding="utf-8")
VERIFICATION_SCHEMA = json.loads((PROMPT_DIR / "verification_schema.json").read_text(encoding="utf-8"))
PASSAGE_KEYS = ("chunk_id", "document_id", "document_title", "page_number", "content")


@dataclass(frozen=True)
class ProviderResult:
    text: str
    model: str
    response_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None


class AnswerProvider(Protocol):
    name: str
    model: str
    configured: bool

    def generate(self, question: str, passages: list[dict]) -> ProviderResult: ...
    def verify(self, question: str, passages: list[dict], answer: ModelAnswer) -> ProviderResult: ...


def evidence_input(question, passages):
    return {
        "question": question,
        "passages": [{key: row[key] for key in PASSAGE_KEYS} for row in passages],
    }


class OpenAIProvider:
    name = "openai"

    def __init__(self, settings, client=None):
        self.model = settings.openai_model
        key = settings.openai_api_key.get_secret_value().strip()
        self.client = client or (
            OpenAI(
                api_key=key, base_url="https://api.openai.com/v1",
                timeout=settings.openai_timeout_seconds, max_retries=settings.openai_max_retries,
            ) if key else None
        )
        self.configured = self.client is not None

    def generate(self, question, passages):
        return self._request(
            instructions=SYSTEM_PROMPT, data=ANSWER_PROMPT.strip() + "\n\n" + json.dumps(
                evidence_input(question, passages), ensure_ascii=False,
            ),
            schema=RESPONSE_SCHEMA, name="course_answer", max_output_tokens=1500,
        )

    def verify(self, question, passages, answer):
        titles = {row["chunk_id"]: row["document_title"] for row in passages}
        data = {
            "question": question,
            "candidate_answer": answer.answer,
            "cited_quotations": [
                {**cite.model_dump(), "document_title": titles[cite.chunk_id]} for cite in answer.citations
            ],
        }
        return self._request(
            instructions=VERIFICATION_PROMPT, data=json.dumps(data, ensure_ascii=False),
            schema=VERIFICATION_SCHEMA, name="grounding_verification", max_output_tokens=350,
        )

    def _request(self, *, instructions, data, schema, name, max_output_tokens):
        if self.client is None:
            raise ProviderError("missing_credentials", "Set OPENAI_API_KEY and restart the backend to ask supported questions.")
        started = perf_counter()
        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=instructions,
                input=data,
                text={"format": {
                    "type": "json_schema", "name": name, "schema": schema, "strict": True,
                }},
                max_output_tokens=max_output_tokens,
                store=False,
            )
        except openai.AuthenticationError:
            raise ProviderError("authentication_error", "OpenAI rejected the credentials. Check the API key in the backend environment.") from None
        except openai.PermissionDeniedError:
            raise ProviderError("permission_denied", "This OpenAI project cannot access the requested operation.") from None
        except openai.RateLimitError as exc:
            if exc.code in ("insufficient_quota", "billing_hard_limit_reached"):
                raise ProviderError("insufficient_quota", "This OpenAI project has insufficient API quota. Check billing and usage limits.") from None
            raise ProviderError("rate_limit", "OpenAI is rate limiting requests. Wait briefly and try again.", True) from None
        except openai.APITimeoutError:
            raise ProviderError("timeout", "OpenAI took too long to respond. Try again.", True) from None
        except openai.APIConnectionError:
            raise ProviderError("network_error", "The backend could not reach OpenAI. Check the network and retry.", True) from None
        except openai.NotFoundError:
            raise ProviderError("model_not_found", "OpenAI could not find the configured model. Check OPENAI_MODEL and project access.") from None
        except openai.APIStatusError as exc:
            raise ProviderError("provider_http_error", "OpenAI could not process this request.", exc.status_code >= 500) from None
        except openai.APIError:
            raise ProviderError("provider_error", "OpenAI returned an unexpected provider error.", True) from None

        if response.status != "completed":
            raise ProviderError("incomplete_response", "OpenAI returned an incomplete response.", True)
        if not response.output_text:
            raise ProviderError("empty_or_refused_response", "OpenAI did not return a usable structured response.")
        usage = response.usage
        return ProviderResult(
            text=response.output_text,
            model=response.model,
            response_id=response.id,
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
            latency_ms=round((perf_counter() - started) * 1000),
        )


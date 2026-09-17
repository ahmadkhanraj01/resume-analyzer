"""Provider chain, JSON validation, retry. No FastAPI here: raises
LLMUnavailableError, which the router translates to 503.

Groq first for latency, Gemini as fallback on any error, including rate
limits. One interface: generate_report(...) -> InterviewReport.
"""

import json
import logging
from functools import lru_cache

from pydantic import ValidationError as PydanticValidationError

from app.core.config import Settings
from app.core.exceptions import LLMUnavailableError
from app.schemas.report import InterviewReport
from app.services.prompts import (
    report_prompt,
    retry_prompt,
    role_profile_prompt,
    skill_extraction_prompt,
)

logger = logging.getLogger(__name__)

PROVIDERS = ("groq", "gemini")

# The full report is a fair amount of JSON (up to 12 skill gaps, 16
# questions, 14 prep days); the skill list is one short JSON array. Reasoning
# models (see _REASONING_MODEL_MARKERS) spend part of this same budget on
# hidden chain-of-thought before emitting content, so it needs real headroom
# or the response gets cut off mid-JSON with finish_reason "length" and
# never reaches the validator.
REPORT_MAX_TOKENS = 6000
SKILLS_MAX_TOKENS = 1024

# Groq's `reasoning_effort` param only exists for its reasoning models
# (currently the gpt-oss family) and is a 400 error on anything else, so it
# is only sent when the configured model looks like one of those.
_REASONING_MODEL_MARKERS = ("gpt-oss",)


def _strip_fences(text: str) -> str:
    """Strips markdown code fences defensively, regardless of what the
    prompt asked for. Models add them anyway often enough that skipping
    this check is not worth the failed parses."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


# Provider clients hold an HTTP connection pool; building one per call
# throws that pool away each time. Keyed on the api key so a settings change
# in tests still gets a fresh client.
@lru_cache(maxsize=4)
def _groq_client(api_key: str):
    from groq import Groq

    return Groq(api_key=api_key)


@lru_cache(maxsize=4)
def _gemini_client(api_key: str):
    from google import genai

    return genai.Client(api_key=api_key)


def _call_groq(prompt: str, settings: Settings, max_tokens: int) -> str:
    client = _groq_client(settings.groq_api_key)
    kwargs = {}
    if any(marker in settings.groq_model for marker in _REASONING_MODEL_MARKERS):
        # Low effort: the task is following a fixed JSON schema, not
        # reasoning depth, so spend as few hidden tokens on it as possible.
        kwargs["reasoning_effort"] = "low"
    resp = client.chat.completions.create(
        model=settings.groq_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=max_tokens,
        **kwargs,
    )
    return resp.choices[0].message.content or ""


def _call_gemini(prompt: str, settings: Settings, max_tokens: int) -> str:
    from google.genai import types

    client = _gemini_client(settings.gemini_api_key)
    resp = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            # No tools are passed, so disable automatic function calling
            # explicitly; otherwise the SDK logs a warning on every call.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    return resp.text or ""


def _call_provider(provider: str, prompt: str, settings: Settings, max_tokens: int) -> str:
    if provider == "groq":
        return _call_groq(prompt, settings, max_tokens)
    if provider == "gemini":
        return _call_gemini(prompt, settings, max_tokens)
    raise ValueError(f"unknown provider {provider}")


def _try_report_on_provider(
    provider: str, prompt: str, settings: Settings
) -> InterviewReport | None:
    """response -> strip fences -> validate; on a validation failure, retry
    once on the same provider with the error appended so the model can
    self-correct. Any other failure (network, auth, rate limit) moves
    straight to the next provider with no retry."""
    current_prompt = prompt
    for attempt in range(2):
        try:
            raw = _call_provider(provider, current_prompt, settings, REPORT_MAX_TOKENS)
        except Exception:
            logger.warning("provider %s call failed", provider, exc_info=True)
            return None

        cleaned = _strip_fences(raw)
        try:
            return InterviewReport.model_validate_json(cleaned)
        except (PydanticValidationError, json.JSONDecodeError) as e:
            if attempt == 0:
                current_prompt = retry_prompt(prompt, str(e))
                continue
            logger.warning("provider %s produced invalid JSON twice", provider)
            return None
    return None


def generate_report(
    resume_text: str,
    job_description: str,
    self_description: str,
    covered_skills: list[str],
    missing_skills: list[str],
    match_score: int,
    settings: Settings,
) -> InterviewReport:
    """Calls the LLM to produce questions and a preparation plan, given the
    scoring output as authoritative context. The returned match_score is
    always the deterministic one passed in; whatever the model returns for
    that field is discarded."""
    prompt = report_prompt(
        resume_text, job_description, self_description, covered_skills, missing_skills
    )

    for provider in PROVIDERS:
        report = _try_report_on_provider(provider, prompt, settings)
        if report is not None:
            return report.model_copy(update={"match_score": match_score})

    raise LLMUnavailableError()


def _try_skills_on_provider(provider: str, prompt: str, settings: Settings) -> list[str] | None:
    current_prompt = prompt
    for attempt in range(2):
        try:
            raw = _call_provider(provider, current_prompt, settings, SKILLS_MAX_TOKENS)
        except Exception:
            logger.warning("provider %s call failed", provider, exc_info=True)
            return None

        cleaned = _strip_fences(raw)
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list) and all(isinstance(s, str) for s in parsed):
                return parsed
            raise ValueError("expected a JSON array of strings")
        except (json.JSONDecodeError, ValueError) as e:
            if attempt == 0:
                current_prompt = f"{prompt}\n\nYour previous response was invalid: {e}\nReturn a JSON array of strings only."
                continue
            return None
    return None


def extract_skills_llm(job_description: str, settings: Settings) -> list[str]:
    """The LLM pass in the skill extraction union: loose, high recall. Unlike
    generate_report, failure here is not fatal to the analysis; the regex
    seed pass in services/skills.py still runs. Returns [] rather than
    raising so one flaky provider call cannot sink the whole request."""
    prompt = skill_extraction_prompt(job_description)
    for provider in PROVIDERS:
        skills = _try_skills_on_provider(provider, prompt, settings)
        if skills is not None:
            return skills
    return []


def _parse_role_profile(raw: str) -> tuple[str | None, list[str]]:
    parsed = json.loads(_strip_fences(raw))
    if not isinstance(parsed, dict):
        raise ValueError("expected a JSON object")
    role = parsed.get("role")
    skills = parsed.get("skills", [])
    if role is not None and not isinstance(role, str):
        raise ValueError("role must be a string or null")
    if not isinstance(skills, list) or not all(isinstance(x, str) for x in skills):
        raise ValueError("skills must be an array of strings")
    role = role.strip() if role else None
    skills = [x.strip() for x in skills if x.strip()]
    if not role:
        return None, []
    return role, skills


def infer_role_profile(text: str, settings: Settings) -> tuple[str | None, list[str]]:
    """Fallback for a job description with no extractable skills. Returns
    (role title, typical skills), or (None, []) if the text names no role or
    every provider failed. Like extract_skills_llm, failure is not fatal
    here; the caller decides what an empty result means."""
    prompt = role_profile_prompt(text)
    for provider in PROVIDERS:
        current_prompt = prompt
        for attempt in range(2):
            try:
                raw = _call_provider(provider, current_prompt, settings, SKILLS_MAX_TOKENS)
            except Exception:
                logger.warning("provider %s call failed", provider, exc_info=True)
                break
            try:
                return _parse_role_profile(raw)
            except (json.JSONDecodeError, ValueError) as e:
                if attempt == 0:
                    current_prompt = f"{prompt}\n\nYour previous response was invalid: {e}\nReturn the JSON object only."
                    continue
    return None, []

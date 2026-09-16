"""Provider chain, JSON validation, retry. No FastAPI here: raises
LLMUnavailableError, which the router translates to 503.

Groq first for latency, Gemini as fallback on any error, including rate
limits. One interface: generate_report(...) -> InterviewReport.
"""

import json
import logging

from pydantic import ValidationError as PydanticValidationError

from app.core.config import Settings
from app.core.exceptions import LLMUnavailableError
from app.schemas.report import InterviewReport
from app.services.prompts import report_prompt, retry_prompt, skill_extraction_prompt

logger = logging.getLogger(__name__)

PROVIDERS = ("groq", "gemini")


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


def _call_groq(prompt: str, settings: Settings) -> str:
    from groq import Groq

    client = Groq(api_key=settings.groq_api_key)
    resp = client.chat.completions.create(
        model=settings.groq_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    return resp.choices[0].message.content or ""


def _call_gemini(prompt: str, settings: Settings) -> str:
    from google import genai

    client = genai.Client(api_key=settings.gemini_api_key)
    resp = client.models.generate_content(model=settings.gemini_model, contents=prompt)
    return resp.text or ""


def _call_provider(provider: str, prompt: str, settings: Settings) -> str:
    if provider == "groq":
        return _call_groq(prompt, settings)
    if provider == "gemini":
        return _call_gemini(prompt, settings)
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
            raw = _call_provider(provider, current_prompt, settings)
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
            raw = _call_provider(provider, current_prompt, settings)
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

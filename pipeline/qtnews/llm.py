"""Минимальный клиент Anthropic Messages API (без SDK, только requests)."""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Protocol

import requests

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


class DeadlineExceeded(LLMError):
    """До лимита времени запуска осталось слишком мало — новый запрос не начинаем."""


class _Budget:
    """Общий лимит времени запуска (функция Vercel живёт не дольше 300 с).

    deadline — момент time.monotonic(), к которому все запросы должны завершиться; None — без лимита.
    """

    deadline: float | None = None

    def remaining(self) -> float:
        return float("inf") if self.deadline is None else self.deadline - time.monotonic()

    def timeout(self, default: float) -> float:
        left = self.remaining()
        if left < 15:
            raise DeadlineExceeded(f"До конца запуска {left:.0f} с — запрос к ИИ не начинаем")
        return min(default, left - 5)

    def sleep(self, seconds: float) -> None:
        if self.remaining() < seconds + 20:
            raise DeadlineExceeded("Не хватает времени на повтор запроса к ИИ")
        time.sleep(seconds)


class LLM(Protocol):
    def complete(self, *, model: str, system: str, prompt: str, max_tokens: int = 4000,
                 temperature: float = 0.4) -> str: ...


class AnthropicClient:
    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com", timeout: int = 180,
                 max_retries: int = 4):
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY не задан")
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.budget = _Budget()
        self.session = requests.Session()
        self.session.headers.update({
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        })

    def complete(self, *, model: str, system: str, prompt: str, max_tokens: int = 4000,
                 temperature: float = 0.4) -> str:
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        delay = 2.0
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.post(f"{self.base_url}/v1/messages", json=body,
                                         timeout=self.budget.timeout(self.timeout))
            except requests.RequestException as exc:
                if attempt == self.max_retries:
                    raise LLMError(f"Сетевая ошибка LLM: {exc}") from exc
                self.budget.sleep(delay)
                delay *= 2
                continue
            if resp.status_code in (429, 500, 502, 503, 529) and attempt < self.max_retries:
                wait = float(resp.headers.get("retry-after", delay))
                log.warning("LLM %s, повтор через %.0f с", resp.status_code, wait)
                self.budget.sleep(wait)
                delay *= 2
                continue
            if resp.status_code >= 400:
                raise LLMError(f"LLM HTTP {resp.status_code}: {resp.text[:500]}")
            data = resp.json()
            if data.get("stop_reason") == "max_tokens":
                raise LLMError("Ответ LLM обрезан (max_tokens)")
            return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        raise LLMError("Исчерпаны попытки обращения к LLM")


class _Overloaded(LLMError):
    """Модель перегружена или недоступна — можно попробовать запасную."""


class GeminiClient:
    """Google Gemini API (бесплатный тариф AI Studio подходит для демо).

    Бесплатный тариф ограничен по запросам в минуту и в день, поэтому между вызовами
    выдерживается пауза, а на 429 — повтор с ожиданием.
    """

    def __init__(self, api_key: str, base_url: str = "https://generativelanguage.googleapis.com", timeout: int = 75,
                 max_retries: int = 4, min_interval_s: float = 7.0):
        if not api_key:
            raise LLMError("GEMINI_API_KEY не задан")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.min_interval_s = min_interval_s
        self._last_call = 0.0
        self.budget = _Budget()
        self.session = requests.Session()
        self.session.headers.update({"x-goog-api-key": api_key, "content-type": "application/json"})

    def complete(self, *, model: str, system: str, prompt: str, max_tokens: int = 4000,
                 temperature: float = 0.4) -> str:
        """model может быть списком через запятую: при перегрузке (503/429) берётся следующая модель."""
        models = [m.strip() for m in model.split(",") if m.strip()]
        last: LLMError | None = None
        for i, m in enumerate(models):
            try:
                return self._complete_one(m, system, prompt, max_tokens, temperature,
                                          retries=self.max_retries if i == len(models) - 1 else 1)
            except _Overloaded as exc:
                log.warning("Модель %s перегружена, пробуем следующую", m)
                last = LLMError(str(exc))
        raise last or LLMError("Нет доступных моделей Gemini")

    def _complete_one(self, model: str, system: str, prompt: str, max_tokens: int, temperature: float,
                      retries: int) -> str:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            # запас на «размышления» моделей Flash, иначе ответ обрезается
            "generationConfig": {"maxOutputTokens": max(max_tokens * 2, 8192), "temperature": temperature,
                                 "responseMimeType": "application/json"},
        }
        url = f"{self.base_url}/v1beta/models/{model}:generateContent"
        delay = 10.0
        for attempt in range(1, retries + 1):
            wait = self.min_interval_s - (time.monotonic() - self._last_call)
            if wait > 0:
                self.budget.sleep(wait)
            self._last_call = time.monotonic()
            try:
                resp = self.session.post(url, json=body, timeout=self.budget.timeout(self.timeout))
            except requests.RequestException as exc:
                if attempt == retries:
                    raise _Overloaded(f"Сетевая ошибка Gemini: {exc}") from exc
                self.budget.sleep(delay)
                continue
            if resp.status_code in (429, 500, 503) and attempt == retries:
                raise _Overloaded(f"Gemini HTTP {resp.status_code}: {resp.text[:200]}")
            if resp.status_code in (429, 500, 503):
                log.warning("Gemini %s, повтор через %.0f с", resp.status_code, delay)
                self.budget.sleep(delay)
                delay *= 2
                continue
            if resp.status_code >= 400:
                raise LLMError(f"Gemini HTTP {resp.status_code}: {resp.text[:400]}")
            data = resp.json()
            cands = data.get("candidates") or []
            if not cands:
                raise LLMError(f"Gemini без ответа: {str(data.get('promptFeedback'))[:300]}")
            if cands[0].get("finishReason") == "MAX_TOKENS":
                raise LLMError("Ответ Gemini обрезан (MAX_TOKENS)")
            parts = (cands[0].get("content") or {}).get("parts") or []
            return "".join(p.get("text", "") for p in parts if not p.get("thought"))
        raise _Overloaded("Исчерпаны попытки обращения к Gemini")


def extract_json(text: str) -> Any:
    """Достаёт JSON из ответа модели (допускает обёртку ```json ... ```)."""
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    candidate = fenced.group(1) if fenced else text
    start = min((i for i in (candidate.find("{"), candidate.find("[")) if i != -1), default=-1)
    if start == -1:
        raise LLMError(f"В ответе LLM нет JSON: {text[:300]}")
    opener = candidate[start]
    closer = "}" if opener == "{" else "]"
    end = candidate.rfind(closer)
    try:
        return json.loads(candidate[start:end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"Некорректный JSON от LLM: {exc}") from exc


def complete_json(llm: LLM, **kwargs: Any) -> Any:
    """complete() + разбор JSON, с одной повторной попыткой при битом JSON."""
    try:
        return extract_json(llm.complete(**kwargs))
    except DeadlineExceeded:
        raise
    except LLMError:
        kwargs["temperature"] = 0.0
        return extract_json(llm.complete(**kwargs))

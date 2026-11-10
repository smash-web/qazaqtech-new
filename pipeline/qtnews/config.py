"""Конфигурация конвейера. Все значения берутся из переменных окружения."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(f"Переменная окружения {name} не задана")
    return value or ""


@dataclass(frozen=True)
class Config:
    # База данных конвейера (сырые новости, сюжеты). Postgres в проде, sqlite для локальных тестов.
    database_url: str = field(default_factory=lambda: _env("PIPELINE_DATABASE_URL", "sqlite:///pipeline.db"))

    # Payload CMS
    cms_url: str = field(default_factory=lambda: _env("CMS_URL", "http://localhost:3000").rstrip("/"))
    cms_api_key: str = field(default_factory=lambda: _env("CMS_API_KEY"))
    cms_user_collection: str = field(default_factory=lambda: _env("CMS_USER_COLLECTION", "users"))

    # LLM (Anthropic Messages API)
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    anthropic_base_url: str = field(default_factory=lambda: _env("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/"))
    writer_model: str = field(default_factory=lambda: _env("WRITER_MODEL", "claude-sonnet-5-5"))
    qa_model: str = field(default_factory=lambda: _env("QA_MODEL"))  # пусто = как writer_model
    # Google Gemini — бесплатный тариф для демо. Используется, если нет ключа Anthropic.
    gemini_api_key: str = field(default_factory=lambda: _env("GEMINI_API_KEY"))
    gemini_writer_model: str = field(default_factory=lambda: _env("GEMINI_WRITER_MODEL", "gemini-3.5-flash,gemini-3.6-flash,gemini-3.5-flash-lite"))
    gemini_qa_model: str = field(default_factory=lambda: _env("GEMINI_QA_MODEL", "gemini-3.5-flash-lite,gemini-3.1-flash-lite"))
    gemini_scorer_model: str = field(default_factory=lambda: _env("GEMINI_SCORER_MODEL", "gemini-3.5-flash-lite,gemini-3.1-flash-lite"))
    scorer_model: str = field(default_factory=lambda: _env("SCORER_MODEL", "claude-haiku-5-5"))

    # Расписание и лимиты
    collect_interval_min: int = field(default_factory=lambda: int(_env("COLLECT_INTERVAL_MIN", "20")))
    process_interval_min: int = field(default_factory=lambda: int(_env("PROCESS_INTERVAL_MIN", "60")))
    max_articles_per_run: int = field(default_factory=lambda: int(_env("MAX_ARTICLES_PER_RUN", "3")))
    cluster_threshold: float = field(default_factory=lambda: float(_env("CLUSTER_THRESHOLD", "0.42")))
    story_window_hours: int = field(default_factory=lambda: int(_env("STORY_WINDOW_HOURS", "36")))
    timezone: str = field(default_factory=lambda: _env("SITE_TIMEZONE", "Asia/Almaty"))
    fetch_full_text: bool = field(default_factory=lambda: _env("FETCH_FULL_TEXT", "true").lower() == "true")
    require_image: bool = field(default_factory=lambda: _env("REQUIRE_IMAGE", "true").lower() == "true")
    duplicate_threshold: float = field(default_factory=lambda: float(_env("DUPLICATE_THRESHOLD", "0.45")))
    user_agent: str = field(default_factory=lambda: _env("USER_AGENT", "QazaqTechNewsBot/1.0 (+https://example.kz/bot)"))


def load_dotenv(path: str = ".env") -> None:
    """Подхватывает переменные из .env (если файл есть); уже заданные в окружении не перезаписываются."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load() -> Config:
    load_dotenv()
    return Config()

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    groq_api_key: str = ""
    gemini_api_key: str = ""
    groq_stt_model: str = "whisper-large-v3"
    gemini_model: str = "gemini-3.5-flash"
    data_dir: Path = ROOT / "data"
    notes_dir: Path = ROOT / "notes"
    host: str = "127.0.0.1"
    port: int = 8000

    max_chunk_bytes: int = 24 * 1024 * 1024
    max_chunk_seconds: float = 600.0
    split_safety_ratio: float = 0.92
    stt_max_attempts: int = 3
    gemini_map_threshold_chars: int = 24_000
    gemini_map_chunk_chars: int = 18_000
    gemini_map_overlap_chars: int = 800

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def groq_ready(self) -> bool:
        return bool(self.groq_api_key.strip())

    @property
    def gemini_ready(self) -> bool:
        return bool(self.gemini_api_key.strip())


settings = Settings()
settings.data_dir = Path(settings.data_dir)
if not settings.data_dir.is_absolute():
    settings.data_dir = (ROOT / settings.data_dir).resolve()
settings.notes_dir = Path(settings.notes_dir)
if not settings.notes_dir.is_absolute():
    settings.notes_dir = (ROOT / settings.notes_dir).resolve()

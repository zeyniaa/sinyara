from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SINYARA_", env_file=".env", extra="ignore")
    llm_provider: str = "ollama"
    llm_model: str = "qwen3:4b"
    ollama_url: str = "http://127.0.0.1:11434"
    llm_timeout: float = 180
    asr_provider: str = "whisper"
    asr_space: str = ""
    whisper_model: str = "small"
    aasist_enabled: bool = False
    aasist_dir: str = ".cache/aasist"
    cors_origins: str = "http://127.0.0.1:5174,http://localhost:5174,http://127.0.0.1:4174"
    ttl_seconds: int = 900
    max_queue: int = 10
    analyses_per_day: int = 3
    followups_per_case: int = 5
    max_cases: int = 100
    max_audio_memory_mb: int = 150


settings = Settings()

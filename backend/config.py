from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_chat_model: str = "llama3.2"
    ollama_vision_model: str = "llava"

    backend_host: str = "127.0.0.1"
    backend_port: int = 8765

    whisper_model: str = "base.en"
    whisper_device: str = "cpu"
    whisper_language: str = "en"
    tts_voice: str = "en-US-AriaNeural"

    wakeword_models: list[str] = ["hey_jarvis", "alexa"]
    wakeword_threshold: float = 0.45

    screenshot_dir: str = "data/screenshots"

    # Flow system settings (guided multi-turn conversations)
    flows_enabled: bool = True
    email_provider: str = "gmail_web"  # "gmail_web", "mailto", "outlook_com"
    email_live_typing: bool = False
    followup_listen_seconds: int = 8
    flow_idle_timeout_seconds: int = 90
    context_ttl_seconds: int = 120

    @property
    def screenshot_path(self) -> Path:
        p = ROOT / self.screenshot_dir
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()

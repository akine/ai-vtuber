from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # YouTube
    YOUTUBE_VIDEO_ID: str = ""

    # Twitch
    TWITCH_TOKEN: str = ""
    TWITCH_CHANNEL: str = ""

    # LLM
    VLLM_URL: str = "http://localhost:8000/v1"

    # TTS
    TTS_URL: str = "http://localhost:8001"

    # VTube Studio
    VTS_ENABLED: bool = False  # VTS連携を有効にする場合はTrue
    VTS_HOST: str = "localhost"
    VTS_PORT: int = 8001  # VTube Studio APIのデフォルトポート

    # Character
    CHARACTER_NAME: str = "ミコト"
    IDLE_THRESHOLD_SECONDS: int = 30

    # Chat Mode
    CHAT_MODE: str = "mock"  # "youtube", "twitch", "mock"
    MOCK_INTERVAL: float = 10.0  # seconds between mock comments

    class Config:
        env_file = ".env"


settings = Settings()

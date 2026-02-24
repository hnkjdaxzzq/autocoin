from pathlib import Path
from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{BASE_DIR / 'autocoin.db'}"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["*"]
    frontend_dir: str = str(BASE_DIR / "frontend")
    debug: bool = False

    jwt_secret: str = "autocoin-dev-secret-change-in-production"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days
    jwt_algorithm: str = "HS256"

    # --- LLM image recognition settings ---
    # Supported providers: openai, gemini, zhipu, qwen, deepseek
    # Comma-separated priority order; only providers with API keys configured will be used.
    # The system tries each in order until one succeeds.
    llm_provider_order: str = "zhipu,qwen,deepseek,openai,gemini"
    llm_timeout: int = 60  # seconds, timeout for LLM API calls

    # OpenAI (GPT-4o-mini) — also used as generic OpenAI-compatible client
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = ""  # custom base URL, leave empty for default

    # Google Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # 智谱 GLM (OpenAI-compatible)
    # Image limits per model:
    #   GLM-4.1V-Thinking-Flash: FREE, supports base64 & URL (recommended)
    #   glm-4v-plus-0111: max 5 images/request, supports base64 & URL
    #   glm-4v-flash: FREE but max 1 image, URL only (no base64)
    zhipu_api_key: str = ""
    zhipu_model: str = "GLM-4.1V-Thinking-Flash"
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"

    # 通义千问 Qwen VL (OpenAI-compatible)
    qwen_api_key: str = ""
    qwen_model: str = "qwen-vl-max"  # qwen-vl-plus for cheaper option
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # Deepseek (OpenAI-compatible) — text only, no vision support
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"

    # Daily image import limit per user (number of images successfully imported)
    image_import_daily_limit: int = 10

    class Config:
        env_prefix = "AUTOCOIN_"


settings = Settings()

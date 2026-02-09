import re
import os
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from dotenv import load_dotenv, find_dotenv

from src.utils.logger import logger


@dataclass(frozen=True)
class ManagerSettings:
    name: str
    greeting: str
    script_paths: List[str]
    lang: str


@dataclass(frozen=True)
class BotSettings:
    token: str
    primary_lang: str
    managers: Dict[str, ManagerSettings]


@dataclass(frozen=True)
class Settings:
    logger = logger

    database_url: str = "sqlite+aiosqlite:///telegram_bot.db"
    echo: bool = False
    webhook_base_url: str = ""
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8080
    webhook_path_prefix: str = "/telegram"
    webhook_secret_token: str = ""
    webhook_drop_pending_updates: bool = True
    webhook_allowed_updates: List[str] = field(
        default_factory=lambda: ["message", "callback_query"]
    )
    webhook_url: Optional[str] = None
    webhook_path: str = "/telegram/webhook"
    env: str = "prod"
    llm_provider: str = "deepseek"
    llm_api_key: str = ""
    llm_model: Optional[str] = None
    
    bots: Dict[str, BotSettings] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(find_dotenv())

        def parse_bool(value: Optional[str], default: bool) -> bool:
            if value is None:
                return default
            if value.strip().lower() in ("1", "true", "yes", "y"):
                return True
            elif value.strip().lower() in ("0", "false", "no", "n"):
                return False
            else:
                cls.logger.error("Failed to parse boolean value. Using default value as fallback variant.")
                return default

        def parse_int(value: Optional[str], default: int) -> int:
            if value is None or not value.strip():
                return default
            try:
                return int(value)
            except ValueError:
                return default

        def parse_list(value: Optional[str], default: List[str]) -> List[str]:
            if value is None or not value.strip():
                return default
            # Remove leading/trailing brackets if present
            cleaned_value = value.strip()
            if cleaned_value.startswith("[") and cleaned_value.endswith("]"):
                cleaned_value = cleaned_value[1:-1]
            return [item.strip() for item in cleaned_value.split(",") if item.strip()]

        def load_bots_from_json(path: str) -> Dict[str, BotSettings]:
            if not os.path.exists(path):
                cls.logger.warning(f"Config file {path} not found.")
                return {}
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                bots = {}
                for bot_name, bot_data in data.items():
                    managers = {}
                    for m_id, m_data in bot_data.get("managers", {}).items():
                        managers[m_id] = ManagerSettings(
                            name=m_data.get("name", ""),
                            greeting=m_data.get("greeting", ""),
                            script_paths=m_data.get("script_paths", []),
                            lang=m_data.get("lang", "en")
                        )
                    bots[bot_name] = BotSettings(
                        token=bot_data.get("token", ""),
                        primary_lang=bot_data.get("primary_lang", "en"),
                        managers=managers
                    )
                return bots
            except Exception as e:
                cls.logger.error(f"Failed to load {path}: {e}")
                return {}

        bots = load_bots_from_json("bot_configs.json")

        return cls(
            database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///telegram_bot.db"),
            echo=parse_bool(os.getenv("ECHO"), False),
            webhook_base_url=os.getenv("WEBHOOK_BASE_URL", ""),
            webhook_host=os.getenv("WEBHOOK_HOST", "0.0.0.0"),
            webhook_port=parse_int(os.getenv("WEBHOOK_PORT"), 8080),
            webhook_path_prefix=os.getenv("WEBHOOK_PATH_PREFIX", "/telegram"),
            webhook_secret_token=os.getenv("WEBHOOK_SECRET_TOKEN", ""),
            webhook_drop_pending_updates=parse_bool(
                os.getenv("WEBHOOK_DROP_PENDING_UPDATES"), True
            ),
            webhook_allowed_updates=parse_list(
                os.getenv("WEBHOOK_ALLOWED_UPDATES"), ["message", "callback_query"]
            ),
            webhook_url=os.getenv("WEBHOOK_URL"),
            webhook_path=os.getenv("WEBHOOK_PATH", "/telegram/webhook"),
            env=os.getenv("ENV", "prod").lower(),
            llm_provider=os.getenv("LLM_PROVIDER", "deepseek").lower(),
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_model=os.getenv("LLM_MODEL"),
            bots=bots,
        )

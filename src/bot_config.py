from dataclasses import dataclass
from typing import List, Optional, Dict

from src.config import Settings, BotSettings, ManagerSettings


@dataclass
class BotConfig:
    name: str
    token: str
    webhook_path: str
    primary_lang: str
    managers: Dict[str, ManagerSettings]
    secret_token: str = ""

    @property
    def manager_ids(self) -> List[str]:
        return list(self.managers.keys())

    def build_webhook_url(self, base_url: str) -> str:
        base = base_url.rstrip("/")
        path = self.webhook_path if self.webhook_path.startswith("/") else f"/{self.webhook_path}"
        return f"{base}{path}"


def _normalize_path(path: str) -> str:
    if not path:
        return "/"
    return path if path.startswith("/") else f"/{path}"


def load_bot_configs(settings: Settings) -> List[BotConfig]:
    configs: List[BotConfig] = []

    if not settings.bots:
        return configs

    for name, bot_settings in settings.bots.items():
        if len(settings.bots) == 1:
             path = _normalize_path(settings.webhook_path)
        else:
             path = f"{settings.webhook_path_prefix}/{name}"

        configs.append(
            BotConfig(
                name=name,
                token=bot_settings.token,
                webhook_path=_normalize_path(path),
                primary_lang=bot_settings.primary_lang,
                managers=bot_settings.managers,
                secret_token=settings.webhook_secret_token or "",
            )
        )
    return configs

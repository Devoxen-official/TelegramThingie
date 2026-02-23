from dataclasses import dataclass
from typing import List, Optional, Dict

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as OrmSession

from src.config import Settings, BotSettings, ManagerSettings
from src.db.models import BotConfigModel, ManagerConfigModel


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

    # Load bot configs from a separate sync SQLite database (telegram_bot_configs.db)
    # Using sync SQLAlchemy here to keep this function synchronous.
    configs_db_url = "sqlite:///telegram_bot_configs.db"
    engine = create_engine(configs_db_url, future=True)

    with OrmSession(engine) as session:
        bots = session.execute(select(BotConfigModel)).scalars().all()
        for bot in bots:
            mgr_rows = session.execute(
                select(ManagerConfigModel).where(ManagerConfigModel.bot_id == bot.id)
            ).scalars().all()
            managers: Dict[str, ManagerSettings] = {}
            for m in mgr_rows:
                managers[m.manager_id] = ManagerSettings(
                    name=m.name,
                    greeting=m.greeting,
                    script_paths=m.script_paths or [],
                    lang=m.lang or "en",
                )

            if len(bots) == 1:
                path = _normalize_path(settings.webhook_path)
            else:
                path = f"{settings.webhook_path_prefix}/{bot.name}"

            configs.append(
                BotConfig(
                    name=bot.name,
                    token=bot.token,
                    webhook_path=_normalize_path(path),
                    primary_lang=bot.primary_lang,
                    managers=managers,
                    secret_token=settings.webhook_secret_token or "",
                )
            )

    return configs

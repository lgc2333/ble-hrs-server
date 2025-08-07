from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

CONFIG_FILE = Path.cwd() / "config.json"


class Config(BaseModel):
    log_level: str = "INFO"
    server_host: str = "127.0.0.1"
    server_port: int = 11642
    server_cors_origins: list[str] = ["*"]
    server_static_dir: Path | None = Path.cwd() / "web/packages/frontend/dist"

    last_device_address: str | None = None
    device_discover_delay: float = 3.0
    conn_retry_interval: float = 1.0


if TYPE_CHECKING:

    class ConfigManager(Config):
        def __init__(self) -> None:
            self._config: Config | None = None

        def init(self) -> Config: ...
        def save(self) -> None: ...

else:

    class ConfigManager:
        def __init__(self) -> None:
            self._config: Config | None = None

        def __getattr__(self, item: str) -> Any:
            config = self.init() if (self._config is None) else self._config
            return getattr(config, item)

        def __setattr__(self, name: str, value: Any) -> None:
            if name.startswith("_"):
                return super().__setattr__(name, value)
            return setattr(self._config, name, value)

        def init(self) -> Config:
            if not CONFIG_FILE.exists():
                self._config = Config()
            else:
                self._config = Config.model_validate_json(CONFIG_FILE.read_text("u8"))
            self.save()
            return self._config

        def save(self) -> None:
            if self._config is None:
                raise ValueError("Config not initialized.")
            CONFIG_FILE.write_text(self._config.model_dump_json(indent=2), "u8")


config = ConfigManager()

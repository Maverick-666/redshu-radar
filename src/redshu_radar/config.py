from dataclasses import dataclass
from pathlib import Path


def default_data_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "RedshuRadar"


@dataclass(frozen=True)
class Settings:
    data_dir: Path = default_data_dir()
    host: str = "127.0.0.1"
    port: int = 8765

    @property
    def database_path(self) -> Path:
        return self.data_dir / "redshu-radar.sqlite3"

    @property
    def log_path(self) -> Path:
        return self.data_dir / "redshu-radar.log"

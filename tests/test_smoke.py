from pathlib import Path

import redshu_radar
from redshu_radar.cli import main
from redshu_radar.config import Settings


def test_package_imports() -> None:
    assert redshu_radar.__version__ == "0.1.0"


def test_settings_build_paths_inside_data_directory(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)

    assert settings.database_path == tmp_path / "redshu-radar.sqlite3"
    assert settings.log_path == tmp_path / "redshu-radar.log"


def test_cli_reports_version(capsys) -> None:
    exit_code = main(["--version"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "redshu-radar 0.1.0"

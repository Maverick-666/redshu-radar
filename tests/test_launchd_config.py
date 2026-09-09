import os
import plistlib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from redshu_radar.services.scheduling import daily_anchor_due


ROOT = Path(__file__).parents[1]
TEMPLATE = ROOT / "launchd" / "com.maverick.redshu-radar.daily.plist.template"
INSTALLER = ROOT / "scripts" / "install-launch-agent.sh"
UNINSTALLER = ROOT / "scripts" / "uninstall-launch-agent.sh"
SHANGHAI = ZoneInfo("Asia/Shanghai")


def test_daily_anchor_becomes_due_after_0002() -> None:
    last_success = datetime(2026, 9, 8, 0, 2, tzinfo=SHANGHAI)

    assert daily_anchor_due(last_success, datetime(2026, 9, 9, 0, 1, tzinfo=SHANGHAI)) is False
    assert daily_anchor_due(last_success, datetime(2026, 9, 9, 0, 3, tzinfo=SHANGHAI)) is True


def test_daily_anchor_is_due_when_no_success_exists() -> None:
    assert daily_anchor_due(None, datetime(2026, 9, 9, 12, 0, tzinfo=SHANGHAI)) is True


def test_launchd_template_runs_daily_collection_under_caffeinate() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    rendered = text.replace("__PROJECT_DIR__", "/tmp/project").replace(
        "__DATA_DIR__", "/tmp/data"
    )
    config = plistlib.loads(rendered.encode())

    assert config["Label"] == "com.maverick.redshu-radar.daily"
    assert config["StartCalendarInterval"] == {"Hour": 0, "Minute": 2}
    assert config["ProgramArguments"][:2] == ["/usr/bin/caffeinate", "-i"]
    assert "collect" in config["ProgramArguments"]
    assert "daily" in config["ProgramArguments"]
    assert "pmset" not in text


def test_launch_agent_scripts_are_executable_and_uninstall_preserves_data() -> None:
    assert os.access(INSTALLER, os.X_OK)
    assert os.access(UNINSTALLER, os.X_OK)
    uninstall_text = UNINSTALLER.read_text(encoding="utf-8")
    assert "redshu-radar.sqlite3" not in uninstall_text
    assert "Application Support/RedshuRadar" not in uninstall_text

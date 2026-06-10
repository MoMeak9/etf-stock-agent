from pathlib import Path
from typing import Any, Dict


def reports_dir_from_config(config: Dict[str, Any]) -> Path:
    """Return the configured report directory, falling back to the legacy path."""
    reports_dir = config.get("reports_dir")
    if reports_dir:
        return Path(str(reports_dir)).expanduser()

    project_dir = Path(str(config.get("project_dir", ".")))
    return project_dir / "docs" / "reports"


def report_path_for(ticker: str, trade_date: str, config: Dict[str, Any]) -> Path:
    return reports_dir_from_config(config) / f"{ticker}_{trade_date}_report.md"

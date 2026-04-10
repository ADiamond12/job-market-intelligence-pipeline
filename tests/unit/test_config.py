from __future__ import annotations

from pathlib import Path

from jobintel.config import load_config


def test_comparison_scope_is_stable_across_fixture_changes(tmp_path: Path) -> None:
    fixture_a = tmp_path / "fixture-a.json"
    fixture_b = tmp_path / "fixture-b.json"
    fixture_a.write_text("{}", encoding="utf-8")
    fixture_b.write_text("{}", encoding="utf-8")

    config_a = tmp_path / "config-a.yaml"
    config_b = tmp_path / "config-b.yaml"
    config_a.write_text(
        f"""
project_name: Job Market Intelligence Pipeline
companies:
  - name: Acme Analytics
    source_type: greenhouse
    identifier: acme-analytics
    fixture_path: {fixture_a.as_posix()}
  - name: BrightOps
    source_type: lever
    identifier: brightops
    fixture_path: {fixture_a.as_posix()}
""".strip(),
        encoding="utf-8",
    )
    config_b.write_text(
        f"""
project_name: Job Market Intelligence Pipeline
ai:
  enabled: true
companies:
  - name: Acme Analytics
    source_type: greenhouse
    identifier: acme-analytics
    fixture_path: {fixture_b.as_posix()}
  - name: BrightOps
    source_type: lever
    identifier: brightops
    fixture_path: {fixture_b.as_posix()}
""".strip(),
        encoding="utf-8",
    )

    app_config_a = load_config(config_a)
    app_config_b = load_config(config_b)

    assert app_config_a.comparison_scope == app_config_b.comparison_scope


def test_named_history_scope_overrides_default_comparison_scope(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
project_name: Job Market Intelligence Pipeline
history_scope: athens-data-watch
companies:
  - name: Acme Analytics
    source_type: greenhouse
    identifier: acme-analytics
""".strip(),
        encoding="utf-8",
    )

    app_config = load_config(config_path)

    assert app_config.comparison_scope == "named:athens-data-watch"

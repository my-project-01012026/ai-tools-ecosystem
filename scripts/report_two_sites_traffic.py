#!/usr/bin/env python3
"""Privacy-respecting report from two *different* native analytics systems.

here.now: first-party API JSON for an owned, published site.
ChatGPT Sites: manually transcribed, non-sensitive aggregate figures from Sites > Analytics.
This script never accesses external services and never commits visitor data.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any
from report_herenow_traffic import build_report


def _data(path: str) -> dict[str, Any]:
    source = Path(path)
    if source.stat().st_size > 2_000_000:
        raise ValueError("Analytics snapshot is too large.")
    with source.open("r", encoding="utf-8") as fh:
        obj = json.load(fh)
    if not isinstance(obj, dict):
        raise ValueError("Expected a JSON object.")
    return obj


def _metric(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        v = int(value)
        return v if v >= 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def _display(v: int | None) -> str:
    return str(v) if v is not None else "не указано"


def report(here_now: dict | None, sites: dict | None, slug: str, period: str) -> str:
    output = ["СВОДКА ПО ДВУМ НЕЗАВИСИМЫМ САЙТАМ", f"Выбранный период: {period}", ""]
    output.append("1. AI TOOLS ECOSYSTEM — here.now")
    if here_now is None:
        output.append("Нет подключённого отчёта here.now: числа неизвестны.")
    else:
        output.append(build_report(here_now, slug, period))
    output.extend(["", "2. LOCAL MEDIA AI — ChatGPT Sites"])
    if sites is None:
        output.append("Не введены показатели из Sites > Analytics: числа неизвестны.")
    else:
        recorded_period = sites.get("period")
        if recorded_period != period:
            raise ValueError("Periods must match; never compare different time ranges.")
        views = _metric(sites.get("page_views"))
        visitors = _metric(sites.get("unique_visitors"))
        output.append(f"Просмотры: {_display(views)}")
        output.append(f"Уникальные посетители: {_display(visitors)}")
        output.append("Страны: не предоставляются подтверждённой встроенной аналитикой Sites.")
        output.append("Источники переходов: не предоставляются подтверждённой встроенной аналитикой Sites.")
        output.append("Скриншоты/агрегаты в GitHub не загружать без отдельного разрешения.")
    output.extend([
        "",
        "ВАЖНО:",
        "- Разные платформы могут считать просмотры и посетителей по-разному; суммы нельзя трактовать как точный общий охват.",
        "- На here.now география и источники ранжируются по просмотрам.",
        "- Нельзя определить, какой конкретно адресат письма посещал сайт.",
        "- Никакие персональные данные посетителей не собираются этим скриптом.",
    ])
    return "\n".join(output)


def main() -> int:
    p = argparse.ArgumentParser(description="Read-only summary: here.now + ChatGPT Sites")
    p.add_argument("--here-now-json", help="Private here.now API JSON saved outside git")
    p.add_argument("--sites-json", help="Manual ChatGPT Sites aggregate JSON saved outside git")
    p.add_argument("--site-slug", default="site-not-confirmed")
    p.add_argument("--range", choices=("24h", "7d", "30d", "90d", "all"), default="7d")
    args = p.parse_args()
    try:
        first = _data(args.here_now_json) if args.here_now_json else None
        second = _data(args.sites_json) if args.sites_json else None
        print(report(first, second, args.site_slug, args.range))
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print("Некорректные входные данные: проверьте формат и период.", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

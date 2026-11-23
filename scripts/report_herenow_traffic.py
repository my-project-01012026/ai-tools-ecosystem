#!/usr/bin/env python3
"""Read private, aggregated here.now traffic analytics. No site code or cookies."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

VALID_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RANGES = ("24h", "7d", "30d", "90d", "all")
COUNTRIES = {
    "KZ": "Казахстан", "US": "США", "RU": "Россия", "GB": "Великобритания",
    "DE": "Германия", "FR": "Франция", "IN": "Индия", "CN": "Китай",
    "TR": "Турция", "UA": "Украина", "AE": "ОАЭ", "JP": "Япония",
    "KR": "Южная Корея", "CA": "Канада", "NL": "Нидерланды",
}


class AnalyticsError(Exception):
    """Safe error message; never includes secrets or full URLs."""


def _clean(value: object) -> str:
    """Make external labels safe for terminal output."""
    return re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", str(value))[:120].strip()


def read_analytics(slug: str, period: str, key: str, opener=None) -> dict:
    if not VALID_SLUG.fullmatch(slug):
        raise AnalyticsError("Неверный slug сайта (допустимы буквы a-z, цифры, дефисы).")
    if period not in RANGES:
        raise AnalyticsError("Недопустимый период.")
    if not key:
        raise AnalyticsError("Требуется HERENOW_API_KEY в окружении (не передавайте ключ в аргументах).")
    url = f"https://here.now/api/v1/publishes/{quote(slug, safe='')}/analytics?range={period}"
    request = Request(url, headers={
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "User-Agent": "AI-Tools-Ecosystem-ReadOnly-Analytics/1.0",
    }, method="GET")
    try:
        transport = opener or urlopen
        with transport(request, timeout=20) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise AnalyticsError("Ответ аналитики превышает допустимый размер.")
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise AnalyticsError("Некорректный формат ответа аналитики.")
        return payload
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise AnalyticsError("Нет доступа: проверьте ключ, владение сайтом и тариф here.now.") from None
        if exc.code == 402:
            raise AnalyticsError("Для API аналитики here.now требуется платный тариф.") from None
        if exc.code == 404:
            raise AnalyticsError("Сайт или аналитика не найдены; проверьте slug.") from None
        raise AnalyticsError(f"Сервис here.now вернул HTTP {exc.code}.") from None
    except (URLError, TimeoutError):
        raise AnalyticsError("Не удалось подключиться к here.now.") from None
    except (UnicodeError, ValueError):
        raise AnalyticsError("Не удалось прочитать JSON аналитики.") from None


def _number(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def _ranking(data: dict, field: str, name_field: str, limit: int = 10) -> list[tuple[str, int]]:
    values = data.get(field)
    if not isinstance(values, list):
        return []
    grouped: dict[str, int] = {}
    for record in values:
        if not isinstance(record, dict):
            continue
        name = _clean(record.get(name_field, ""))
        count = _number(record.get("views", 0))
        if name and count:
            grouped[name] = grouped.get(name, 0) + count
    return sorted(grouped.items(), key=lambda item: (-item[1], item[0]))[:limit]


def build_report(data: dict, slug: str, period: str) -> str:
    totals = data.get("totals")
    totals = totals if isinstance(totals, dict) else {}
    views = _number(totals.get("rangeViews"))
    visitors = _number(totals.get("rangeVisitors"))
    all_views = _number(totals.get("allTimeViews"))
    lines = [
        f"СТАТИСТИКА САЙТА: {_clean(slug)}",
        f"Период: {period}",
        f"Просмотры: {views}",
        f"Посетители (приблизительно): {visitors}",
        f"Просмотры за всё время сбора: {all_views}",
        "",
    ]

    def add_section(label: str, field: str, name_field: str, country: bool = False) -> None:
        lines.append(label)
        ranked = _ranking(data, field, name_field)
        if not ranked:
            lines.append("  Нет данных")
            return
        for idx, (name, count) in enumerate(ranked, 1):
            display = f"{COUNTRIES.get(name.upper(), name)} ({name})" if country else name
            share = f" — {count * 100 / views:.1f}%" if views else ""
            lines.append(f"  {idx}. {display}: {count}{share}")

    add_section("СТРАНЫ (где просмотров больше):", "topCountries", "country", True)
    lines.append("")
    add_section("ИСТОЧНИКИ ПЕРЕХОДОВ:", "topReferrers", "referrer")
    lines.append("")
    add_section("ПОПУЛЯРНЫЕ СТРАНИЦЫ:", "topPaths", "path")
    crawlers = data.get("topCrawlers")
    if isinstance(crawlers, list) and crawlers:
        hits = sum(_number(c.get("hits")) for c in crawlers if isinstance(c, dict))
        lines.append("")
        lines.append(f"Отдельные запросы известных роботов: {hits} (не считаются просмотрами)")
    lines.extend(["", "Показатели приблизительные; по ним нельзя установить личности посетителей."])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Приватный отчёт о посещаемости here.now")
    parser.add_argument("--slug", default=os.getenv("HERENOW_SITE_SLUG"),
                        help="Slug сайта вида example-123 (или HERENOW_SITE_SLUG)")
    parser.add_argument("--range", choices=RANGES, default="30d")
    arguments = parser.parse_args(argv)
    if not arguments.slug:
        parser.error("Укажите --slug или HERENOW_SITE_SLUG")
    try:
        data = read_analytics(arguments.slug, arguments.range,
                              os.getenv("HERENOW_ANALYTICS_KEY") or os.getenv("HERENOW_API_KEY", ""))
    except AnalyticsError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2
    print(build_report(data, arguments.slug, arguments.range))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

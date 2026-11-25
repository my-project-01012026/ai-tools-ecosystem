import json
import unittest
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
LANGS = {"en", "ru", "kk", "zh-CN", "de", "fr", "ar", "ja", "ko"}

class LanguageLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.locales = set()
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("hreflang") == a.get("lang") and a.get("lang"):
            self.locales.add(a["lang"])

class PriorityLocaleTests(unittest.TestCase):
    def test_menu_and_inventory(self):
        status = json.loads((ROOT / "data/i18n-status.json").read_text(encoding="utf-8"))
        self.assertEqual(set(status["languages"]), LANGS)
        paths = {line.split("  ", 1)[1] for line in (ROOT / "scripts/SITE_SHA256SUMS.txt").read_text().splitlines()}
        for lang in LANGS:
            self.assertIn("index.html" if lang == "en" else lang + "/index.html", paths)
        for lang in status["reserve_languages"]:
            self.assertNotIn(lang + "/index.html", paths)
            self.assertTrue((ROOT / lang / "index.html").is_file())
        for path in paths:
            if path.endswith(".html"):
                parser = LanguageLinks()
                parser.feed((ROOT / path).read_text(encoding="utf-8"))
                self.assertEqual(parser.locales, LANGS, path)
    def test_arabic_direction(self):
        self.assertIn('<html lang="ar" dir="rtl">', (ROOT / "ar/index.html").read_text(encoding="utf-8"))

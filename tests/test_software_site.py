"""Offline integrity, link and product-claim tests for the static portfolio."""
import hashlib
import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scripts" / "SITE_SHA256SUMS.txt"
class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs=[]
        self.ids=set()
        self.styles=[]
        self.scripts=[]
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if "id" in d: self.ids.add(d["id"])
        if tag in ("a","link") and "href" in d: self.hrefs.append(d["href"])
        if tag == "link" and d.get("rel") == "stylesheet": self.styles.append(d)
        if tag == "script": self.scripts.append(d)
class SoftwarePortfolioChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files={}
        for line in MANIFEST.read_text(encoding="utf-8").splitlines():
            match=re.fullmatch(r"([a-f0-9]{64})  ([A-Za-z0-9._/-]+)",line)
            assert match, "invalid manifest entry"
            digest,name=match.groups()
            assert name not in cls.files, name
            cls.files[name]=digest
    def test_frozen_files(self):
        self.assertEqual(len(self.files),33)
        for name,expected in self.files.items():
            file=ROOT/name
            self.assertTrue(file.is_file(),name)
            self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),expected,name)
    def test_no_obsolete_material_in_published_bundle(self):
        all_names=set(self.files)
        for name in ("data/tokenomics.json","assets/app.js","token/index.html","ru/token/index.html","assets/og-cover.png"):
            self.assertNotIn(name,all_names)
        self.assertIn("cvlm/index.html",all_names)
        self.assertIn("ru/cvlm/index.html",all_names)
        self.assertIn("localaidevmanager/index.html",all_names)
        self.assertIn("ru/localaidevmanager/index.html",all_names)
    def test_links_integrity_and_no_scripts(self):
        stylesheet=ROOT/"assets/styles.css"
        sri="sha384-"+__import__("base64").b64encode(hashlib.sha384(stylesheet.read_bytes()).digest()).decode("ascii")
        for filename in (name for name in self.files if name.endswith(".html")):
            html=(ROOT/filename).read_text(encoding="utf-8")
            self.assertIn('<meta name="robots" content="noindex,nofollow"',html,filename)
            self.assertIn('Content-Security-Policy',html,filename)
            self.assertNotRegex(html,re.compile(r"(?i)\\bsolana\\b|\\btokenomics\\b|\\braydium\\b|токен|криптовалют",re.UNICODE),filename)
            parser=Parser();parser.feed(html)
            self.assertFalse(parser.scripts,filename)
            self.assertTrue(parser.styles,filename)
            self.assertEqual(parser.styles[0].get("integrity"),sri,filename)
            for href in parser.hrefs:
                if href.startswith("https://"):
                    self.assertTrue(href.startswith("https://local-media-ai-community.cheekysloth259.chatgpt.site/"),(filename,href))
                elif href.startswith("/"):
                    path=href.split("#",1)[0].split("?",1)[0]
                    item=(path.lstrip("/")+"index.html") if path.endswith("/") else path.lstrip("/")
                    self.assertIn(item,self.files,(filename,href))
                elif href.startswith("#"):
                    self.assertIn(href[1:],parser.ids,(filename,href))
                else:
                    self.fail("unexpected URL: "+filename+" "+href)
    def test_all_homepages_explain_three_products(self):
        for lang in ("en","ru","es","pt-BR","ja","ko","hi","uk","th","id","vi","tr"):
            name="index.html" if lang=="en" else lang+"/index.html"
            html=(ROOT/name).read_text(encoding="utf-8")
            for product in ("Local Media AI","CVLM Platform","LocalAIDevManager"):
                self.assertIn("<h3>"+product+"</h3>",html,(name,product))
            self.assertIn("https://local-media-ai-community.cheekysloth259.chatgpt.site/",html,name)
    def test_status_is_consistent(self):
        data=json.loads((ROOT/"data/status.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["products"]),3)
        self.assertEqual(data["products"][0]["installer"],"NOT_PUBLICLY_RELEASED")
        self.assertEqual(data["products"][1]["stage"],"CONCEPT_DESIGN")
        self.assertEqual(data["products"][2]["stage"],"CONCEPT_DESIGN")
if __name__=="__main__":
    unittest.main()

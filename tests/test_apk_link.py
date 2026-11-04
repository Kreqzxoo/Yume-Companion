import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.utils.apk_link import pick_apk_url, releases_page

REPO = "Kreqzxoo/Yume-Companion"
BASE = f"https://github.com/{REPO}/releases/download/"


def rel(tag, *names, draft=False):
    return {"tag_name": tag, "draft": draft,
            "assets": [{"name": n, "state": "uploaded", "browser_download_url": f"{BASE}{tag}/{n}"} for n in names]}


class ApkLinkTest(unittest.TestCase):
    def test_newest_release_with_an_apk_wins(self):
        releases = [rel("v3.0.0-beta13", "Yume-Companion-Setup-3.0.0-beta13.exe"), rel("v3.0.0-beta11", "Yume-Companion.apk"), rel("v3.0.0-beta10", "Yume-Companion.apk")]
        self.assertEqual(pick_apk_url(releases, REPO), BASE + "v3.0.0-beta11/Yume-Companion.apk")

    def test_drafts_and_foreign_addresses_are_ignored(self):
        releases = [rel("v3.0.0-beta14", "Yume-Companion.apk", draft=True)]
        foreign = rel("v3.0.0-beta15", "Yume-Companion.apk")
        foreign["assets"][0]["browser_download_url"] = "https://evil.example/releases/download/v3.0.0-beta15/Yume-Companion.apk"
        self.assertEqual(pick_apk_url(releases + [foreign], REPO), "")
        self.assertEqual(pick_apk_url([{"tag_name": "x", "assets": None}, "text"], REPO), "")

    def test_releases_page(self):
        self.assertEqual(releases_page(REPO), "https://github.com/Kreqzxoo/Yume-Companion/releases")


if __name__ == "__main__":
    unittest.main()

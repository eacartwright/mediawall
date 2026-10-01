import os
import unittest

from core.recent import MAX_RECENT, with_recent, without_recent


class RecentTests(unittest.TestCase):

    def test_newest_first_without_duplicates(self):
        paths = with_recent([], "/w/a.mediawall")
        paths = with_recent(paths, "/w/b.mediawall")
        paths = with_recent(paths, "/w/a.mediawall")
        self.assertEqual(paths, ["/w/a.mediawall", "/w/b.mediawall"])

    def test_limited(self):
        paths = []
        for i in range(MAX_RECENT + 3):
            paths = with_recent(paths, f"/w/{i}.mediawall")
        self.assertEqual(len(paths), MAX_RECENT)
        self.assertEqual(paths[0], f"/w/{MAX_RECENT + 2}.mediawall")

    def test_remove(self):
        self.assertEqual(without_recent(["/w/a.mediawall", "/w/b.mediawall"], "/w/a.mediawall"),
                         ["/w/b.mediawall"])

    @unittest.skipUnless(os.name == "nt", "Windows paths only")
    def test_windows_case_insensitive(self):
        self.assertEqual(with_recent(["C:/W/A.mediawall"], "c:/w/a.mediawall"),
                         ["c:/w/a.mediawall"])


if __name__ == "__main__":
    unittest.main()

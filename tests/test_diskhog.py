import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from diskhog import find_duplicates, human, parse_size, scan  # noqa: E402


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)


class DiskHogTests(unittest.TestCase):
    def test_human(self):
        self.assertEqual(human(512), "512 B")
        self.assertEqual(human(1536), "1.5 KB")
        self.assertEqual(human(5 * 1024**2), "5.0 MB")

    def test_parse_size(self):
        self.assertEqual(parse_size("500"), 500)
        self.assertEqual(parse_size("10K"), 10 * 1024)
        self.assertEqual(parse_size("2MB"), 2 * 1024**2)

    def test_scan_and_dir_totals(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "a", "big.bin"), b"x" * 1000)
            write(os.path.join(tmp, "a", "b", "small.bin"), b"y" * 10)
            write(os.path.join(tmp, "top.txt"), b"z" * 5)
            files, dirs = scan(tmp)
            root = os.path.abspath(tmp)
            self.assertEqual([size for size, _ in files], [1000, 10, 5])
            self.assertEqual(dirs[root], 1015)
            self.assertEqual(dirs[os.path.join(root, "a")], 1010)
            self.assertEqual(dirs[os.path.join(root, "a", "b")], 10)

    def test_min_size_and_exclude(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "keep", "k.bin"), b"k" * 100)
            write(os.path.join(tmp, "skip", "s.bin"), b"s" * 100)
            files, _ = scan(tmp, min_size=50, exclude={"skip"})
            self.assertEqual(len(files), 1)
            self.assertTrue(files[0][1].endswith("k.bin"))

    def test_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "one.txt"), b"same content")
            write(os.path.join(tmp, "sub", "two.txt"), b"same content")
            write(os.path.join(tmp, "other.txt"), b"diff content")
            files, _ = scan(tmp)
            groups = find_duplicates(files)
            self.assertEqual(len(groups), 1)
            self.assertEqual(len(groups[0][1]), 2)


if __name__ == "__main__":
    unittest.main()

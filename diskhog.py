#!/usr/bin/env python3
"""diskhog - find the biggest files, folders and duplicate files (zero dependencies)."""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from collections import defaultdict

__version__ = "1.0.0"


def human(size: float) -> str:
    """Format a byte count, e.g. 1536 -> '1.5 KB'."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def parse_size(text: str) -> int:
    """Parse sizes like '500', '10K', '5M', '2G'."""
    text = text.strip().upper().rstrip("B")
    units = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    if text and text[-1] in units:
        return int(float(text[:-1]) * units[text[-1]])
    return int(float(text))


def scan(root: str, min_size: int = 0, exclude=()):
    """Walk `root`. Returns (files, dir_sizes) with files as [(size, path)]."""
    root = os.path.abspath(root)
    files: list[tuple[int, str]] = []
    dirs: dict[str, int] = defaultdict(int)
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in exclude and not os.path.islink(os.path.join(current, d))
        ]
        for name in filenames:
            path = os.path.join(current, name)
            try:
                if os.path.islink(path):
                    continue
                size = os.path.getsize(path)
            except OSError:
                continue
            if size >= min_size:
                files.append((size, path))
            parent = current
            while True:
                dirs[parent] += size
                if parent == root:
                    break
                parent = os.path.dirname(parent)
    files.sort(reverse=True)
    return files, dict(dirs)


def _sha256(path: str) -> str | None:
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def find_duplicates(files):
    """Group identical files. Returns [(size, [paths])] sorted by wasted space."""
    by_size: dict[int, list[str]] = defaultdict(list)
    for size, path in files:
        if size > 0:
            by_size[size].append(path)
    groups = []
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        by_hash: dict[str, list[str]] = defaultdict(list)
        for path in paths:
            digest = _sha256(path)
            if digest:
                by_hash[digest].append(path)
        groups.extend((size, sorted(p)) for p in by_hash.values() if len(p) > 1)
    groups.sort(key=lambda g: g[0] * (len(g[1]) - 1), reverse=True)
    return groups


def bar(value: float, maximum: float, width: int = 20) -> str:
    filled = 0 if maximum <= 0 else round(width * value / maximum)
    return "█" * filled + "░" * (width - filled)


def print_table(title: str, rows, root: str) -> None:
    print(f"\n{title}")
    if not rows:
        print("  (nothing found)")
        return
    maximum = rows[0][0]
    for size, path in rows:
        rel = os.path.relpath(path, root)
        print(f"  {human(size):>9}  {bar(size, maximum)}  {rel}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="diskhog", description="Find what is eating your disk space."
    )
    parser.add_argument("path", nargs="?", default=".", help="folder to scan (default: .)")
    parser.add_argument("-n", "--top", type=int, default=10, help="rows to show (default: 10)")
    parser.add_argument("--min-size", default="0", help="ignore files smaller than e.g. 10M")
    parser.add_argument("--dupes", action="store_true", help="also find duplicate files")
    parser.add_argument(
        "--exclude", action="append", default=[], metavar="NAME", help="skip folders with this name"
    )
    parser.add_argument("--version", action="version", version=f"diskhog {__version__}")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if not os.path.isdir(args.path):
        print(f"diskhog: not a folder: {args.path}", file=sys.stderr)
        return 2
    root = os.path.abspath(args.path)
    files, dirs = scan(root, parse_size(args.min_size), set(args.exclude))
    total = sum(dirs.get(root, 0) for _ in [0])
    print(f"Scanned {root}: {len(files)} files, {human(total)} total")

    print_table(f"Top {args.top} biggest files", files[: args.top], root)
    top_dirs = sorted(
        ((size, path) for path, size in dirs.items() if path != root), reverse=True
    )[: args.top]
    print_table(f"Top {args.top} biggest folders", top_dirs, root)

    if args.dupes:
        groups = find_duplicates(files)
        wasted = sum(size * (len(paths) - 1) for size, paths in groups)
        print(f"\nDuplicate files: {len(groups)} groups, {human(wasted)} wasted")
        for size, paths in groups[: args.top]:
            print(f"  {human(size)} x {len(paths)}")
            for path in paths:
                print(f"    {os.path.relpath(path, root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

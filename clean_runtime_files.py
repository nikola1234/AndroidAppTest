from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIRS = ("generated", "reports", "artifacts")
CACHE_DIR_NAMES = ("__pycache__", ".pytest_cache")
CACHE_FILE_SUFFIXES = (".pyc", ".pyo", ".pyd")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delete files generated while running android_test_agent.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting it.")
    parser.add_argument(
        "--include-knowledge",
        action="store_true",
        help="Also delete ignored JSON memory files under knowledge/.",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    deleted: list[Path] = []

    for dirname in OUTPUT_DIRS:
        clean_directory(PROJECT_ROOT / dirname, deleted, dry_run=args.dry_run)

    remove_cache_dirs(deleted, dry_run=args.dry_run)
    remove_cache_files(deleted, dry_run=args.dry_run)

    if args.include_knowledge:
        remove_knowledge_json(deleted, dry_run=args.dry_run)

    action = "Would delete" if args.dry_run else "Deleted"
    unique_deleted = sorted(dict.fromkeys(deleted), key=lambda path: str(path))
    if not unique_deleted:
        print("No runtime files found.")
        return

    print(f"{action} {len(unique_deleted)} item(s):")
    for path in unique_deleted:
        print(f"- {path.relative_to(PROJECT_ROOT)}")


def clean_directory(directory: Path, deleted: list[Path], *, dry_run: bool) -> None:
    if not directory.exists():
        return
    for child in directory.iterdir():
        if child.name == ".gitkeep":
            continue
        if child.is_dir():
            clean_directory(child, deleted, dry_run=dry_run)
            if not contains_gitkeep(child) and not any(child.iterdir()):
                remove_path(child, deleted, dry_run=dry_run)
            continue
        remove_path(child, deleted, dry_run=dry_run)


def remove_cache_dirs(deleted: list[Path], *, dry_run: bool) -> None:
    for name in CACHE_DIR_NAMES:
        for directory in PROJECT_ROOT.rglob(name):
            if is_inside_venv(directory):
                continue
            remove_path(directory, deleted, dry_run=dry_run)


def remove_cache_files(deleted: list[Path], *, dry_run: bool) -> None:
    for suffix in CACHE_FILE_SUFFIXES:
        for file_path in PROJECT_ROOT.rglob(f"*{suffix}"):
            if is_inside_venv(file_path):
                continue
            remove_path(file_path, deleted, dry_run=dry_run)


def remove_knowledge_json(deleted: list[Path], *, dry_run: bool) -> None:
    knowledge_dir = PROJECT_ROOT / "knowledge"
    if not knowledge_dir.exists():
        return
    for file_path in knowledge_dir.rglob("*.json"):
        remove_path(file_path, deleted, dry_run=dry_run)


def remove_path(path: Path, deleted: list[Path], *, dry_run: bool) -> None:
    if not path.exists():
        return
    record_deleted(path, deleted)
    if dry_run:
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def is_inside_venv(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    return ".venv" in parts or "venv" in parts


def contains_gitkeep(directory: Path) -> bool:
    return (directory / ".gitkeep").exists()


def record_deleted(path: Path, deleted: list[Path]) -> None:
    if any(is_relative_to(path, existing) for existing in deleted):
        return
    deleted[:] = [existing for existing in deleted if not is_relative_to(existing, path)]
    deleted.append(path)


def is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
    except ValueError:
        return False
    return path != other


if __name__ == "__main__":
    main()

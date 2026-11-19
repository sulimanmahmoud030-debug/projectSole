#!/usr/bin/env python3
"""
File Organizer - أداة فرز الملفات داخل مجلد حسب النوع و/أو التاريخ.

أمثلة:
    python organizer.py ~/Downloads --dry-run          # معاينة بدون تنفيذ
    python organizer.py ~/Downloads                    # فرز حسب النوع
    python organizer.py ~/Downloads --mode both        # النوع ثم الشهر
    python organizer.py ~/Downloads --undo             # التراجع عن آخر عملية
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# 1) الإعدادات: عدّل هنا لإضافة أنواع جديدة (قابل للتطوير بسهولة)
# ---------------------------------------------------------------------------
CATEGORIES: dict[str, set[str]] = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".heic"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".odt", ".rtf", ".md"},
    "Spreadsheets": {".xls", ".xlsx", ".csv", ".ods"},
    "Presentations": {".ppt", ".pptx", ".odp"},
    "Videos": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv"},
    "Audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Code": {".py", ".js", ".html", ".css", ".java", ".cpp", ".json", ".sql"},
    "Installers": {".exe", ".msi", ".dmg", ".apk", ".deb"},
}
OTHER_CATEGORY = "Other"      # أي امتداد غير معروف
LOG_NAME = ".organizer_log.json"  # ملف سجل العمليات (للتراجع)
MODES = ("type", "date", "both")


# ---------------------------------------------------------------------------
# 2) دوال مساعدة صغيرة (كل دالة لها مهمة واحدة)
# ---------------------------------------------------------------------------
def get_category(path: Path) -> str:
    """ترجع اسم الفئة بناءً على امتداد الملف."""
    ext = path.suffix.lower()
    for category, extensions in CATEGORIES.items():
        if ext in extensions:
            return category
    return OTHER_CATEGORY


def get_date_parts(path: Path) -> tuple[str, str]:
    """ترجع (السنة, الشهر) من تاريخ آخر تعديل للملف."""
    modified = datetime.fromtimestamp(path.stat().st_mtime)
    return f"{modified.year}", f"{modified.month:02d}"


def build_destination(path: Path, root: Path, mode: str) -> Path:
    """تحدد المسار الجديد للملف حسب نمط الفرز المختار."""
    if mode == "type":
        return root / get_category(path) / path.name
    year, month = get_date_parts(path)
    if mode == "date":
        return root / year / month / path.name
    # mode == "both"
    return root / get_category(path) / f"{year}-{month}" / path.name


def unique_path(dest: Path) -> Path:
    """لو الملف موجود بنفس الاسم، تضيف رقم (_1, _2, ...) بدل ما تمسحه."""
    if not dest.exists():
        return dest
    counter = 1
    while True:
        candidate = dest.with_name(f"{dest.stem}_{counter}{dest.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def list_files(root: Path) -> list[Path]:
    """ترجع الملفات الموجودة مباشرة في المجلد (بدون المجلدات والملفات المخفية)."""
    return sorted(
        p for p in root.iterdir() if p.is_file() and not p.name.startswith(".")
    )


def remove_empty_parents(folder: Path, stop_at: Path) -> None:
    """تمسح المجلدات الفاضية اللي فضلت بعد التراجع، وتقف عند المجلد الرئيسي."""
    while folder != stop_at and folder.is_dir():
        try:
            folder.rmdir()  # بتفشل لو المجلد مش فاضي، وده المطلوب
        except OSError:
            break
        folder = folder.parent


# ---------------------------------------------------------------------------
# 3) المنطق الرئيسي
# ---------------------------------------------------------------------------
def organize(root: Path, mode: str, dry_run: bool = False) -> tuple[int, int]:
    """تفرز الملفات. ترجع (عدد الملفات المنقولة, عدد الأخطاء)."""
    moved: list[dict[str, str]] = []
    errors = 0

    for src in list_files(root):
        try:
            dest = unique_path(build_destination(src, root, mode))
            shown = dest.relative_to(root)

            if dry_run:
                print(f"[DRY-RUN] {src.name}  ->  {shown}")
                moved.append({})  # للعدّ فقط
                continue

            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            moved.append({"from": str(src), "to": str(dest)})
            print(f"Moved: {src.name}  ->  {shown}")
        except (OSError, shutil.Error) as exc:
            errors += 1
            print(f"[ERROR] {src.name}: {exc}", file=sys.stderr)

    if moved and not dry_run:
        save_log(root, moved)
    return len(moved), errors


def save_log(root: Path, moves: list[dict[str, str]]) -> None:
    """تحفظ سجل آخر عملية عشان نقدر نتراجع عنها."""
    try:
        (root / LOG_NAME).write_text(
            json.dumps(moves, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as exc:
        print(f"[WARNING] Could not save undo log: {exc}", file=sys.stderr)


def undo(root: Path) -> int:
    """تتراجع عن آخر عملية فرز. ترجع كود الخروج (0 = نجاح)."""
    log_file = root / LOG_NAME
    if not log_file.exists():
        print("Nothing to undo: no log file found.", file=sys.stderr)
        return 1

    try:
        entries = json.loads(log_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[ERROR] Could not read log file: {exc}", file=sys.stderr)
        return 1

    restored = 0
    for entry in reversed(entries):
        current, original = Path(entry["to"]), Path(entry["from"])
        if not current.exists():
            print(f"[SKIP] Missing: {current.name}", file=sys.stderr)
            continue
        try:
            shutil.move(str(current), str(unique_path(original)))
            remove_empty_parents(current.parent, stop_at=root)
            restored += 1
            print(f"Restored: {original.name}")
        except (OSError, shutil.Error) as exc:
            print(f"[ERROR] {current.name}: {exc}", file=sys.stderr)

    log_file.unlink(missing_ok=True)
    print(f"\nDone. Restored {restored} file(s).")
    return 0


# ---------------------------------------------------------------------------
# 4) واجهة سطر الأوامر
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Organize files in a folder by type and/or date."
    )
    parser.add_argument("folder", help="Path of the folder to organize")
    parser.add_argument(
        "-m", "--mode", choices=MODES, default="type",
        help="type = by extension (default), date = Year/Month, both = Type/Year-Month",
    )
    parser.add_argument(
        "-d", "--dry-run", action="store_true",
        help="Preview what would happen without moving anything",
    )
    parser.add_argument(
        "-u", "--undo", action="store_true",
        help="Undo the last organize operation in this folder",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.folder).expanduser().resolve()

    if not root.exists():
        print(f"[ERROR] Folder not found: {root}", file=sys.stderr)
        return 1
    if not root.is_dir():
        print(f"[ERROR] Not a folder: {root}", file=sys.stderr)
        return 1

    if args.undo:
        return undo(root)

    try:
        count, errors = organize(root, args.mode, args.dry_run)
    except PermissionError:
        print(f"[ERROR] Permission denied: {root}", file=sys.stderr)
        return 1

    if count == 0 and errors == 0:
        print("No files to organize.")
    else:
        verb = "would be moved" if args.dry_run else "moved"
        print(f"\nSummary: {count} file(s) {verb}, {errors} error(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

"""اختبارات بسيطة. التشغيل:  pytest"""
import os
from datetime import datetime

import organizer


def make_file(folder, name, content="x"):
    path = folder / name
    path.write_text(content)
    return path


def test_get_category(tmp_path):
    assert organizer.get_category(tmp_path / "a.JPG") == "Images"
    assert organizer.get_category(tmp_path / "a.unknown") == "Other"


def test_organize_by_type(tmp_path):
    make_file(tmp_path, "photo.png")
    make_file(tmp_path, "report.pdf")
    organizer.main([str(tmp_path)])
    assert (tmp_path / "Images" / "photo.png").exists()
    assert (tmp_path / "Documents" / "report.pdf").exists()


def test_dry_run_moves_nothing(tmp_path):
    make_file(tmp_path, "photo.png")
    organizer.main([str(tmp_path), "--dry-run"])
    assert (tmp_path / "photo.png").exists()
    assert not (tmp_path / "Images").exists()


def test_duplicate_names_not_overwritten(tmp_path):
    (tmp_path / "Images").mkdir()
    make_file(tmp_path / "Images", "a.png", "old")
    make_file(tmp_path, "a.png", "new")
    organizer.main([str(tmp_path)])
    assert (tmp_path / "Images" / "a.png").read_text() == "old"
    assert (tmp_path / "Images" / "a_1.png").read_text() == "new"


def test_date_mode(tmp_path):
    f = make_file(tmp_path, "old.txt")
    ts = datetime(2023, 5, 10).timestamp()
    os.utime(f, (ts, ts))
    organizer.main([str(tmp_path), "--mode", "date"])
    assert (tmp_path / "2023" / "05" / "old.txt").exists()


def test_undo(tmp_path):
    make_file(tmp_path, "photo.png")
    organizer.main([str(tmp_path)])
    organizer.main([str(tmp_path), "--undo"])
    assert (tmp_path / "photo.png").exists()
    assert not (tmp_path / "Images").exists()


def test_invalid_folder_returns_error(tmp_path):
    assert organizer.main([str(tmp_path / "nope")]) == 1

import pytest


@pytest.fixture(autouse=True)
def isolated_sqlite_db(tmp_path, monkeypatch):
    """ทุกเทสต์ใช้ฐานข้อมูล SQLite ชั่วคราวของตัวเอง ไม่แตะข้อมูลจริง"""

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))

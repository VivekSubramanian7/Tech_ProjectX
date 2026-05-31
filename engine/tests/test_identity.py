from app.identity import file_id


def test_file_id_is_deterministic():
    a = file_id("local", "/data/root", "docs/a.txt")
    b = file_id("local", "/data/root", "docs/a.txt")
    assert a == b
    assert len(a) == 64


def test_file_id_differs_for_different_native_id():
    assert file_id("local", "/r", "a.txt") != file_id("local", "/r", "b.txt")

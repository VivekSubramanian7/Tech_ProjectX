from pathlib import Path

from app.sources import LocalFolderSource

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_iter_files_yields_metadata_without_reading_content(monkeypatch):
    reads: list[str] = []
    original_open = Path.open

    def tracking_open(self, *args, **kwargs):
        reads.append(str(self))
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", tracking_open)
    source = LocalFolderSource(FIXTURES)
    refs = list(source.iter_files())
    assert refs
    assert not reads
    assert all(r.size >= 0 for r in refs)


def test_open_yields_bounded_chunks():
    source = LocalFolderSource(FIXTURES)
    ref = next(source.iter_files())
    stream = source.open(ref)
    chunk = stream.read(1024)
    assert chunk
    stream.close()


def test_file_id_stable_across_runs():
    source = LocalFolderSource(FIXTURES)
    ids1 = [r.file_id for r in source.iter_files()]
    ids2 = [r.file_id for r in source.iter_files()]
    assert ids1 == ids2

"""Focused tests for collision-safe, run-scoped image persistence."""

import io
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest
from PIL import Image

import main


def _image_bytes(
    *,
    mode: str = "RGB",
    size: tuple[int, int] = (20, 10),
    image_format: str = "JPEG",
    orientation: int | None = None,
) -> bytes:
    buffer = io.BytesIO()
    image = Image.new(mode, size, color=(200, 20, 10, 128) if mode == "RGBA" else "red")
    exif = None
    if orientation is not None:
        exif = Image.Exif()
        exif[274] = orientation
    save_kwargs = {"exif": exif} if exif is not None else {}
    image.save(buffer, image_format, **save_kwargs)
    return buffer.getvalue()


def test_writer_uses_canonical_paths_and_separates_runs(tmp_path, monkeypatch):
    upload_root = tmp_path / "uploads"
    monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)

    first = main.write_upload_image(_image_bytes(), 7)
    second = main.write_upload_image(_image_bytes(), 8)

    for upload, run_id in ((first, 7), (second, 8)):
        prefix = f"static/uploads/beer_runs/{run_id}/"
        assert upload.image_path.startswith(prefix)
        assert upload.image_path.endswith(".jpg")
        UUID(upload.image_path.removeprefix(prefix).removesuffix(".jpg"))
        assert "\\" not in upload.image_path
        assert upload.physical_path.parent == upload_root / "beer_runs" / str(run_id)
        assert upload.physical_path.is_file()


def test_existing_uuid_candidate_is_preserved_and_next_candidate_is_used(
    tmp_path, monkeypatch
):
    upload_root = tmp_path / "uploads"
    run_directory = upload_root / "beer_runs" / "4"
    run_directory.mkdir(parents=True)
    collision = UUID("11111111-1111-4111-8111-111111111111")
    replacement = UUID("22222222-2222-4222-8222-222222222222")
    sentinel = run_directory / f"{collision}.jpg"
    sentinel.write_bytes(b"sentinel")
    candidates = iter((collision, replacement))
    monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
    monkeypatch.setattr(main, "uuid4", lambda: next(candidates))

    upload = main.write_upload_image(_image_bytes(), 4)

    assert sentinel.read_bytes() == b"sentinel"
    assert upload.physical_path.name == f"{replacement}.jpg"
    assert upload.physical_path.is_file()
    assert sorted(path.name for path in run_directory.iterdir()) == [
        f"{collision}.jpg",
        f"{replacement}.jpg",
    ]


def test_first_concurrent_writes_create_one_run_directory_and_keep_both_files(
    tmp_path, monkeypatch
):
    upload_root = tmp_path / "uploads"
    monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
    contents = _image_bytes()

    with ThreadPoolExecutor(max_workers=2) as executor:
        uploads = list(executor.map(lambda _: main.write_upload_image(contents, 12), range(2)))

    assert len({upload.image_path for upload in uploads}) == 2
    run_directory = upload_root / "beer_runs" / "12"
    assert run_directory.is_dir()
    assert len(list(run_directory.glob("*.jpg"))) == 2


def test_writer_applies_exif_orientation_and_longest_edge_limit(tmp_path, monkeypatch):
    upload_root = tmp_path / "uploads"
    monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)

    upload = main.write_upload_image(
        _image_bytes(size=(1200, 600), orientation=6),
        3,
    )

    with Image.open(upload.physical_path) as stored:
        assert stored.format == "JPEG"
        assert stored.mode == "RGB"
        assert stored.size == (540, 1080)


def test_writer_converts_rgba_input_to_optimized_jpeg(tmp_path, monkeypatch):
    upload_root = tmp_path / "uploads"
    monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)

    upload = main.write_upload_image(
        _image_bytes(mode="RGBA", size=(1200, 600), image_format="PNG"),
        9,
    )

    with Image.open(upload.physical_path) as stored:
        assert stored.format == "JPEG"
        assert stored.mode == "RGB"
        assert stored.size == (1080, 540)


@pytest.mark.parametrize("invalid_run_id", (0, -1, True, "../escape"))
def test_writer_rejects_non_positive_or_non_integer_run_ids(
    tmp_path, monkeypatch, invalid_run_id
):
    upload_root = tmp_path / "uploads"
    monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)

    with pytest.raises(ValueError):
        main.write_upload_image(_image_bytes(), invalid_run_id)

    assert not upload_root.exists()

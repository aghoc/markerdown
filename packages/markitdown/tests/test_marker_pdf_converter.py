import io
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from markitdown import MarkItDown, MissingDependencyException, StreamInfo
from markitdown.converters import MarkerPdfConverter
from markitdown.converters._marker_pdf_converter import (
    _configure_marker_torch_device,
    _select_marker_torch_device,
)

TEST_FILES_DIR = Path(__file__).parent / "test_files"


class FakeMarkerPdfConverter:
    def __init__(self, markdown="# Marker output", should_raise=False):
        self.markdown = markdown
        self.should_raise = should_raise
        self.seen_paths = []

    def __call__(self, source_path):
        assert os.path.exists(source_path)
        self.seen_paths.append(source_path)
        if self.should_raise:
            raise RuntimeError("marker failed")
        return SimpleNamespace(
            markdown=self.markdown,
            metadata={"title": "Marker title"},
            images={},
        )


class RepairableMarkerPdfConverter(MarkerPdfConverter):
    def __init__(self):
        super().__init__(marker_auto_repair=True)
        self.create_count = 0
        self.repair_count = 0

    def _create_marker_runtime(self):
        self.create_count += 1
        if self.repair_count == 0:
            raise MissingDependencyException("marker is missing")
        return FakeMarkerPdfConverter(markdown="repaired marker"), fake_text_from_rendered

    def _repair_marker_dependency(self, reason):
        self._marker_repair_attempted = True
        self.repair_count += 1


def fake_text_from_rendered(rendered):
    return rendered.markdown, {}, rendered.images


def fake_text_with_images(rendered):
    return rendered.markdown, {}, rendered.images


def test_marker_torch_device_prefers_marker_config(monkeypatch):
    monkeypatch.setenv("MARKERDOWN_TORCH_DEVICE", "cuda")

    assert _select_marker_torch_device({"torch_device": "cpu"}) == "cpu"


def test_marker_torch_device_prefers_cuda_then_mps(monkeypatch):
    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: True),
        backends=SimpleNamespace(
            mps=SimpleNamespace(is_available=lambda: True),
        ),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.delenv("MARKERDOWN_TORCH_DEVICE", raising=False)
    monkeypatch.delenv("TORCH_DEVICE", raising=False)

    assert _select_marker_torch_device() == "cuda"

    fake_torch.cuda.is_available = lambda: False
    assert _select_marker_torch_device() == "mps"


def test_configure_marker_torch_device_updates_marker_and_surya_settings(monkeypatch):
    monkeypatch.setenv("MARKERDOWN_TORCH_DEVICE", "mps")
    marker_settings_module = SimpleNamespace(settings=SimpleNamespace(TORCH_DEVICE=None))
    surya_settings_module = SimpleNamespace(settings=SimpleNamespace(TORCH_DEVICE=None))

    device = _configure_marker_torch_device(
        marker_settings_module,
        surya_settings_module,
    )

    assert device == "mps"
    assert os.environ["TORCH_DEVICE"] == "mps"
    assert marker_settings_module.settings.TORCH_DEVICE == "mps"
    assert surya_settings_module.settings.TORCH_DEVICE == "mps"


def test_marker_pdf_converter_accepts_only_pdf_hints():
    converter = MarkerPdfConverter(marker_converter=FakeMarkerPdfConverter())

    assert converter.accepts(io.BytesIO(b""), StreamInfo(extension=".pdf"))
    assert converter.accepts(io.BytesIO(b""), StreamInfo(mimetype="application/pdf"))
    assert not converter.accepts(io.BytesIO(b""), StreamInfo(extension=".docx"))


def test_marker_pdf_converter_uses_marker_runtime():
    fake_marker = FakeMarkerPdfConverter()
    converter = MarkerPdfConverter(
        marker_converter=fake_marker,
        marker_text_from_rendered=fake_text_from_rendered,
    )

    result = converter.convert(
        io.BytesIO(b"%PDF-1.4 fake"),
        StreamInfo(extension=".pdf"),
    )

    assert result.markdown == "# Marker output"
    assert result.title == "Marker title"
    assert len(fake_marker.seen_paths) == 1
    assert not os.path.exists(fake_marker.seen_paths[0])


def test_marker_pdf_converter_repairs_marker_before_failing_over():
    converter = RepairableMarkerPdfConverter()

    result = converter.convert(
        io.BytesIO(b"%PDF-1.4 fake"),
        StreamInfo(extension=".pdf"),
    )

    assert result.markdown == "repaired marker"
    assert converter.create_count == 2
    assert converter.repair_count == 1


def test_marker_pdf_converter_resolves_image_references():
    fake_marker = FakeMarkerPdfConverter(
        markdown="before\n![](picture.png)\nafter",
    )

    def marker_with_image(source_path):
        rendered = fake_marker(source_path)
        rendered.images = {"picture.png": Image.new("RGB", (1, 1), color="white")}
        return rendered

    converter = MarkerPdfConverter(
        marker_converter=marker_with_image,
        marker_text_from_rendered=fake_text_with_images,
    )

    result = converter.convert(
        io.BytesIO(b"%PDF-1.4 fake"),
        StreamInfo(extension=".pdf"),
    )
    assert "picture.png" not in result.markdown

    result_with_data_uri = converter.convert(
        io.BytesIO(b"%PDF-1.4 fake"),
        StreamInfo(extension=".pdf"),
        keep_data_uris=True,
    )
    assert "data:image/png;base64," in result_with_data_uri.markdown


def test_markitdown_auto_pdf_engine_prefers_marker():
    fake_marker = FakeMarkerPdfConverter(markdown="marker wins")
    markitdown = MarkItDown(
        pdf_engine="auto",
        marker_converter=fake_marker,
        marker_text_from_rendered=fake_text_from_rendered,
    )

    result = markitdown.convert(
        io.BytesIO(b"%PDF-1.4 fake"),
        stream_info=StreamInfo(extension=".pdf", mimetype="application/pdf"),
    )

    assert result.markdown == "marker wins"


def test_markitdown_auto_pdf_engine_falls_back_to_builtin_pdf_converter():
    fake_marker = FakeMarkerPdfConverter(should_raise=True)
    markitdown = MarkItDown(
        pdf_engine="auto",
        marker_converter=fake_marker,
        marker_text_from_rendered=fake_text_from_rendered,
    )

    result = markitdown.convert(
        TEST_FILES_DIR / "test.pdf",
    )

    assert "AutoGen" in result.markdown

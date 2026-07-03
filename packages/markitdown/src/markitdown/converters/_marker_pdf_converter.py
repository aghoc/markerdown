import io
import os
import base64
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from typing import Any, BinaryIO
from warnings import warn

from .._base_converter import DocumentConverter, DocumentConverterResult
from .._exceptions import MissingDependencyException, MISSING_DEPENDENCY_MESSAGE
from .._stream_info import StreamInfo

ACCEPTED_MIME_TYPE_PREFIXES = [
    "application/pdf",
    "application/x-pdf",
]

ACCEPTED_FILE_EXTENSIONS = [".pdf"]


class MarkerPdfConverter(DocumentConverter):
    """
    Converts PDFs to Markdown using marker.

    Marker is especially useful for PDFs with complex layout, tables, OCR needs,
    and math/equations. It is intentionally PDF-only here so Office formats keep
    using MarkItDown's built-in converters.
    """

    def __init__(
        self,
        *,
        marker_config: Mapping[str, Any] | None = None,
        marker_artifact_dict: Any = None,
        marker_converter: Any = None,
        marker_text_from_rendered: Callable[[Any], tuple[str, Any, Any]] | None = None,
        marker_auto_repair: bool = True,
        marker_repair_command: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        self._marker_config = dict(marker_config or {})
        self._marker_artifact_dict = marker_artifact_dict
        self._marker_converter = marker_converter
        self._marker_text_from_rendered = marker_text_from_rendered
        self._marker_converter_injected = marker_converter is not None
        self._marker_auto_repair = marker_auto_repair
        self._marker_repair_command = tuple(marker_repair_command or ())
        self._marker_repair_attempted = False

    def accepts(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,
    ) -> bool:
        mimetype = (stream_info.mimetype or "").lower()
        extension = (stream_info.extension or "").lower()

        if extension in ACCEPTED_FILE_EXTENSIONS:
            return True

        for prefix in ACCEPTED_MIME_TYPE_PREFIXES:
            if mimetype.startswith(prefix):
                return True

        return False

    def convert(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,
    ) -> DocumentConverterResult:
        assert isinstance(file_stream, io.IOBase)

        cur_pos = file_stream.tell()
        try:
            return self._convert_once(file_stream, stream_info, **kwargs)
        except Exception as first_exc:
            if not self._can_attempt_marker_repair():
                raise

            file_stream.seek(cur_pos)
            self._repair_marker_dependency(first_exc)
            self._reset_marker_runtime()
            return self._convert_once(file_stream, stream_info, **kwargs)

    def _convert_once(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,
    ) -> DocumentConverterResult:
        converter, text_from_rendered = self._get_marker_runtime()

        source_path = self._get_source_path(file_stream, stream_info)
        remove_source_path = source_path != stream_info.local_path

        try:
            rendered = converter(source_path)
            markdown = self._markdown_from_rendered(
                rendered,
                text_from_rendered,
                keep_data_uris=kwargs.get("keep_data_uris", False),
            )
            title = self._title_from_rendered(rendered)
            return DocumentConverterResult(markdown=markdown, title=title)
        finally:
            if remove_source_path:
                try:
                    os.unlink(source_path)
                except FileNotFoundError:
                    pass

    def _can_attempt_marker_repair(self) -> bool:
        return (
            self._marker_auto_repair
            and not self._marker_repair_attempted
            and not self._marker_converter_injected
        )

    def _repair_marker_dependency(self, reason: Exception) -> None:
        self._marker_repair_attempted = True
        command = list(self._marker_repair_command or _default_marker_repair_command())

        warn(
            "Marker PDF conversion failed before fallback. Attempting marker install/update with: "
            + " ".join(command),
            RuntimeWarning,
        )

        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            details = (exc.stderr or exc.stdout or "").strip()
            message = (
                "Marker install/update failed. Falling back is allowed only if another "
                "PDF converter is registered."
            )
            if details:
                message = f"{message}\n\n{details}"
            raise RuntimeError(message) from reason

    def _reset_marker_runtime(self) -> None:
        if not self._marker_converter_injected:
            self._marker_converter = None
            self._marker_text_from_rendered = None

    def _get_marker_runtime(
        self,
    ) -> tuple[Any, Callable[[Any], tuple[str, Any, Any]]]:
        if self._marker_converter is not None:
            if self._marker_text_from_rendered is not None:
                return self._marker_converter, self._marker_text_from_rendered
            return self._marker_converter, _default_text_from_rendered

        self._marker_converter, self._marker_text_from_rendered = (
            self._create_marker_runtime()
        )
        return self._marker_converter, self._marker_text_from_rendered

    def _create_marker_runtime(
        self,
    ) -> tuple[Any, Callable[[Any], tuple[str, Any, Any]]]:
        try:
            import marker.settings as marker_settings_module
            import surya.settings as surya_settings_module
            from marker.config.parser import ConfigParser
            from marker.converters.pdf import PdfConverter as MarkerPdfConverterImpl
            from marker.models import create_model_dict
            from marker.output import text_from_rendered
        except ImportError as exc:
            raise MissingDependencyException(
                MISSING_DEPENDENCY_MESSAGE.format(
                    converter=type(self).__name__,
                    extension=".pdf",
                    feature="marker",
                )
            ) from exc

        marker_device = _configure_marker_torch_device(
            marker_settings_module,
            surya_settings_module,
            self._marker_config,
        )
        marker_config = {
            "output_format": "markdown",
            "disable_image_extraction": True,
            "torch_device": marker_device,
            **self._marker_config,
        }
        config_parser = ConfigParser(marker_config)
        artifact_dict = self._marker_artifact_dict or create_model_dict(
            device=marker_device
        )

        return (
            MarkerPdfConverterImpl(
                config=config_parser.generate_config_dict(),
                artifact_dict=artifact_dict,
                processor_list=config_parser.get_processors(),
                renderer=config_parser.get_renderer(),
                llm_service=config_parser.get_llm_service(),
            ),
            text_from_rendered,
        )

    def _get_source_path(self, file_stream: BinaryIO, stream_info: StreamInfo) -> str:
        if stream_info.local_path is not None and os.path.exists(stream_info.local_path):
            return stream_info.local_path

        suffix = stream_info.extension or ".pdf"
        if not suffix.startswith("."):
            suffix = f".{suffix}"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_stream.read())
            return tmp.name

    def _markdown_from_rendered(
        self,
        rendered: Any,
        text_from_rendered: Callable[[Any], tuple[str, Any, Any]],
        *,
        keep_data_uris: bool = False,
    ) -> str:
        images = {}
        try:
            markdown, _, images = text_from_rendered(rendered)
        except Exception:
            markdown = getattr(rendered, "markdown", None)
            images = getattr(rendered, "images", {}) or {}

        if markdown is None:
            markdown = str(rendered)

        if images:
            markdown = _resolve_image_references(markdown, images, keep_data_uris)

        return markdown

    def _title_from_rendered(self, rendered: Any) -> str | None:
        metadata = getattr(rendered, "metadata", None)
        if isinstance(metadata, Mapping):
            title = metadata.get("title")
            if isinstance(title, str) and title.strip():
                return title.strip()
        return None


def _configure_marker_torch_device(
    marker_settings_module: Any,
    surya_settings_module: Any,
    marker_config: Mapping[str, Any] | None = None,
) -> str:
    device = _select_marker_torch_device(marker_config)
    os.environ["TORCH_DEVICE"] = device
    os.environ["MARKERDOWN_TORCH_DEVICE"] = device

    for settings_module in (marker_settings_module, surya_settings_module):
        settings = getattr(settings_module, "settings", None)
        if settings is not None and hasattr(settings, "TORCH_DEVICE"):
            settings.TORCH_DEVICE = device

    return device


def _select_marker_torch_device(marker_config: Mapping[str, Any] | None = None) -> str:
    if marker_config is not None:
        configured_device = (
            marker_config.get("torch_device") or marker_config.get("TORCH_DEVICE") or ""
        )
        if isinstance(configured_device, str) and configured_device.strip():
            return configured_device.strip()

    configured_device = (
        os.getenv("MARKERDOWN_TORCH_DEVICE") or os.getenv("TORCH_DEVICE") or ""
    ).strip()
    if configured_device:
        return configured_device

    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass

    return "cpu"


def _default_text_from_rendered(rendered: Any) -> tuple[str, Any, Any]:
    markdown = getattr(rendered, "markdown", None)
    if markdown is None:
        markdown = str(rendered)
    return markdown, None, getattr(rendered, "images", None)


def _resolve_image_references(markdown: str, images: Mapping[str, Any], keep_data_uris: bool) -> str:
    def replace_image(match: re.Match[str]) -> str:
        alt_text = match.group(1)
        image_path = match.group(2)

        if image_path not in images:
            return match.group(0)

        if keep_data_uris:
            data_uri = _image_to_data_uri(images[image_path], image_path)
            return f"![{alt_text}]({data_uri})"

        return ""

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replace_image, markdown)


def _image_to_data_uri(image: Any, image_path: str) -> str:
    image_format = "JPEG"
    mimetype = "image/jpeg"
    lower_path = image_path.lower()
    if lower_path.endswith(".png"):
        image_format = "PNG"
        mimetype = "image/png"

    if image_format == "JPEG" and getattr(image, "mode", "RGB") != "RGB":
        image = image.convert("RGB")

    buffer = io.BytesIO()
    image.save(buffer, image_format)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:{mimetype};base64,{encoded}"


def _default_marker_repair_command() -> list[str]:
    return [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "marker-pdf",
        "pdfplumber>=0.11.8,<0.11.9",
        "pdfminer.six>=20251107",
    ]

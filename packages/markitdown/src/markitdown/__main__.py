# SPDX-FileCopyrightText: 2024-present Adam Fourney <adamfo@microsoft.com>
#
# SPDX-License-Identifier: MIT
import argparse
import sys
import codecs
import json
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple
from textwrap import dedent
from importlib.metadata import entry_points
from .__about__ import __version__
from ._markitdown import MarkItDown, StreamInfo, DocumentConverterResult


def main():
    parser = argparse.ArgumentParser(
        description="Convert various file formats to markdown.",
        prog="markerdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage=dedent(
            """
            SYNTAX:

                markerdown <OPTIONAL: FILENAME>
                If FILENAME is empty and stdin is piped, markerdown reads from stdin.
                If FILENAME is empty in a terminal, markerdown lets you choose
                files or folders from ./input and writes Markdown to ./output.

            EXAMPLE:

                markerdown example.pdf

                OR

                cat example.pdf | markerdown

                OR

                markerdown < example.pdf

                OR to save to a file use

                markerdown example.pdf -o example.md

                OR

                markerdown example.pdf > example.md

                OR choose from the local input folder

                markerdown
            """
        ).strip(),
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="show the version number and exit",
    )

    parser.add_argument(
        "-o",
        "--output",
        help="Output file name. If not provided, output is written to stdout.",
    )

    parser.add_argument(
        "--input-dir",
        default="input",
        help="Input folder used by the interactive picker when no filename is provided. Defaults to ./input.",
    )

    parser.add_argument(
        "--output-dir",
        default="output",
        help="Output folder used by the interactive picker when no filename is provided. Defaults to ./output.",
    )

    parser.add_argument(
        "-x",
        "--extension",
        help="Provide a hint about the file extension (e.g., when reading from stdin).",
    )

    parser.add_argument(
        "-m",
        "--mime-type",
        help="Provide a hint about the file's MIME type.",
    )

    parser.add_argument(
        "-c",
        "--charset",
        help="Provide a hint about the file's charset (e.g, UTF-8).",
    )

    parser.add_argument(
        "--pdf-engine",
        choices=["auto", "marker", "builtin"],
        help=(
            "PDF conversion engine. 'auto' uses marker first, tries marker "
            "install/update if needed, then falls back to MarkItDown's built-in "
            "PDF converter. Defaults to MARKITDOWN_PDF_ENGINE or 'auto'."
        ),
    )

    parser.add_argument(
        "--no-marker-auto-repair",
        action="store_true",
        help="Disable automatic marker install/update before PDF fallback.",
    )

    cloud_group = parser.add_mutually_exclusive_group()
    cloud_group.add_argument(
        "-d",
        "--use-docintel",
        action="store_true",
        help="Use Document Intelligence to extract text instead of offline conversion. Requires a valid Document Intelligence Endpoint.",
    )

    cloud_group.add_argument(
        "--use-cu",
        "--use-content-understanding",
        action="store_true",
        dest="use_cu",
        help="Use Azure Content Understanding to extract text. Requires --cu-endpoint.",
    )

    parser.add_argument(
        "-e",
        "--endpoint",
        type=str,
        help="Document Intelligence Endpoint. Required if using Document Intelligence.",
    )

    parser.add_argument(
        "--cu-endpoint",
        type=str,
        help="Content Understanding Endpoint. Required if using --use-cu.",
    )

    parser.add_argument(
        "--cu-analyzer",
        type=str,
        help="Content Understanding analyzer ID. If not specified, auto-selects by file type.",
    )

    parser.add_argument(
        "--cu-file-types",
        type=str,
        help="Comma-separated list of file types to route to Content Understanding (e.g., pdf,jpeg,mp4). If omitted, all supported types are routed.",
    )

    parser.add_argument(
        "-p",
        "--use-plugins",
        action="store_true",
        help="Use 3rd-party plugins to convert files. Use --list-plugins to see installed plugins.",
    )

    parser.add_argument(
        "--list-plugins",
        action="store_true",
        help="List installed 3rd-party plugins. Plugins are loaded when using the -p or --use-plugin option.",
    )

    parser.add_argument(
        "--keep-data-uris",
        action="store_true",
        help="Keep data URIs (like base64-encoded images) in the output. By default, data URIs are truncated.",
    )

    parser.add_argument(
        "--marker-config-json",
        help='JSON object with marker configuration, e.g. \'{"force_ocr": true}\'.',
    )

    parser.add_argument(
        "--marker-force-ocr",
        action="store_true",
        help="Force marker OCR for PDFs. Useful for scanned PDFs and inline math.",
    )

    parser.add_argument(
        "--marker-strip-existing-ocr",
        action="store_true",
        help="Ask marker to strip existing OCR text and re-OCR the PDF.",
    )

    parser.add_argument(
        "--marker-use-llm",
        action="store_true",
        help="Enable marker's LLM-assisted PDF mode. Requires marker LLM service configuration.",
    )

    parser.add_argument(
        "--marker-redo-inline-math",
        action="store_true",
        help="Ask marker to redo inline math conversion. Most useful with --marker-use-llm.",
    )

    parser.add_argument(
        "--marker-disable-image-extraction",
        action="store_true",
        help="Disable marker image extraction while converting PDFs.",
    )

    parser.add_argument("filename", nargs="?")
    args = parser.parse_args()
    interactive_input = args.filename is None and _stdin_is_interactive()

    # Parse the extension hint
    extension_hint = args.extension
    if extension_hint is not None:
        extension_hint = extension_hint.strip().lower()
        if len(extension_hint) > 0:
            if not extension_hint.startswith("."):
                extension_hint = "." + extension_hint
        else:
            extension_hint = None

    # Parse the mime type
    mime_type_hint = args.mime_type
    if mime_type_hint is not None:
        mime_type_hint = mime_type_hint.strip()
        if len(mime_type_hint) > 0:
            if mime_type_hint.count("/") != 1:
                _exit_with_error(f"Invalid MIME type: {mime_type_hint}")
        else:
            mime_type_hint = None

    # Parse the charset
    charset_hint = args.charset
    if charset_hint is not None:
        charset_hint = charset_hint.strip()
        if len(charset_hint) > 0:
            try:
                charset_hint = codecs.lookup(charset_hint).name
            except LookupError:
                _exit_with_error(f"Invalid charset: {charset_hint}")
        else:
            charset_hint = None

    stream_info = None
    if (
        extension_hint is not None
        or mime_type_hint is not None
        or charset_hint is not None
    ):
        stream_info = StreamInfo(
            extension=extension_hint, mimetype=mime_type_hint, charset=charset_hint
        )

    marker_config: Dict[str, Any] = {}
    if args.marker_config_json is not None:
        try:
            parsed_marker_config = json.loads(args.marker_config_json)
        except json.JSONDecodeError as exc:
            _exit_with_error(f"Invalid --marker-config-json: {exc}")
        if not isinstance(parsed_marker_config, dict):
            _exit_with_error("--marker-config-json must be a JSON object.")
        marker_config.update(parsed_marker_config)

    marker_bool_options = {
        "force_ocr": args.marker_force_ocr,
        "strip_existing_ocr": args.marker_strip_existing_ocr,
        "use_llm": args.marker_use_llm,
        "redo_inline_math": args.marker_redo_inline_math,
        "disable_image_extraction": args.marker_disable_image_extraction,
    }
    marker_config.update(
        {key: value for key, value in marker_bool_options.items() if value}
    )

    markitdown_kwargs: Dict[str, Any] = {}
    if args.pdf_engine is not None:
        markitdown_kwargs["pdf_engine"] = args.pdf_engine
    if args.no_marker_auto_repair:
        markitdown_kwargs["marker_auto_repair"] = False
    if marker_config:
        markitdown_kwargs["marker_config"] = marker_config

    if args.list_plugins:
        # List installed plugins, then exit
        print("Installed MarkItDown 3rd-party Plugins:\n")
        plugin_entry_points = list(entry_points(group="markitdown.plugin"))
        if len(plugin_entry_points) == 0:
            print("  * No 3rd-party plugins installed.")
            print(
                "\nFind plugins by searching for the hashtag #markitdown-plugin on GitHub.\n"
            )
        else:
            for entry_point in plugin_entry_points:
                print(f"  * {entry_point.name:<16}\t(package: {entry_point.value})")
            print(
                "\nUse the -p (or --use-plugins) option to enable 3rd-party plugins.\n"
            )
        sys.exit(0)

    if args.use_docintel:
        if args.endpoint is None:
            _exit_with_error(
                "Document Intelligence Endpoint is required when using Document Intelligence."
            )
        elif args.filename is None and not interactive_input:
            _exit_with_error("Filename is required when using Document Intelligence.")

        markitdown = MarkItDown(
            enable_plugins=args.use_plugins,
            docintel_endpoint=args.endpoint,
            **markitdown_kwargs,
        )
    elif args.use_cu:
        if args.cu_endpoint is None:
            _exit_with_error(
                "Content Understanding Endpoint (--cu-endpoint) is required when using --use-cu."
            )
        elif args.filename is None and not interactive_input:
            _exit_with_error("Filename is required when using Content Understanding.")

        cu_kwargs: Dict[str, Any] = {
            "cu_endpoint": args.cu_endpoint,
        }
        if args.cu_analyzer is not None:
            cu_kwargs["cu_analyzer_id"] = args.cu_analyzer
        if args.cu_file_types is not None:
            # Parse comma-separated file types into ContentUnderstandingFileType list
            from .converters import ContentUnderstandingFileType

            type_names = [
                t.strip().lower() for t in args.cu_file_types.split(",") if t.strip()
            ]
            cu_types = []
            for name in type_names:
                # Try matching by value (e.g., "pdf", "jpeg", "mp4")
                try:
                    cu_types.append(ContentUnderstandingFileType(name))
                except ValueError:
                    _exit_with_error(f"Unknown file type: {name}")
            cu_kwargs["cu_file_types"] = cu_types

        markitdown = MarkItDown(
            enable_plugins=args.use_plugins, **markitdown_kwargs, **cu_kwargs
        )
    else:
        markitdown = MarkItDown(enable_plugins=args.use_plugins, **markitdown_kwargs)

    if args.filename is None:
        if interactive_input:
            _handle_interactive_input(args, markitdown, stream_info)
            return
        else:
            result = markitdown.convert_stream(
                sys.stdin.buffer,
                stream_info=stream_info,
                keep_data_uris=args.keep_data_uris,
            )
    else:
        result = markitdown.convert(
            args.filename, stream_info=stream_info, keep_data_uris=args.keep_data_uris
        )

    _handle_output(args, result)


def _handle_output(args, result: DocumentConverterResult):
    """Handle output to stdout or file"""
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result.markdown)
    else:
        # Handle stdout encoding errors more gracefully
        print(
            result.markdown.encode(sys.stdout.encoding, errors="replace").decode(
                sys.stdout.encoding
            )
        )


def _stdin_is_interactive() -> bool:
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


def _handle_interactive_input(args, markitdown: MarkItDown, stream_info) -> None:
    input_dir = _resolve_user_path(args.input_dir)
    output_dir = _resolve_user_path(args.output_dir)

    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates = _discover_input_candidates(input_dir)
    if not candidates:
        _exit_with_error(
            f"No files or folders found in input folder: {input_dir}\n"
            "Put files or folders there, then run markitdown again."
        )

    selected_paths = _prompt_for_input_paths(candidates, input_dir, output_dir)
    if not selected_paths:
        print("Cancelled.")
        return

    jobs = _build_conversion_jobs(selected_paths, input_dir, output_dir)
    if not jobs:
        _exit_with_error("No files found in the selected input.")

    successes: List[Tuple[Path, Path]] = []
    failures: List[Tuple[Path, Exception]] = []

    for source_path, output_path in jobs:
        print(f"Converting {source_path.relative_to(input_dir)} -> {output_path}")
        try:
            result = markitdown.convert(
                str(source_path),
                stream_info=stream_info,
                keep_data_uris=args.keep_data_uris,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result.markdown, encoding="utf-8")
            successes.append((source_path, output_path))
        except Exception as exc:
            failures.append((source_path, exc))
            print(f"Failed: {source_path} ({exc})", file=sys.stderr)

    print()
    print(f"Done: {len(successes)} converted, {len(failures)} failed.")
    if successes:
        print(f"Output folder: {output_dir}")
    if failures:
        sys.exit(1)


def _resolve_user_path(path_value: str) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def _discover_input_candidates(input_dir: Path) -> List[Path]:
    candidates: List[Path] = []
    if not input_dir.exists():
        return candidates

    for path in input_dir.iterdir():
        if path.name.startswith("."):
            continue
        if path.is_file() or path.is_dir():
            candidates.append(path)

    return sorted(candidates, key=lambda path: (not path.is_dir(), path.name.lower()))


def _prompt_for_input_paths(
    candidates: Sequence[Path], input_dir: Path, output_dir: Path
) -> List[Path]:
    print(f"Input folder:  {input_dir}")
    print(f"Output folder: {output_dir}")
    print()
    print("Select a file or folder to convert:")

    for index, candidate in enumerate(candidates, start=1):
        rel_path = candidate.relative_to(input_dir)
        if candidate.is_dir():
            file_count = len(list(_iter_files(candidate)))
            print(f"  {index}. {rel_path}/ ({file_count} files)")
        else:
            print(f"  {index}. {rel_path}")

    if len(candidates) > 1:
        print("  a. all")
    print("  q. quit")
    print()

    default_choice = "1" if len(candidates) == 1 else None
    while True:
        prompt = "Choice"
        if default_choice is not None:
            prompt += f" [{default_choice}]"
        prompt += ": "
        choice = input(prompt).strip().lower()
        if choice == "" and default_choice is not None:
            choice = default_choice

        if choice in {"q", "quit", "exit"}:
            return []
        if choice in {"a", "all"} and len(candidates) > 1:
            return list(candidates)
        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(candidates):
                return [candidates[index - 1]]

        print("Please enter a listed number, 'a', or 'q'.")


def _build_conversion_jobs(
    selected_paths: Sequence[Path], input_dir: Path, output_dir: Path
) -> List[Tuple[Path, Path]]:
    sources: List[Path] = []
    for selected_path in selected_paths:
        if selected_path.is_file():
            sources.append(selected_path)
        elif selected_path.is_dir():
            sources.extend(_iter_files(selected_path))

    used_outputs: set[Path] = set()
    jobs: List[Tuple[Path, Path]] = []
    for source_path in sources:
        output_path = _default_output_path(source_path, input_dir, output_dir)
        output_path = _dedupe_output_path(output_path, source_path, used_outputs)
        used_outputs.add(output_path)
        jobs.append((source_path, output_path))

    return jobs


def _iter_files(path: Path) -> List[Path]:
    files: List[Path] = []
    for child in path.rglob("*"):
        if child.name.startswith("."):
            continue
        if any(part.startswith(".") for part in child.relative_to(path).parts):
            continue
        if child.is_file():
            files.append(child)
    return sorted(files, key=lambda child: str(child).lower())


def _default_output_path(source_path: Path, input_dir: Path, output_dir: Path) -> Path:
    relative_path = source_path.relative_to(input_dir)
    return output_dir / relative_path.with_suffix(".md")


def _dedupe_output_path(
    output_path: Path, source_path: Path, used_outputs: set[Path]
) -> Path:
    if output_path not in used_outputs:
        return output_path

    source_suffix = source_path.suffix.lstrip(".")
    suffix_label = f".{source_suffix}" if source_suffix else ".file"
    candidate = output_path.with_name(f"{output_path.stem}{suffix_label}.md")
    if candidate not in used_outputs:
        return candidate

    counter = 2
    while True:
        candidate = output_path.with_name(
            f"{output_path.stem}{suffix_label}.{counter}.md"
        )
        if candidate not in used_outputs:
            return candidate
        counter += 1


def _exit_with_error(message: str):
    print(message)
    sys.exit(1)


if __name__ == "__main__":
    main()

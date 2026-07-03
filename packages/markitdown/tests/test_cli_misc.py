#!/usr/bin/env python3 -m pytest
import subprocess
import sys
from markitdown import __version__

# This file contains CLI tests that are not directly tested by the FileTestVectors.
# This includes things like help messages, version numbers, and invalid flags.


def test_version() -> None:
    result = subprocess.run(
        ["python", "-m", "markitdown", "--version"], capture_output=True, text=True
    )

    assert result.returncode == 0, f"CLI exited with error: {result.stderr}"
    assert __version__ in result.stdout, f"Version not found in output: {result.stdout}"


def test_invalid_flag() -> None:
    result = subprocess.run(
        ["python", "-m", "markitdown", "--foobar"], capture_output=True, text=True
    )

    assert result.returncode != 0, f"CLI exited with error: {result.stderr}"
    assert (
        "unrecognized arguments" in result.stderr
    ), "Expected 'unrecognized arguments' to appear in STDERR"
    assert "SYNTAX" in result.stderr, "Expected 'SYNTAX' to appear in STDERR"


def test_interactive_input_picker_writes_output(tmp_path, monkeypatch) -> None:
    import markitdown.__main__ as markitdown_cli

    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    (input_dir / "note.txt").write_text("hello from input", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "markitdown",
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
        ],
    )
    monkeypatch.setattr(markitdown_cli, "_stdin_is_interactive", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "1")

    markitdown_cli.main()

    output_file = output_dir / "note.md"
    assert output_file.exists()
    assert "hello from input" in output_file.read_text(encoding="utf-8")


def test_interactive_folder_jobs_preserve_structure(tmp_path) -> None:
    import markitdown.__main__ as markitdown_cli

    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    nested_dir = input_dir / "reports" / "nested"
    nested_dir.mkdir(parents=True)
    first_file = input_dir / "reports" / "first.pdf"
    second_file = nested_dir / "second.docx"
    first_file.write_bytes(b"fake pdf")
    second_file.write_bytes(b"fake docx")

    jobs = markitdown_cli._build_conversion_jobs(
        [input_dir / "reports"], input_dir, output_dir
    )

    assert jobs == [
        (first_file, output_dir / "reports" / "first.md"),
        (second_file, output_dir / "reports" / "nested" / "second.md"),
    ]


if __name__ == "__main__":
    """Runs this file's tests from the command line."""
    test_version()
    test_invalid_flag()
    print("All tests passed!")

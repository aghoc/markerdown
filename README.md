# MarkerDown

MarkerDown is a document-to-Markdown converter that combines
[Microsoft MarkItDown](https://github.com/microsoft/markitdown) with
[Datalab Marker](https://github.com/datalab-to/marker).

It keeps MarkItDown's broad file format support for Office documents, HTML,
text files, archives, audio, images, and other common inputs, while using Marker
as the default PDF engine for better handling of complex layouts, OCR, tables,
math, and equations.

## Features

- Converts common document formats to Markdown
- Uses Marker first for PDF conversion
- Keeps MarkItDown's built-in converters for Word, Excel, and PowerPoint
- Falls back to MarkItDown's built-in PDF converter if Marker still cannot run
- Tries to install or update Marker before falling back
- Uses GPU acceleration by default when CUDA or Apple Silicon MPS is available
- Provides a simple `input/` to `output/` local workflow
- Supports recursive folder conversion
- Keeps the MarkItDown Python API compatible

## Supported Inputs

MarkerDown inherits MarkItDown's broad input support, including:

- PDF
- Word: `.docx`
- Excel: `.xlsx`, `.xls`
- PowerPoint: `.pptx`
- Images
- Audio
- HTML
- CSV, JSON, XML, and plain text
- ZIP archives
- EPUB
- URLs supported by MarkItDown

## Installation

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install MarkerDown from the repository root:

```bash
pip install -e 'packages/markitdown[all,marker]'
```

## Local Input/Output Workflow

MarkerDown includes two root-level folders for everyday conversion:

```text
input/
output/
```

Put files or folders into `input/`, then run:

```bash
markerdown
```

MarkerDown will show a picker for the files and folders in `input/`.

If you choose a file, one Markdown file is written to `output/`:

```text
input/report.pdf
output/report.md
```

If you choose a folder, every file under that folder is converted recursively and
the folder structure is preserved:

```text
input/project/report.pdf
input/project/slides.pptx
input/project/tables/results.xlsx

output/project/report.md
output/project/slides.md
output/project/tables/results.md
```

If multiple entries exist in `input/`, choose `a` to convert all of them.

## CLI Usage

Convert a single file:

```bash
markerdown document.pdf -o document.md
```

Write Markdown to stdout:

```bash
markerdown document.pdf
```

Pipe input:

```bash
cat document.txt | markerdown --extension txt
```

The original MarkItDown command name is also available for compatibility:

```bash
markitdown document.pdf -o document.md
```

## PDF Conversion

The default PDF engine is `auto`.

```bash
markerdown document.pdf -o document.md
```

In `auto` mode:

1. MarkerDown tries Marker first.
2. If Marker cannot be imported or fails at runtime, MarkerDown tries to install
   or update Marker-related dependencies.
3. MarkerDown retries Marker once.
4. If Marker still fails, MarkerDown falls back to MarkItDown's built-in PDF
   converter.

Force Marker:

```bash
markerdown document.pdf --pdf-engine marker -o document.md
```

Use the original MarkItDown PDF converter:

```bash
markerdown document.pdf --pdf-engine builtin -o document.md
```

Disable automatic Marker repair:

```bash
markerdown document.pdf --no-marker-auto-repair -o document.md
```

## GPU Behavior

MarkerDown configures Marker to prefer GPU acceleration by default:

1. CUDA, when available
2. Apple Silicon MPS, when available
3. CPU fallback

On Apple Silicon, some Marker/Surya model components may still fall back to CPU
if the underlying model does not support MPS. In that case MarkerDown still uses
GPU-capable components where supported and lets Marker/Surya handle unsupported
operations safely.

## Marker Options

Force OCR:

```bash
markerdown scanned.pdf --marker-force-ocr -o scanned.md
```

Strip existing OCR text and re-OCR:

```bash
markerdown scanned.pdf --marker-strip-existing-ocr -o scanned.md
```

Enable Marker LLM mode:

```bash
markerdown complex.pdf --marker-use-llm -o complex.md
```

Redo inline math conversion:

```bash
markerdown paper.pdf --marker-redo-inline-math -o paper.md
```

Pass raw Marker config as JSON:

```bash
markerdown paper.pdf --marker-config-json '{"force_ocr": true}' -o paper.md
```

## Python API

The Python import namespace remains compatible with MarkItDown:

```python
from markitdown import MarkItDown

md = MarkItDown()
result = md.convert("document.pdf")
print(result.markdown)
```

Select a PDF engine explicitly:

```python
from markitdown import MarkItDown

md = MarkItDown(pdf_engine="marker")
result = md.convert("document.pdf")
```

Disable automatic Marker repair:

```python
from markitdown import MarkItDown

md = MarkItDown(marker_auto_repair=False)
result = md.convert("document.pdf")
```

## Project Layout

```text
input/                         Local files and folders to convert
output/                        Local Markdown results
packages/markitdown/           Main converter package
packages/markitdown/src/       Python source
packages/markitdown/tests/     Tests
INPUT_OUTPUT_USAGE.md          Short local usage guide
```

## Attribution

MarkerDown combines two open-source projects:

- [Microsoft MarkItDown](https://github.com/microsoft/markitdown), which
  provides the base converter framework, CLI, Python API, and broad file format
  support.
- [Datalab Marker](https://github.com/datalab-to/marker), which provides the
  PDF engine used for layout-aware PDF parsing, OCR, tables, and math.

## License Notice

MarkerDown combines MIT-licensed MarkItDown code with Marker integration.
Marker's code is licensed under GPL-3.0, and its model weights have separate
model license terms. Because MarkerDown imports and uses Marker for the default
PDF engine, redistribution or commercial use of MarkerDown with Marker enabled
should be reviewed under GPL-3.0 and Marker's own licensing terms.

The original MarkItDown MIT license notice is retained in this repository for
the upstream MarkItDown code. Marker is an external dependency installed through
`marker-pdf`; see the Marker repository for its current code, model, and
commercial licensing information:

- [Marker repository](https://github.com/datalab-to/marker)
- [Marker GPL-3.0 license](https://github.com/datalab-to/marker/blob/master/LICENSE)
- [Marker model license](https://github.com/datalab-to/marker/blob/master/MODEL_LICENSE)

## Security Notes

MarkerDown reads local files and can fetch URLs when URL conversion is used. It
runs with the privileges of the current process. Only convert files and URLs you
trust, especially in automated or hosted environments.

The `input/` and `output/` folders are intended for local use. Their contents are
ignored by Git by default so private documents are not accidentally committed.

This README is not legal advice. If you plan to redistribute MarkerDown or use
it commercially, review the upstream licenses directly and consult counsel when
needed.

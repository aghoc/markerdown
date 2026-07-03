# MarkerDown

MarkerDown is a tuned document-to-Markdown converter that combines
[Microsoft MarkItDown](https://github.com/microsoft/markitdown) with
[Datalab Marker](https://github.com/datalab-to/marker).

It keeps MarkItDown's broad file format support and Python API while using
Marker as the default PDF engine for better handling of complex PDF layout,
OCR, tables, math, and equations.

MarkerDown prefers GPU acceleration for Marker PDF conversion when CUDA or Apple
Silicon MPS is available, with CPU fallback when no supported GPU backend exists.

## Installation

From source:

```bash
pip install -e 'packages/markitdown[all,marker]'
```

## CLI

Use the MarkerDown command:

```bash
markerdown document.pdf -o document.md
```

The original command is kept for compatibility:

```bash
markitdown document.pdf -o document.md
```

When run without a filename in a terminal, MarkerDown lets you choose files or
folders from the repository root `input/` folder and writes Markdown files to
`output/`.

```bash
markerdown
```

## PDF Strategy

PDF conversion defaults to `auto` mode:

1. Try Marker first.
2. If Marker cannot run, try to install or update Marker dependencies.
3. Retry Marker.
4. Fall back to MarkItDown's built-in PDF converter if Marker still fails.

Word, Excel, and PowerPoint continue to use MarkItDown's built-in Office
converters.

## Python API

The import namespace remains compatible with MarkItDown:

```python
from markitdown import MarkItDown

md = MarkItDown()
result = md.convert("document.pdf")
print(result.markdown)
```

## More Information

See the repository README:

```text
https://github.com/aghoc/markerdown
```

## Attribution

MarkerDown is based on MarkItDown and integrates Marker as the preferred PDF
engine.

Marker's code is GPL-3.0 licensed, and its model weights have separate model
license terms. Because MarkerDown imports and uses Marker for the default PDF
engine, redistribution or commercial use of MarkerDown with Marker enabled
should be reviewed under GPL-3.0 and Marker's own licensing terms.

Review the upstream projects and their licenses before redistribution or
commercial use:

- https://github.com/microsoft/markitdown
- https://github.com/datalab-to/marker

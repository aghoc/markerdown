# Local Input/Output Workflow

MarkerDown provides simple root-level folders for local conversion:

```text
input/
output/
```

## How to Use

1. Put files or folders in `input/`.
2. Run MarkerDown from the repository root.
3. Choose the file or folder to convert.
4. Read the generated Markdown files in `output/`.

```bash
.venv/bin/markerdown
```

The compatibility command also works:

```bash
.venv/bin/markitdown
```

## File Input

```text
input/report.pdf
output/report.md
```

## Folder Input

```text
input/project/report.pdf
input/project/slides.pptx
input/project/tables/results.xlsx

output/project/report.md
output/project/slides.md
output/project/tables/results.md
```

## Notes

- PDF files use Marker first by default.
- If Marker cannot run, MarkerDown tries to install or update Marker before
  falling back to MarkItDown's built-in PDF converter.
- Word, Excel, and PowerPoint continue to use MarkItDown's built-in converters.
- Files placed in `input/` and generated in `output/` are ignored by Git by
  default so private documents are not accidentally uploaded.

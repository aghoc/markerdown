import os


# Keep the existing PDF fixtures pinned to the built-in converter unless a test
# explicitly asks for marker. This keeps the core suite deterministic on
# developer machines that have the optional marker dependency installed.
os.environ.setdefault("MARKITDOWN_PDF_ENGINE", "builtin")

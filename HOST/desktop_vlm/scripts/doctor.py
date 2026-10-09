"""Read-only capability inventory. Does not load a model or prove inference."""
from desktop_vlm.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["doctor"]))

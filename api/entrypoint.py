"""Entry script for the packaged binary (PyInstaller needs a script, not `python -m app`)."""

from app.__main__ import main

if __name__ == "__main__":
    main()

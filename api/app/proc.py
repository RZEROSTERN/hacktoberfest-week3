"""Settings for running other programs from the api."""

import subprocess
import sys

# On Windows the api runs without a console (the desktop app hides it), so a console program it
# starts (whisper-cli, ffmpeg) would otherwise open its own visible window. Zero means "no flags"
# everywhere else.
if sys.platform == "win32":
    NO_WINDOW: int = subprocess.CREATE_NO_WINDOW
else:
    NO_WINDOW = 0

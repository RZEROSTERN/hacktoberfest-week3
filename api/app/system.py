import shutil
from pathlib import Path

import psutil


def total_ram_bytes() -> int:
    """Installed memory. `psutil` because `os.sysconf` does not exist on Windows."""
    return int(psutil.virtual_memory().total)


def free_disk_bytes(path: Path) -> int:
    """Free space on the volume that holds `path` (or the nearest folder that exists)."""
    target = path
    while not target.exists() and target != target.parent:
        target = target.parent
    return shutil.disk_usage(target).free

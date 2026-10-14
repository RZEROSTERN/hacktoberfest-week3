import os
import shutil
from pathlib import Path


def total_ram_bytes() -> int:
    return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))


def free_disk_bytes(path: Path) -> int:
    """Free space on the volume that holds `path` (or the nearest folder that exists)."""
    target = path
    while not target.exists() and target != target.parent:
        target = target.parent
    return shutil.disk_usage(target).free

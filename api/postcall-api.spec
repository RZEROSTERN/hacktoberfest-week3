# PyInstaller recipe for the packaged api: one executable that unpacks itself on start.
# Build with `make build-api`. Data files sit next to the `app` package, where the code looks for
# them (prompts/ and data/), both in development and inside the binary.
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hidden = (
    collect_submodules("uvicorn")  # picked at run time by name (loops, protocols, lifespan)
    + collect_submodules("sqlalchemy.dialects.sqlite")
    + ["multipart", "python_multipart"]
)
datas = [("prompts", "prompts"), ("data", "data")] + collect_data_files("reportlab")

a = Analysis(
    ["entrypoint.py"],
    pathex=["."],
    datas=datas,
    hiddenimports=hidden,
    excludes=["tkinter", "pytest", "mypy", "ruff"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="postcall-api",
    console=True,
    upx=False,
)

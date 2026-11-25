"""The set-up script for another machine (laptop.py): the pieces that differ by system, and that it needs nothing
but Python's own library."""

import ast
import re
import sys
from pathlib import Path

import laptop
from experiments import stage8b


def test_the_environments_python_is_where_each_system_keeps_it():
    root = Path("somewhere")
    assert laptop.venv_python(root, windows=True) == root / ".venv" / "Scripts" / "python.exe"
    assert laptop.venv_python(root, windows=False) == root / ".venv" / "bin" / "python"
    assert laptop.venv_python().parent.parent == laptop.ROOT / ".venv"


def test_an_old_python_is_told_what_to_do_and_a_new_one_passes():
    assert laptop.too_old((3, 11, 0)) is None and laptop.too_old((3, 13, 1)) is None and laptop.too_old() is None
    message = laptop.too_old((3, 9, 7))
    assert message.startswith("!!") and "3.11" in message and "3.9" in message and len(message.splitlines()) >= 2


def test_the_machines_cores_name_and_gpu():
    assert 1 <= laptop.physical_cores() <= 4096
    assert laptop.tidy("My Laptop.local!") == "My-Laptop-local" and laptop.tidy("///") == "laptop"
    assert re.fullmatch(r"[A-Za-z0-9_-]+", laptop.tidy("laptop"))
    gpu = laptop.nvidia_gpu()
    assert gpu is None or isinstance(gpu, str)


def test_pip_is_used_where_the_environment_has_it(monkeypatch):
    """pip reads the system's certificates and uv, left alone, does not: on a network that re-signs HTTPS only pip works."""
    calls = []
    monkeypatch.setattr(laptop, "run", lambda cmd, check=True: calls.append(("pip", [str(c) for c in cmd])) or True)
    monkeypatch.setattr(laptop, "_uv", lambda args, check=True: calls.append(("uv", [str(a) for a in args])) or True)
    monkeypatch.setattr(laptop, "has_pip", lambda py: True)
    assert laptop.install(Path("py"), "dev,fast") and calls[-1] == ("pip", ["py", "-m", "pip", "install", "-e", ".[dev,fast]"])
    monkeypatch.setattr(laptop, "has_pip", lambda py: False)
    monkeypatch.setattr(laptop.shutil, "which", lambda name: "/somewhere/uv" if name == "uv" else None)
    assert laptop.install(Path("py"), "dev,gpu") and calls[-1] == ("uv", ["pip", "install", "--python", "py", "-e", ".[dev,gpu]"])
    assert laptop.has_pip(Path(sys.executable)) in (True, False)


def test_it_imports_nothing_outside_pythons_own_library():
    tree = ast.parse(Path(laptop.__file__).read_text(encoding="utf-8"))
    names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert names <= set(sys.stdlib_module_names), names - set(sys.stdlib_module_names)


def test_staying_awake_is_only_asked_of_windows():
    if sys.platform != "win32":
        assert stage8b.stay_awake() is False

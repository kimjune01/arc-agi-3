"""The modularity discipline, machine-checked from the manifest.

Rules derived from arcg/manifest.py:
- A layer module may import any LOWER layer (triangular reach) but never a higher
  one (no upward peeking).
- Only Layer 0 may import the ArcClient (`..client`).

If someone adds a layer or an upward import, this test fails — the seam can't rot.
"""

import ast
import pathlib

from arc_agi_3.arcg.manifest import LAYERS, layer_index

ARCG = pathlib.Path(__file__).resolve().parents[1] / "src" / "arc_agi_3" / "arcg"


def _imports(path: pathlib.Path) -> list[str]:
    """Return imported names referencing sibling arcg modules or the client."""
    tree = ast.parse(path.read_text())
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod in ("client",) or mod.endswith(".client"):
                names.append("client")
            # `from . import layer1_intent` -> module is None/'.', names in node.names
            for alias in node.names:
                if alias.name in LAYERS:
                    names.append(alias.name)
            if mod in LAYERS:
                names.append(mod)
    return names


def test_no_upward_imports():
    for module in LAYERS:
        path = ARCG / f"{module}.py"
        idx = layer_index(module)
        for imported in _imports(path):
            if imported == "client":
                continue
            other = layer_index(imported)
            assert other is not None and other < idx, (
                f"{module} (layer {idx}) imports {imported} (layer {other}) — "
                f"upward/illegal import")


def test_only_layer0_imports_client():
    for module in LAYERS:
        path = ARCG / f"{module}.py"
        has_client = "client" in _imports(path)
        if layer_index(module) == 0:
            continue
        assert not has_client, f"{module} imports the ArcClient; only Layer 0 may"


def test_manifest_modules_exist():
    for module in LAYERS:
        assert (ARCG / f"{module}.py").exists(), f"manifest lists missing {module}"

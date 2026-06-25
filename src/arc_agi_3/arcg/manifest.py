"""The layer stack as data. The CLI command table and the import-boundary test
both derive from this list, so adding a layer is a one-line append here.

Order is low -> high. Index = layer number. A module may import any module
earlier in this list (triangular reach) but none later (no upward peeking).
"""

LAYERS = [
    "layer0_protocol",
    "layer1_intent",
    "layer2_state",
    "layer3_memory",
]


def layer_index(module_basename: str) -> int | None:
    """Return the layer number for a module basename, or None if not a layer."""
    return LAYERS.index(module_basename) if module_basename in LAYERS else None

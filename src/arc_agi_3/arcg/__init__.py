"""arcg — the layered command surface, the sole interface to the game.

Layers (low -> high), order defined in `manifest.py`:
  0 protocol     raw REST verbs; only importer of the ArcClient
  1 intent       agent action intent (move/interact/click/undo) + perception
  2 state        history/snapshot/restore/peek + budget meter (determinism)
  3 memory       notes

Discipline: a module imports strictly downward (any lower layer; never upward).
`store.py` and `..structs`/`..perception`/`..client` are substrate/vocabulary,
not layers — only `..client` is restricted (Layer 0 alone may import it).
Enforced by tests/test_layering.py.
"""

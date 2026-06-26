"""simmer — the functional simulation engine (piper's interface, in imagination).

`step(grid, action) -> grid'` is a PURE function you edit directly to encode each
learned mechanic. `simmer test` differentially checks it against piper's recorded
transition corpus and localizes where it's wrong, so you refine the code until it
reproduces reality. (Compilation from arbor comes later; for now the engine is
hand-written — soft, prose-first hypotheses turned into code.)
"""

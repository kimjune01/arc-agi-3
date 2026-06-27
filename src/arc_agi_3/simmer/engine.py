"""simmer's engine — the model of the game's mechanics.

PRIOR-FREE BY MANDATE. ARC-AGI-3 forbids problem-specific priors: the agent must learn each game
from scratch. So the shipped engine starts knowing NOTHING — `step` is the identity (it predicts
no change for every action, and assumes nothing about what actions even mean: some games have no
movement at all). simmer gains predictive power only once the game's learned mechanics are compiled
in (compile-from-arbor, not built yet). Until then every prediction is a no-op, so every real
transition surprises — which is correct: an untrained model SHOULD mispredict, and the surprises
are the learning signal.

A hand-written LS20 model is kept OUT of this path in `_ls20_reference.py` (a quarantined test
fixture / compile target). It is never imported here.
"""

from __future__ import annotations

import numpy as np

# simmer models no actions yet — mechanics are learned per game, never assumed. Identity until then.
MODELED: frozenset = frozenset()


def step(grid, action: str, x: int | None = None, y: int | None = None) -> np.ndarray:
    """Predict the successor grid. PRIOR-FREE: the identity (no change) until mechanics are learned
    and compiled in. A non-identity prediction here would be a forbidden game-specific prior."""
    return np.asarray(grid, dtype=np.int16).copy()

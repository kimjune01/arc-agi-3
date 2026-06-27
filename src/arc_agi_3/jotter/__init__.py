"""jotter — episodic memory as a CONTENT-ADDRESSED state graph.

piper records a flat (before, action, after) corpus; jotter content-addresses it:
each state is identified by a hash of its grid, so a state reached by different paths
is ONE node (transposition recognition), and `has <hash>` answers "seen before?"
without re-querying. Paired with simmer this is budget optimality: simmer predicts the
next state, jotter says known-or-novel, you spend a piper action only when it's novel.

This is the grounded-facts track only: state identity + dedup, grounded per-action effects
(`effects`), and a content-addressed `trace` of the play (the series-evidence object, a stable
id you can cite as provenance). The git substrate (branches/merge/notes) and the belief track
(verdicts, credence: a derived, non-monotone query) stay deferred until they pay off. The
evidence layer here needs no git.
"""

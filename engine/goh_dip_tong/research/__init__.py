"""The deterministic research package.

Thesis, counter-thesis, catalysts, risks, breakers and the method-comparison
notes — all of them produced by named rules that fire on calculated records,
never by a language model and never by hand.

Three modules, and the split is deliberate:

* :mod:`records` — what a research record *is*, and what makes one invalid
* :mod:`rules` — the rules themselves. Contains no arithmetic
* :mod:`package` — assembly, and the reference check that rejects a claim
  citing something the engine did not produce
"""

from __future__ import annotations

__all__ = ["records", "rules", "package"]

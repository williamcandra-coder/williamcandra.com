"""Run the pipeline CLI as if it were a different date. Test hook only.

The no-change-no-commit guarantee is a claim about *other days*, so a test that
can only exercise today proves nothing — which is exactly how the membership
heartbeat defect survived: every run happened on the date the seed data was
generated, so the churn had nothing to churn against.

Deliberately not an environment variable read by production code. Nothing in
the shipped pipeline can be told what day it is; this driver reaches in from
the outside and is only ever invoked by tests.

    python -m pipeline.goh_dip_tong.tests._clock 2027-03-14 registry-update \
        --write-mode commit

Every module binds ``utc_now_iso`` by name at import, so patching
``settings.utc_now_iso`` alone would miss them all. Import the package first,
then rebind the name wherever it already landed.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys


def install(date_iso: str) -> None:
    """Freeze every pipeline module's clock at ``date_iso`` (YYYY-MM-DD)."""
    stamp = f"{date_iso}T00:00:00Z" if len(date_iso) == 10 else date_iso

    import pipeline.goh_dip_tong as package

    for module in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        if ".tests" in module.name:
            continue
        importlib.import_module(module.name)

    for module in list(sys.modules.values()):
        name = getattr(module, "__name__", "")
        if name.startswith("pipeline.goh_dip_tong") and hasattr(module, "utc_now_iso"):
            module.utc_now_iso = lambda _stamp=stamp: _stamp


def main(argv: list) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    install(argv[0])
    from pipeline.goh_dip_tong.cli import main as cli_main

    return cli_main(argv[1:])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

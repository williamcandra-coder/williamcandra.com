"""The rights gate.

Two questions, answered in one place so no collector has to reason about
licensing on its own:

1. May this provider run at all?
2. May a record from this provider be written to *this* destination?

Destinations are classified as `public` (git-tracked, published with the site)
or `private` (git-ignored, research only). Attempting to write a
PRIVATE_RESEARCH_ONLY record to a public path raises rather than warns — a
rights breach that only logs is a rights breach that ships.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..contracts.enums import NON_RUNNABLE_RIGHTS, RightsStatus
from ..contracts.provider import ProviderDisabledError, RightsViolationError

#: What each status permits. `commit_to_repo` means "may live in a git-tracked
#: path"; `public_display` means "may be rendered in the public UI".
RIGHTS_MATRIX = {
    RightsStatus.PUBLIC_RAW_DATA_APPROVED: {
        "store_raw": True,
        "commit_to_repo": True,
        "public_display": True,
        "redistribute": True,
    },
    RightsStatus.PUBLIC_DERIVED_OUTPUT_APPROVED: {
        "store_raw": False,
        "commit_to_repo": True,
        "public_display": True,
        "redistribute": False,
    },
    RightsStatus.PUBLIC_METADATA_ONLY: {
        "store_raw": False,
        "commit_to_repo": True,
        "public_display": True,
        "redistribute": False,
    },
    RightsStatus.PRIVATE_RESEARCH_ONLY: {
        "store_raw": True,
        "commit_to_repo": False,
        "public_display": False,
        "redistribute": False,
    },
    RightsStatus.DISCOVERY_ONLY: {
        "store_raw": False,
        "commit_to_repo": True,
        "public_display": False,
        "redistribute": False,
    },
    RightsStatus.MANUAL_REVIEW_REQUIRED: {
        "store_raw": False,
        "commit_to_repo": False,
        "public_display": False,
        "redistribute": False,
    },
    RightsStatus.DISABLED: {
        "store_raw": False,
        "commit_to_repo": False,
        "public_display": False,
        "redistribute": False,
    },
}

ACTIONS = ("store_raw", "commit_to_repo", "public_display", "redistribute")


class RightsGate:
    """Answers rights questions from sources.yml."""

    def __init__(self, sources_config: dict) -> None:
        self.config = sources_config or {}
        self.providers = self.config.get("providers", {}) or {}

    # -- lookups -----------------------------------------------------------

    def provider_config(self, provider_id: str) -> dict:
        if provider_id not in self.providers:
            raise RightsViolationError(
                f"provider {provider_id!r} is not declared in sources.yml; "
                f"an undeclared source has no rights and must not run"
            )
        return self.providers[provider_id] or {}

    def status(self, provider_id: str) -> RightsStatus:
        return RightsStatus(
            self.provider_config(provider_id).get(
                "rights_status", RightsStatus.MANUAL_REVIEW_REQUIRED
            )
        )

    def is_enabled(self, provider_id: str) -> bool:
        return bool(self.provider_config(provider_id).get("enabled", False))

    def declared_rights(self, provider_id: str) -> dict:
        """Effective rights: the status matrix, intersected with any explicit
        per-provider block. A provider may narrow its rights below what the
        status allows, never widen them beyond it."""
        status = self.status(provider_id)
        matrix = dict(RIGHTS_MATRIX[status])
        declared = self.provider_config(provider_id).get("rights") or {}
        for action in ACTIONS:
            if action in declared:
                matrix[action] = bool(declared[action]) and matrix[action]
        return matrix

    # -- checks ------------------------------------------------------------

    def may(self, provider_id: str, action: str) -> bool:
        if action not in ACTIONS:
            raise ValueError(f"unknown rights action: {action!r}")
        return self.declared_rights(provider_id)[action]

    def assert_may(self, provider_id: str, action: str, subject: str = "") -> None:
        if not self.may(provider_id, action):
            raise RightsViolationError(
                f"provider {provider_id!r} (rights_status={self.status(provider_id)}) "
                f"does not permit {action!r}"
                + (f" for {subject}" if subject else "")
                + "; document the right in docs/goh-dip-tong/SOURCE_REGISTER.md and "
                "update config/goh-dip-tong/sources.yml before retrying"
            )

    def assert_runnable(self, provider_id: str) -> None:
        """Both locks: the enabled flag AND a resolved rights status."""
        if not self.is_enabled(provider_id):
            raise ProviderDisabledError(
                f"provider {provider_id!r} is disabled in sources.yml"
            )
        status = self.status(provider_id)
        if status in NON_RUNNABLE_RIGHTS:
            raise ProviderDisabledError(
                f"provider {provider_id!r} has rights_status={status} and must not run"
            )

    def runnable_providers(self) -> list:
        return sorted(
            pid
            for pid in self.providers
            if self.is_enabled(pid) and self.status(pid) not in NON_RUNNABLE_RIGHTS
        )

    def blocked_providers(self) -> list:
        return sorted(set(self.providers) - set(self.runnable_providers()))

    # -- destination gating ------------------------------------------------

    @staticmethod
    def is_private_path(path: Path, private_root: Path) -> bool:
        try:
            Path(path).resolve().relative_to(Path(private_root).resolve())
            return True
        except ValueError:
            return False

    def assert_write_allowed(
        self, provider_id: str, destination: Path, private_root: Path, subject: str = ""
    ) -> None:
        """Gate one write.

        A git-tracked destination requires `commit_to_repo`. The private root
        requires only `store_raw`, since nothing there is published.
        """
        if self.is_private_path(destination, private_root):
            self.assert_may(provider_id, "store_raw", subject or str(destination))
            return
        self.assert_may(provider_id, "commit_to_repo", subject or str(destination))

    def destination_for(
        self, provider_id: str, public_path: Path, private_path: Path
    ) -> Path:
        """Route a write to wherever this provider's rights permit.

        This is what lets the market-price collector run end to end today: its
        output is real and validated, it simply lands somewhere that is never
        committed until the rights are documented.
        """
        return public_path if self.may(provider_id, "commit_to_repo") else private_path

    # -- cross-check against the source register ---------------------------

    def cross_check_register(self, register_text: Optional[str]) -> list:
        """Every provider claiming a public right must appear in the register.

        Returns a list of human-readable problems; empty means consistent.
        """
        problems = []
        text = register_text or ""
        for pid in sorted(self.providers):
            rights = self.declared_rights(pid)
            claims_public = rights["commit_to_repo"] or rights["public_display"]
            if claims_public and f"`{pid}`" not in text and pid not in text:
                problems.append(
                    f"{pid}: claims a public right but has no row in SOURCE_REGISTER.md"
                )
            if rights["redistribute"] and self.status(pid) != RightsStatus.PUBLIC_RAW_DATA_APPROVED:
                problems.append(
                    f"{pid}: claims redistribution but status is {self.status(pid)}"
                )
        return problems

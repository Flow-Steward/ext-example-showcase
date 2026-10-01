from __future__ import annotations

from pathlib import Path
import re

import yaml


def test_descriptor_declares_a_bundle_owned_semver_lower_bound() -> None:
    extension_root = Path(__file__).resolve().parents[1]
    descriptor = yaml.safe_load(
        (extension_root / "extension-descriptor.yaml").read_text(encoding="utf-8")
    )

    platform_min = descriptor["runtime"]["compatibility"]["platform_min"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", platform_min)

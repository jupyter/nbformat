# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

# Standard library imports
from __future__ import annotations

import os
from pathlib import Path

# Constants
HERE = Path(__file__).parent.resolve()
REPO_ROOT = HERE.parent.parent


def parse_ref(current_ref):
    """
    Extract version string from github reference string and create environment
    variable for use within the CI workflows.

    Parameters
    ----------
    current_ref: str
        The github reference string.
    """
    if not current_ref.startswith("refs/tags/"):
        msg = f"Invalid ref `{current_ref}`!"
        raise Exception(msg)

    tag_name = current_ref.replace("refs/tags/", "")
    print(tag_name)  # noqa: T201


if __name__ == "__main__":
    current_ref = os.environ.get("GITHUB_REF")
    parse_ref(current_ref)

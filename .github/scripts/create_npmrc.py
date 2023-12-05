# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

# Standard library imports
from __future__ import annotations

from pathlib import Path


def create_npmrc():
    """
    Create NPM configuration file in user home directory to use authentication
    token from environment variables.
    """
    fpath = Path("~/.npmrc").expanduser()
    with fpath.open("w") as fh:
        fh.write("//registry.npmjs.org/:_authToken=${NPM_TOKEN}")


if __name__ == "__main__":
    create_npmrc()

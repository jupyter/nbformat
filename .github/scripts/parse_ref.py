#!/usr/bin/env python

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

# Standard library imports
import os

# Constants
HERE = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))


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
        raise Exception(f"Invalid ref `{current_ref}`!")

    tag_name = current_ref.replace("refs/tags/", "")
    print(tag_name)


if __name__ == "__main__":
    current_ref = os.environ.get("GITHUB_REF")
    parse_ref(current_ref)

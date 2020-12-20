#!/usr/bin/env python
# coding: utf-8

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

# Standard library imports
import os
import subprocess

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
    if not current_ref.startswith("ref/tags/"):
        raise Exception(f"Invalid ref `{current_ref}`!")

    tag_name = current_ref.replace("ref/tags/", "")
    if not tag_name.startswith("v"):
        raise Exception(f"Invalid tag `{tag_name}`!")

    print(f"::set-env name=RELEASE_TAG::{tag_name}")


if __name__ == "__main__":
    current_ref = os.environ.get("GITHUB_REF")
    parse_ref(current_ref)

#!/usr/bin/env python

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

# Standard library imports
import os


def create_npmrc():
    """
    Create NPM configuration file in user home directory to use authentication
    token from environment variables.
    """
    fpath = os.path.expanduser("~/.npmrc")
    with open(fpath, "w") as fh:
        fh.write("//registry.npmjs.org/:_authToken=${NPM_TOKEN}")


if __name__ == "__main__":
    create_npmrc()

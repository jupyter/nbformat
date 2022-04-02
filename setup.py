#!/usr/bin/env python

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.


import os
import subprocess
import sys
from glob import glob

# the name of the project
name = "nbformat"

from distutils.core import setup

pjoin = os.path.join
here = os.path.abspath(os.path.dirname(__file__))
pkg_root = pjoin(here, name)

packages = []
for d, _, _ in os.walk(pjoin(here, name)):
    if os.path.exists(pjoin(d, "__init__.py")):
        packages.append(d[len(here) + 1 :].replace(os.path.sep, "."))

package_data = {
    "nbformat.v3": [
        "nbformat.v3*.schema.json",
    ],
    "nbformat.v4": [
        "nbformat.v4*.schema.json",
    ],
}

version_ns = {}
with open(pjoin(here, name, "_version.py")) as f:
    exec(f.read(), {}, version_ns)


setup_args = dict(
    name=name,
    version=version_ns["__version__"],
    scripts=glob(pjoin("scripts", "*")),
    packages=packages,
    package_data=package_data,
    include_package_data=True,
    description="The Jupyter Notebook format",
    long_description="""
    This package contains the base implementation of the Jupyter Notebook format,
    and Python APIs for working with notebooks.
    """,
    author="Jupyter Development Team",
    author_email="jupyter@googlegroups.com",
    url="http://jupyter.org",
    license="BSD",
    python_requires=">=3.7",
    platforms="Linux, Mac OS X, Windows",
    keywords=["Interactive", "Interpreter", "Shell", "Web"],
    classifiers=[
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)

if "develop" in sys.argv or any(a.startswith("bdist") for a in sys.argv):
    import setuptools

    subprocess.run([sys.executable, "-m", "pre_commit", "install"])
    subprocess.run([sys.executable, "-m", "pre_commit", "install", "--hook-type", "pre-push"])

setuptools_args = {}
install_requires = setuptools_args["install_requires"] = [
    "traitlets>=4.1",
    "jsonschema>=2.6",
    "jupyter_core",
    "fastjsonschema",
]

extras_require = setuptools_args["extras_require"] = {
    "test": ["check-manifest", "testpath", "pytest", "pre-commit"],
}

if "setuptools" in sys.modules:
    setup_args.update(setuptools_args)
    setup_args["entry_points"] = {
        "console_scripts": [
            "jupyter-trust = nbformat.sign:TrustNotebookApp.launch_instance",
        ]
    }
    setup_args.pop("scripts", None)

if __name__ == "__main__":
    setup(**setup_args)

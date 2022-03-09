# The Jupyter Notebook Format

[![codecov.io](https://codecov.io/github/jupyter/nbformat/coverage.svg?branch=master)](https://codecov.io/github/jupyter/nbformat?branch=master)
[![Code Health](https://landscape.io/github/jupyter/nbformat/master/landscape.svg?style=flat)](https://landscape.io/github/jupyter/nbformat/master)
![CI Tests](https://github.com/jupyter/nbformat/workflows/Run%20tests/badge.svg)

`nbformat` contains the reference implementation of the [Jupyter Notebook format][],
and Python APIs for working with notebooks.

There is also a JSON schema for notebook format versions >= 3.

[Jupyter Notebook format]: https://nbformat.readthedocs.org/en/latest/format_description.html

## Installation

From the command line:

``` {.sourceCode .bash}
pip install nbformat
```

## Using a different json schema validator

You can install and use [fastjsonschema](https://horejsek.github.io/python-fastjsonschema/) by running:

``` {.sourceCode .bash}
pip install nbformat[fast]
```

To enable fast validation with `fastjsonschema`, set the environment variable `NBFORMAT_VALIDATOR` to the value `fastjsonschema`.

## Python Version Support

This library supported Python 2.7 and Python 3.5+ for `4.x.x` releases. With Python 2's end-of-life nbformat `5.x.x` supported Python 3 only. Support for Python 3.x versions will be dropped when they are officially sunset by the python organization.

## Contributing

Read [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines on how to setup a local development environment and make code changes back to nbformat.

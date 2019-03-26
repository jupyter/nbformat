# Contributing

We follow the [IPython Contributing Guide](https://github.com/ipython/ipython/blob/master/CONTRIBUTING.md).

## Release guidelines

When there is a release, update the appropriate schema file to reflect the new
version (both in its top-level description and in its minimum minor/major
version numbers in the spec) and copy the file to an archived schema for that
particular version. Also, update the minor format for tests.

For example, for nbformat 4.5, update:

* Update `nbformat/v4/nbformat.v4.schema.json` so
that its top-level description says version 4.5, and its minimum minor version
number is 5 in the schema.
* Copy `nbformat/v4/nbformat.v4.schema.json` to
`nbformat/v4/nbformat.v4.5.schema.json` and commit the file as an archived version
of that particular nbformat specification.
* Update the `nbformat` and `nbformat_minor` variables in `nbformat/v4/nbbase.py`

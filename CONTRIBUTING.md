# Contributing

We follow the [IPython Contributing Guide](https://github.com/ipython/ipython/blob/master/CONTRIBUTING.md).

## Code Styling

`nbformat` has adopted automatic code formatting so you shouldn't
need to worry too much about your code style.
As long as your code is valid,
the pre-commit hook should take care of how it should look.
You can invoke the pre-commit hook by hand at any time with:

```bash
pre-commit run
```

which should run any autoformatting on your code
and tell you about any errors it couldn't fix automatically.
You may also install [black integration](https://black.readthedocs.io/en/stable/integrations/editors.html)
into your text editor to format code automatically.

If you have already committed files before setting up the pre-commit
hook with `pre-commit install`, you can fix everything up using
`pre-commit run --all-files`. You need to make the fixing commit
yourself after that.

Some of the hooks only run on CI by default, but you can invoke them by
running with the `--hook-stage manual` argument.

## Release guidelines

The nbformat version will change in a package release only when there are
material changes in the specification itself. This Python package can be
released with no spec changes. For example, the package version may be bumped to
5.0 to drop Python 2 support with no changes in the nbformat spec number.

When this package is released, if there are material changes in the
specification, update the appropriate schema file to reflect the new version
(both in its top-level description and in its minimum minor/major version
numbers in the spec) and copy the file to an archived schema for that particular
version. Update the minor format for tests as well.

For example, for nbformat package version 4.5, if we see that there are material
changes in the spec, so do the following:

- Update `nbformat/v4/nbformat.v4.schema.json` so that its top-level description
  says spec version 4.4 (which is the next spec version), and its minimum minor
  version number is 4 in the schema.
- Copy `nbformat/v4/nbformat.v4.schema.json` to
  `nbformat/v4/nbformat.v4.4.schema.json` and commit the file as an archived
  version of that particular nbformat specification.
- Update the `nbformat` and `nbformat_minor` variables in
  `nbformat/v4/nbbase.py`

If there are inconsequential changes to the format spec in a package release
(such as fixing a typo in the documentation of a field), just update the
archived spec file when the package is released.

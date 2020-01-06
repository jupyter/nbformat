# Releasing

## Prerequisites

- First check that the docs/changelog.rst is up to date for the next release version
- If you have a schema version change, you need to bump the schema version manually:
    First copy `nbformat/v4/nbformat/.v4.schema.json` to `nbformat/v4/nbformat/.v4.<new_minor_version_here>schema.json`.
    Then edit the top of `nbformat/v4/nbbase.py`:

```
# Change the nbformat_minor and nbformat_schema variables when incrementing the
# nbformat version

# current major version
nbformat = 4

# current minor version
nbformat_minor = <new_minor_version_here>

# schema files for (major, minor) version tuples. (None, None) means the current version
nbformat_schema = {
    (None, None): 'nbformat.v4.schema.json',
    (4, 0): 'nbformat.v4.0.schema.json',
    ...
    (4, <new_minor_version_here>): 'nbformat.v4.<new_minor_version_here>.schema.json'
}
```

    If you do one of these steps but not the others it will fail many tests.

## Push to GitHub

Change from patch to minor or major for appropriate version updates.

```bash
# Commit, test, publish, tag release
bumpversion minor # CHECK FIRST: If the patch version currently set is not sufficient
git commit -am "Prepared <release-id>"
bumpversion suffix  # Remove the .dev
git commit -am "Generated release <release-id>"
git tag <release_version_here>
git push && git push --tags
```

## Push to PyPI

```bash
rm -rf dist/*
rm -rf build/*
python setup.py sdist bdist_wheel
# Double check the dist/* files have the right verison (no `.dev`) and install the wheel to ensure it's good
pip install dist/*
twine upload dist/*
```

## Push to npm

```bash
npm publish
```

Note for JavaScript developers -- `bumpversion` updates the version in `package.json`.

## Prep repo for development

- `bumpversion patch # Resets the patch and dev versions`
- `git commit -am "Resumed patch dev"; git push`

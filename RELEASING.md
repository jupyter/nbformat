# Releasing

## Prerequisites

- First check that the docs/changelog.rst is up to date for the next release version
- If you have a schema version change, you need to bump the schema version manually:
  First copy `nbformat/v4/nbformat/.v4.schema.json` to `nbformat/v4/nbformat/.v4.<new_minor_version_here>schema.json`.
  Then edit the top of `nbformat/v4/nbbase.py`:

  ```python
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

## Update version

We use [bump2version](https://github.com/c4urself/bump2version) to manage versions.

To bump versions we use the `bump2version <VERSION-COMPONENT>` command, where the
version component can take any of the following values:

- `major`: Bump the major component. `5.0.9b0 -> 6.0.0b0`
- `minor`: Bump the minor component. `5.0.9b0 -> 5.1.0b0`
- `patch`: Bump the patch component. `5.0.9b0 -> 5.0.10b0`
- `release`: Bump the release component. `5.0.9b0 -> 5.0.9`
- `build`: Bump the build component. `5.0.9b0 -> 5.0.9b1`

Configuration of bump2version is stored on the [.bumpversion.cfg](https://github.com/jupyter/nbformat/blob/master/.bumpversion.cfg) file and it currently tracks and updates the following files:

- [nbformat/\_version.py](https://github.com/jupyter/nbformat/blob/master/nbformat/_version.py)
- [docs/conf.py](https://github.com/jupyter/nbformat/blob/master/docs/conf.py)
- [package.json](https://github.com/jupyter/nbformat/blob/master/package.json)

### To make a beta release

```bash
# Commit, test, publish, beta tag
bump2version build --tag

git push upstream master
git push upstream --tags
```

### To make a release

Change `<VERSION-COMPONENT>` to `major`, `minor` or `patch` for the corresponding
version updates depending on the release type that will follow.

```bash
# Commit, test, publish, tag release
bump2version release --tag
bump2version <VERSION-COMPONENT>

git push upstream master
git push upstream --tags
```

## Publish packages

PyPI and NPM packages will be built and published on CI when a tag is pushed.

## Manual publish procedure

### Push to PyPI

```bash
rm -rf dist/*
rm -rf build/*
python setup.py sdist bdist_wheel
# Double check the dist/* files have the right verison (no `.dev`) and install the wheel to ensure it's good
pip install dist/*
twine upload dist/*
```

### Push to npm

```bash
npm publish
```

Note for JavaScript developers -- `bump2version` updates the version in `package.json`.

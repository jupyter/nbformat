# Releasing

## Prerequisites

- First check that the docs/changelog.rst is up to date for the next release version

## Push to GitHub

Change from patch to minor or major for appropriate version updates.

```bash
bumpversion suffix  # Remove the .dev
# Commit, test, publish, tag release
bumpversion patch
git push && git push --tags
```

## Push to PyPI

```bash
rm -rf dist/*
rm -rf build/*
python setup.py sdist bdist_wheel
# Double check the dist/* files have the right verison and install the wheel to ensure it's good
pip install dist/*
twine upload dist/*
```

## Prep repo for development

- Change package.json version to next version (e.g. `4.4` -> `4.5`)

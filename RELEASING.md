# Releasing

## Prerequisites

- First check that the docs/changelog.rst is up to date for the next release version

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

## Prep repo for development

- `bumpversion patch # Resets the patch and dev versions`
- `git commit -am "Resumed patch dev"; git push`

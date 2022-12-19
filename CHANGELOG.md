(changelog)=

<!-- <START NEW CHANGELOG ENTRY> -->

## 5.7.1

([Full Changelog](https://github.com/jupyter/nbformat/compare/5.7.0...45ff0cd6dbc5e46a3b620124deeda00aaeebfa29))

### Maintenance and upkeep improvements

- Expose more attributes for typing [#337](https://github.com/jupyter/nbformat/pull/337) ([@blink1073](https://github.com/blink1073))
- Fix lint [#336](https://github.com/jupyter/nbformat/pull/336) ([@blink1073](https://github.com/blink1073))
- Adopt ruff and address lint [#333](https://github.com/jupyter/nbformat/pull/333) ([@blink1073](https://github.com/blink1073))
- Use base setup dependency type [#329](https://github.com/jupyter/nbformat/pull/329) ([@blink1073](https://github.com/blink1073))
- Switch to using Jupyter Releaser [#326](https://github.com/jupyter/nbformat/pull/326) ([@blink1073](https://github.com/blink1073))
- More maintenance cleanup [#325](https://github.com/jupyter/nbformat/pull/325) ([@blink1073](https://github.com/blink1073))
- Handle warning from jupyter client [#322](https://github.com/jupyter/nbformat/pull/322) ([@blink1073](https://github.com/blink1073))
- Add dependabot [#320](https://github.com/jupyter/nbformat/pull/320) ([@blink1073](https://github.com/blink1073))
- Clean up docs and maintenance [#314](https://github.com/jupyter/nbformat/pull/314) ([@blink1073](https://github.com/blink1073))

### Documentation improvements

- Fix changelog target [#321](https://github.com/jupyter/nbformat/pull/321) ([@chrisjsewell](https://github.com/chrisjsewell))
- Clean up docs and maintenance [#314](https://github.com/jupyter/nbformat/pull/314) ([@blink1073](https://github.com/blink1073))

### Other merged PRs

### Contributors to this release

([GitHub contributors page for this release](https://github.com/jupyter/nbformat/graphs/contributors?from=2022-10-10&to=2022-12-19&type=c))

[@blink1073](https://github.com/search?q=repo%3Ajupyter%2Fnbformat+involves%3Ablink1073+updated%3A2022-10-10..2022-12-19&type=Issues) | [@chrisjsewell](https://github.com/search?q=repo%3Ajupyter%2Fnbformat+involves%3Achrisjsewell+updated%3A2022-10-10..2022-12-19&type=Issues) | [@pre-commit-ci](https://github.com/search?q=repo%3Ajupyter%2Fnbformat+involves%3Apre-commit-ci+updated%3A2022-10-10..2022-12-19&type=Issues)

<!-- <END NEW CHANGELOG ENTRY> -->

# Changes in nbformat

## 5.7.0

- Always use jsonschema to handle error reporting.
- Fix deprecation warning suggestion.

## 5.6.1

- Fix handling of `__version__` on Python 3.7.

## 5.6.0

- Fix docs and type annotations for `validator.normalize`.
- Switch to hatch build backend.

## 5.5.0

The biggest change in `nbformat` 5.5.0 is the deprecation of arguments
to `validate()` that try to fix notebooks errors during validation.

`validate()` is a function that is core to the security model of
Jupyter, and is assumed in a number of places to not mutate it's
argument, or try to fix notebooks passed to it.

Auto fixing of notebook in validate can also hide subtle bugs, and will
therefore be updated in a near future to not take any of the argument
related to auto-fixing, and fail instead of silently modifying its
parameters on invalid notebooks.

`nbformat` now contain a `normalize` function that will return a
normalized copy of a notebook that is suitable for validation. While
offered as a convenience we discourage its use and suggest library make
sure to generate valid notebooks.

### Other changes

- `nbformat` is now built with flit, and uses `pyproject.toml`
- Documentation and Deprecations have been updated with version number
  and stack levels.

## 5.4.0

- Add project URLs to `setup.py`
- Fix import in `nbformat.current`
- Add `mypy` and typings support
- Improve CI

## 5.3.0

- Use `fastjsonschema` by default
- Adopt `pre-commit` and auto-formatters
- Increase minimum `jsonschema` to 2.6, handle warnings

## 5.2.0

- Add ability to capture validation errors
- Update supported python versions
- Ensure nbformat minor version is present when upgrading
- Only fix cell ID validation issues if asked
- Return the notebook when no conversion is needed
- Catch AttributeErrors stemming from ipython_genutils as
  ValidationErrors on read
- Don't list pytest-cov as a test dependency
- Remove dependency on IPython genutils
- Include tests in sdist but not wheel

## 5.1.3

- Change id generation to be hash based to avoid problematic word
  combinations
- Added tests for python 3.9
- Fixed setup.py build operations to include package data

## 5.1.2

- Fixed missing file in manifest

## 5.1.1

- Changes convert.upgrade to upgrade minor 4.x versions to 4.5

## 5.1.0

- Implemented CellIds from JEP-62
- Fixed a regression introduced when using fastjsonschema, which does
  not directly support to validate a "reference"/"subschema"
- Removed unreachable/unneeded code
- Added CI workflow for package release on tag push

## 5.0.8

- Add optional support for using \[fastjsonschema\]{.title-ref} as the
  JSON validation library. To enable fast validation, install
  \[fastjsonschema\]{.title-ref} and set the environment variable
  \[NBFORMAT_VALIDATOR\]{.title-ref} to the value
  \[fastjsonschema\]{.title-ref}.

## 5.0.7

- Fixed a bug where default values for validator.get_validator()
  failed with an import error

## 5.0.6

- nbformat.read() function has a better duck-type interface and will
  raise more meaningful error messages if it can't parse a notebook
  document.

## 5.0.5

- Allow notebook format 4.0 and 4.1 to have the arbitrary JSON
  mimebundles from format 4.2 for pragmatic purposes.
- Support reading/writing path-like objects has been added to read
  operations.

## 5.0.4

- Fixed issue causing python 2 to pick up 5.0.x releases.

## 5.0.3

- Removed debug print statements from project.

## 5.0.2

- Added schema validation files for older versions. This was breaking
  notebook generation.

## 5.0.1

## 5.0

[5.0 on GitHub](https://github.com/jupyter/nbformat/milestone/5)

- Starting with 5.0, `nbformat` is now Python 3 only (>= 3.5)
- Add execution timings in code cell metadata for v4 spec.
  `"metadata": { "execution": {...}}` should be populated with
  kernel-specific timing information.
- Documentation for how markup is used in notebooks added
- Link to json schema docs from format page added
- Documented the editable metadata flag
- Update description for collapsed field
- Documented notebook format versions 4.0-4.3 with accurate json
  schema specification files
- Clarified info about name's meaning for cells
- Added a default execution_count of None for
  new_output_cell('execute_result')
- Added support for handling nbjson kwargs
- Wheels now correctly have a LICENSE file
- Travis builds now have a few more execution environments

## 4.4

[4.4 on GitHub](https://github.com/jupyter/nbformat/milestone/9)

- Explicitly state that metadata fields can be ignored.
- Introduce official jupyter namespace inside metadata
  (`metadata.jupyter`).
- Introduce `source_hidden` and `outputs_hidden` as official front-end
  metadata fields to indicate hiding source and outputs areas. **NB**:
  These fields should not be used to hide elements in exported
  formats.
- Fix ending the redundant storage of signatures in the signature
  database.
- `nbformat.validate` can be set to not
  raise a ValidationError if additional properties are included.
- Fix for errors with connecting and backing up the signature
  database.
- Dict-like objects added to NotebookNode attributes are now
  transformed to be NotebookNode objects; transformation also works
  for \[.update()\]{.title-ref}.

## 4.3

[4.3 on GitHub](https://github.com/jupyter/nbformat/milestone/7)

- A new pluggable `SignatureStore` class allows specifying different
  ways to record the signatures of trusted notebooks. The default is
  still an SQLite database. See
  `pluggable_signature_store` for more
  information.
- `nbformat.read` and
  `nbformat.write` accept file paths as
  bytes as well as unicode.
- Fix for calling `nbformat.validate`
  on an empty dictionary.
- Fix for running the tests where the locale makes ASCII the default
  encoding.
- Include nbformat-schema files (v3 and v4) in nbformat-schema npm
  package.
- Include configuration for appveyor's continuous integration
  service.

## 4.2

### 4.2.0

[4.2 on GitHub](https://github.com/jupyter/nbformat/milestones/4.2)

- Update nbformat spec version to 4.2, allowing JSON outputs to have
  any JSONable type, not just `object`, and mime-types of the form
  `application/anything+json`.
- Define basics of `authors` in notebook metadata.
  `nb.metadata.authors` shall be a list of objects with the property
  `name`, a string of each author's full name.
- Update use of traitlets API to require traitlets 4.1.
- Support trusting notebooks on stdin with
  `cat notebook | jupyter trust`

## 4.1

### 4.1.0

[4.1 on GitHub](https://github.com/jupyter/nbformat/milestones/4.1)

- Update nbformat spec version to 4.1, adding support for attachments
  on markdown and raw cells.
- Catch errors opening trust database, falling back on `:memory:` if
  the database cannot be opened.

## 4.0

[4.0 on GitHub](https://github.com/jupyter/nbformat/milestones/4.0)

The first release of nbformat as its own package.

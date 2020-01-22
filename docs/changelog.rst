.. _changelog:

=========================
Changes in nbformat
=========================

5.0.4
=====

- Fixed issue causing python 2 to pick up 5.0.x releases.

5.0.3
=====

- Removed debug print statements from project.

5.0.2
=====

- Added schema validation files for older versions. This was breaking notebook generation.

5.0.1
=====

5.0
===

`5.0 on GitHub https://github.com/jupyter/nbformat/milestone/5`__

- Starting with 5.0, ``nbformat`` is now Python 3 only (>= 3.5)
- Add execution timings in code cell metadata for v4 spec.
  ``"metadata": { "execution": {...}}`` should be populated with kernel-specific
  timing information.
- Documentation for how markup is used in notebooks added
- Link to json schema docs from format page added
- Documented the editable metadata flag
- Update description for collapsed field
- Documented nbformat versions 4.0-4.3 with accurate json schema specification files
- Clarified info about :ref:`name`'s meaning for cells
- Added a default execution_count of None for new_output_cell('execute_result')
- Added support for handling nbjson kwargs
- Wheels now correctly have a LICENSE file
- Travis builds now have a few more execution environments

4.4
===

`4.4 on GitHub <https://github.com/jupyter/nbformat/milestone/9>`__

- Explicitly state that metadata fields can be ignored.
- Introduce official jupyter namespace inside metadata (``metadata.jupyter``).
- Introduce ``source_hidden`` and ``outputs_hidden`` as official front-end
  metadata fields to indicate hiding source and outputs areas. **NB**: These
  fields should not be used to hide elements in exported formats.
- Fix ending the redundant storage of signatures in the signature database.
- :func:`nbformat.validate` can be set to not raise a ValidationError if
  additional properties are included.
- Fix for errors with connecting and backing up the signature database.
- Dict-like objects added to NotebookNode attributes are now transformed to be
  NotebookNode objects; transformation also works for `.update()`.


4.3
===

`4.3 on GitHub <https://github.com/jupyter/nbformat/milestone/7>`__

- A new pluggable ``SignatureStore`` class allows specifying different ways to
  record the signatures of trusted notebooks. The default is still an SQLite
  database. See :ref:`pluggable_signature_store` for more information.
- :func:`nbformat.read` and :func:`nbformat.write` accept file paths as bytes
  as well as unicode.
- Fix for calling :func:`nbformat.validate` on an empty dictionary.
- Fix for running the tests where the locale makes ASCII the default encoding.
- Include nbformat-schema files (v3 and v4) in nbformat-schema npm package.
- Include configuration for appveyor's continuous integration service.

4.2
===


4.2.0
-----

`4.2 on GitHub <https://github.com/jupyter/nbformat/milestones/4.2>`__

- Update nbformat spec version to 4.2, allowing JSON outputs to have any JSONable type,  not just ``object``,
  and mime-types of the form ``application/anything+json``.
- Define basics of ``authors`` in notebook metadata.
  ``nb.metadata.authors`` shall be a list of objects with the property ``name``, a string of each author's full name.
- Update use of traitlets API to require traitlets 4.1.
- Support trusting notebooks on stdin with ``cat notebook | jupyter trust``


4.1
===


4.1.0
-----

`4.1 on GitHub <https://github.com/jupyter/nbformat/milestones/4.1>`__

- Update nbformat spec version to 4.1, adding support for attachments on markdown and raw cells.
- Catch errors opening trust database, falling back on ``:memory:`` if the database cannot be opened.


4.0
===

`4.0 on GitHub <https://github.com/jupyter/nbformat/milestones/4.0>`__

The first release of nbformat as its own package.

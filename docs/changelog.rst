.. _changelog:

=========================
Changes in nbformat
=========================

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

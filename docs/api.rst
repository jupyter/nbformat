Python API for working with notebook files
==========================================

.. module:: nbformat

Reading and writing
-------------------

.. autofunction:: read

.. autofunction:: reads

The reading functions require you to pass the *as_version* parameter. Your
code should specify the notebook format that it knows how to work with: for
instance, if your code handles version 4 notebooks::

    nb = nbformat.read('path/to/notebook.ipynb', as_version=4)

This will automatically upgrade or downgrade notebooks in other versions of
the notebook format to the structure your code knows about.

.. autofunction:: write

.. autofunction:: writes

.. data:: NO_CONVERT

   This special value can be passed to the reading and writing functions, to
   indicate that the notebook should be loaded/saved in the format it's supplied.

.. data:: current_nbformat
          current_nbformat_minor

   These integers represent the current notebook format version that the
   nbformat module knows about.

NotebookNode objects
--------------------

The functions in this module work with :class:`NotebookNode` objects, which are
like dictionaries, but allow attribute access (``nb.cells``). The structure of
these objects matches the notebook format described in :doc:`format_description`.

.. autoclass:: NotebookNode

.. autofunction:: from_dict

Other functions
---------------

.. autofunction:: convert

.. autofunction:: validate

.. autoclass:: ValidationError

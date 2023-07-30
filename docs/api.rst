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

Constructing notebooks programmatically
---------------------------------------

.. module:: nbformat.v4

These functions return :class:`~.NotebookNode` objects with the necessary fields.

.. autofunction:: new_notebook

.. autofunction:: new_code_cell

.. autofunction:: new_markdown_cell

.. autofunction:: new_raw_cell

.. autofunction:: new_output

.. autofunction:: output_from_msg


Notebook signatures
-------------------

.. module:: nbformat.sign

This machinery is used by the notebook web application to record which notebooks
are *trusted*, and may show dynamic output as soon as they're loaded. See
:ref:`server:server_security` for more information.

.. autoclass:: NotebookNotary

   .. automethod:: sign

   .. automethod:: unsign

   .. automethod:: check_signature

   .. automethod:: mark_cells

   .. automethod:: check_cells

.. _pluggable_signature_store:

Signature storage
*****************

Signatures are stored using a pluggable :class:`SignatureStore` subclass. To
implement your own, override the methods below and configure
``NotebookNotary.store_factory``.

.. autoclass:: SignatureStore

   .. automethod:: store_signature

   .. automethod:: remove_signature

   .. automethod:: check_signature

   .. automethod:: close

By default, :class:`NotebookNotary` will use an SQLite based store if SQLite
bindings are available, and an in-memory store otherwise.

.. autoclass:: SQLiteSignatureStore

.. autoclass:: MemorySignatureStore

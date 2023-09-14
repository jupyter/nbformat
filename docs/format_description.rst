.. _notebook_file_format:

========================
The Notebook file format
========================

The official Jupyter Notebook format is defined with
`this JSON schema <https://github.com/jupyter/nbformat/blob/master/nbformat/v4/nbformat.v4.schema.json>`_,
which is used by Jupyter tools to validate notebooks.

This page contains a human-readable description of the notebook format.

.. note::

    *All* metadata fields are optional.
    While the types and values of some metadata fields are defined,
    no metadata fields are required to be defined. Any metadata field
    may also be ignored.


Top-level structure
===================

At the highest level, a Jupyter notebook is a dictionary with a few keys:

- metadata (dict)
- nbformat (int)
- nbformat_minor (int)
- cells (list)

.. sourcecode:: python

    {
        "metadata": {
            "kernel_info": {
                # if kernel_info is defined, its name field is required.
                "name": "the name of the kernel"
            },
            "language_info": {
                # if language_info is defined, its name field is required.
                "name": "the programming language of the kernel",
                "version": "the version of the language",
                "codemirror_mode": "The name of the codemirror mode to use [optional]",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 0,
        "cells": [
            # list of cell dictionaries, see below
        ],
    }

Some fields, such as code input and text output, are characteristically multi-line strings.
When these fields are written to disk, they **may** be written as a list of strings,
which should be joined with ``''`` when reading back into memory.
In programmatic APIs for working with notebooks (Python, Javascript),
these are always re-joined into the original multi-line string.
If you intend to work with notebook files directly,
you must allow multi-line string fields to be either a string or list of strings.


Cell Types
==========

There are a few basic cell types for encapsulating code and text.
All cells have the following basic structure:

.. sourcecode:: python

    {
        "cell_type": "type",
        "metadata": {},
        "source": "single string or [list, of, strings]",
    }

.. note::

    On disk, multi-line strings **MAY** be split into lists of strings.
    When read with the nbformat Python API,
    these multi-line strings will always be a single string.

Markdown cells
--------------

Markdown cells are used for body-text, and contain markdown,
as defined in `GitHub-flavored markdown`_, and implemented in marked_.

.. _GitHub-flavored markdown: https://help.github.com/articles/github-flavored-markdown
.. _marked: https://github.com/chjj/marked

.. sourcecode:: python

    {
        "cell_type": "markdown",
        "metadata": {},
        "source": "[multi-line *markdown*]",
    }

.. versionchanged:: nbformat 4.0

    Heading cells have been removed in favor of simple headings in markdown.


Code cells
----------

Code cells are the primary content of Jupyter notebooks.
They contain source code in the language of the document's associated kernel,
and a list of outputs associated with executing that code.
They also have an execution_count, which must be an integer or ``null``.

.. sourcecode:: python

    {
        "cell_type": "code",
        "execution_count": 1,  # integer or null
        "metadata": {
            "collapsed": True,  # whether the output of the cell is collapsed
            "scrolled": False,  # any of true, false or "auto"
        },
        "source": "[some multi-line code]",
        "outputs": [
            {
                # list of output dicts (described below)
                "output_type": "stream",
                # ...
            }
        ],
    }

.. versionchanged:: nbformat 4.0

    ``input`` was renamed to ``source``, for consistency among cell types.

.. versionchanged:: nbformat 4.0

    ``prompt_number`` renamed to ``execution_count``

Code cell outputs
-----------------

A code cell can have a variety of outputs (stream data or rich mime-type output).
These correspond to :ref:`messages <messaging>` produced as a result of executing the cell.

All outputs have an ``output_type`` field,
which is a string defining what type of output it is.


stream output
*************

.. sourcecode:: python

    {
        "output_type": "stream",
        "name": "stdout",  # or stderr
        "text": "[multiline stream text]",
    }

.. versionchanged:: nbformat 4.0

    The ``stream`` key was changed to ``name`` to match
    the stream message.

.. _display-data:

display_data
************

Rich display outputs, as created by ``display_data`` messages,
contain data keyed by mime-type. This is often called a mime-bundle,
and shows up in various locations in the notebook format and message spec.
The metadata of these messages may be keyed by mime-type as well.



.. sourcecode:: python

    {
        "output_type": "display_data",
        "data": {
            "text/plain": "[multiline text data]",
            "image/png": "[base64-encoded-multiline-png-data]",
            "application/json": {
                # JSON data is included as-is
                "key1": "data",
                "key2": ["some", "values"],
                "key3": {"more": "data"},
            },
            "application/vnd.exampleorg.type+json": {
                # JSON data, included as-is, when the mime-type key ends in +json
                "key1": "data",
                "key2": ["some", "values"],
                "key3": {"more": "data"},
            },
        },
        "metadata": {
            "image/png": {
                "width": 640,
                "height": 480,
            },
        },
    }


.. versionchanged:: nbformat 4.0

    ``application/json`` output is no longer double-serialized into a string.

.. versionchanged:: nbformat 4.0

    mime-types are used for keys, instead of a combination of short names (``text``)
    and mime-types, and are stored in a ``data`` key, rather than the top-level.
    i.e. ``output.data['image/png']`` instead of ``output.png``.


execute_result
**************

Results of executing a cell (as created by ``displayhook`` in Python)
are stored in ``execute_result`` outputs.
``execute_result`` outputs are identical to ``display_data``,
adding only a ``execution_count`` field, which must be an integer.

.. sourcecode:: python

    {
        "output_type": "execute_result",
        "execution_count": 42,
        "data": {
            "text/plain": "[multiline text data]",
            "image/png": "[base64-encoded-multiline-png-data]",
            "application/json": {
                # JSON data is included as-is
                "json": "data",
            },
        },
        "metadata": {
            "image/png": {
                "width": 640,
                "height": 480,
            },
        },
    }

.. versionchanged:: nbformat 4.0

    ``pyout`` renamed to ``execute_result``

.. versionchanged:: nbformat 4.0

    ``prompt_number`` renamed to ``execution_count``


error
*****

Failed execution may show an error::

    {
        'output_type': 'error',
        'ename' : str,   # Exception name, as a string
        'evalue' : str,  # Exception value, as a string

        # The traceback will contain a list of frames,
        # represented each as a string.
        'traceback' : list,
    }

.. versionchanged:: nbformat 4.0

    ``pyerr`` renamed to ``error``


.. _raw nbconvert cells:

Raw NBConvert cells
-------------------

.. _nbconvert: https://nbconvert.readthedocs.org

A raw cell is defined as content that should be included *unmodified* in `nbconvert`_ output.
For example, this cell could include raw LaTeX for nbconvert to pdf via latex,
or restructured text for use in Sphinx documentation.

The notebook authoring environment does not render raw cells.

The only logic in a raw cell is the ``format`` metadata field.
If defined, it specifies which nbconvert output format is the intended target
for the raw cell. When outputting to any other format,
the raw cell's contents will be excluded.
In the default case when this value is undefined,
a raw cell's contents will be included in any nbconvert output,
regardless of format.

.. sourcecode:: python

    {
        "cell_type": "raw",
        "metadata": {
            # the mime-type of the target nbconvert format.
            # nbconvert to formats other than this will exclude this cell.
            "format": "mime/type"
        },
        "source": "[some nbformat output text]",
    }


Cell attachments
----------------

Markdown and raw cells can have a number of attachments, typically inline
images that can be referenced in the markdown content of a cell. The ``attachments``
dictionary of a cell contains a set of mime-bundles (see :ref:`display_data`)
keyed by filename that represents the files attached to the cell.

.. note::

  The ``attachments`` dictionary is an optional field and can be undefined or empty if the cell does not have any attachments.


.. sourcecode:: python

    {
        "cell_type": "markdown",
        "metadata": {},
        "source": ["Here is an *inline* image ![inline image](attachment:test.png)"],
        "attachments": {"test.png": {"image/png": "base64-encoded-png-data"}},
    }


Cell ids
--------

Since the 4.5 schema release, all cells have an ``id`` field which must be a string of length
1-64 with alphanumeric, ``-``, and ``_`` as legal characters to use. These ids must be unique to
any given Notebook following the nbformat spec.

The full rules and guidelines for using cells ids is captured in the corresponding
`JEP Proposal <https://github.com/jupyter/enhancement-proposals/blob/master/62-cell-id/cell-id.md>`_.

If attempting to add similar support to other languages supporting notebooks specs, this
`Example PR <https://github.com/jupyter/nbformat/pull/189>`_ can be used as a reference to follow.


Backward-compatible changes
===========================

The notebook format is an evolving format. When backward-compatible changes are made,
the notebook format minor version is incremented. When backward-incompatible changes are made,
the major version is incremented.

As of nbformat 4.x, backward-compatible changes include:

- new fields in any dictionary (notebook, cell, output, metadata, etc.)
- new cell types
- new output types

New cell or output types will not be rendered in versions that do not recognize them,
but they will be preserved.


Because the nbformat python package used to be less strict about validating
notebook files, two features have been backported from nbformat 4.x to
nbformat 4.0. These are:

* ``attachment`` top-level keys in the Markdown and raw cell types
  (backported from nbformat 4.1)
* Mime-bundle attributes are JSON data if the mime-type key ends in ``+json``
  (backported from nbformat 4.2)

These backports ensure that any valid nbformat 4.4 file is also a valid
nbformat 4.0 file.

Metadata
========

Metadata is a place that you can put arbitrary JSONable information about
your notebook, cell, or output. Because it is a shared namespace,
any custom metadata should use a sufficiently unique namespace,
such as ``metadata.kaylees_md.foo = "bar"``.

Metadata fields officially defined for Jupyter notebooks are listed here:

Notebook metadata
-----------------

The following metadata keys are defined at the notebook level:

=========== =============== ==============
Key         Value           Interpretation
=========== =============== ==============
kernelspec  dict            A :ref:`kernel specification <kernelspecs>`
authors     list of dicts   A list of authors of the document
=========== =============== ==============

A notebook's authors is a list of dictionaries containing information about each author of the notebook.
Currently, only the name is required.
Additional fields may be added.

.. sourcecode:: python

    nb.metadata.authors = [
        {
            "name": "Fernando Perez",
        },
        {
            "name": "Brian Granger",
        },
    ]

Cell metadata
-------------

Official Jupyter metadata, as used by Jupyter frontends should be placed in the
``metadata.jupyter`` namespace, for example ``metadata.jupyter.foo = "bar"``.

The following metadata keys are defined at the cell level:

=========== =============== ==============
Key         Value           Interpretation
=========== =============== ==============
collapsed   bool            Whether the cell's output container should be collapsed
scrolled    bool or 'auto'  Whether the cell's output is scrolled, unscrolled, or autoscrolled
deletable   bool            If False, prevent deletion of the cell
editable    bool            If False, prevent editing of the cell (by definition, this also prevents deleting the cell)
format      'mime/type'     The mime-type of a :ref:`Raw NBConvert Cell <raw nbconvert cells>`
name        str             A name for the cell. Should be unique across the notebook. Uniqueness must be verified outside of the json schema.
tags        list of str     A list of string tags on the cell. Commas are not allowed in a tag
jupyter     dict            A namespace holding jupyter specific fields. See docs below for more details
execution   dict            A namespace holding execution specific fields. See docs below for more details
=========== =============== ==============

The following metadata keys are defined at the cell level within the ``jupyter`` namespace

=============== =============== ==============
Key             Value           Interpretation
=============== =============== ==============
source_hidden   bool            Whether the cell's source should be shown
outputs_hidden  bool            Whether the cell's outputs should be shown
=============== =============== ==============

The following metadata keys are defined at the cell level within the ``execution`` namespace.
These are lower level fields capturing common kernel message timestamps for better visibility
in applications where needed. Most users will not look at these directly.

==================== ================ ==============
Key                  Value            Interpretation
==================== ================ ==============
iopub.execute_input  ISO 8601 format  Indicates the time at which the kernel broadcasts an execute_input message. This represents the time when request for work was received by the kernel.
iopub.status.busy    ISO 8601 format  Indicates the time at which the iopub channel's kernel status message is 'busy'. This represents the time when work was started by the kernel.
shell.execute_reply  ISO 8601 format  Indicates the time at which the shell channel's execute_reply status message was created. This represents the time when work was completed by the kernel.
iopub.status.idle    ISO 8601 format  Indicates the time at which the iopub channel's kernel status message is 'idle'. This represents the time when the kernel is ready to accept new work.
==================== ================ ==============

Output metadata
---------------

The following metadata keys are defined for code cell outputs:

=========== =============== ==============
Key         Value           Interpretation
=========== =============== ==============
isolated    bool            Whether the output should be isolated into an IFrame
=========== =============== ==============

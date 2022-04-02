.. _markup:

========================
Supported markup formats
========================

The Jupyter Notebook format supports Markdown in text cells.
There is not a strict specification for the flavor of markdown that
is supported, but this page should help guide the user / developer
in understanding what behavior to expect with Jupyter interfaces and
markup languages.


What flavor of Markdown does the notebook format support?
=========================================================

Most Jupyter Notebook interfaces use the `marked.js <https://github.com/markedjs/marked>`_
JavaScript library for rendering markdown. This supports markdown in
the following markdown flavors:

*  `CommonMark <http://spec.commonmark.org/0.29/>`_.
* `GitHub Flavored Markdown <https://github.github.com/gfm/>`_

See the `Marked.js specification page <https://marked.js.org>`_
for more information.

.. note::

    Currently, as the Marked.js specification changes, so to will the
    behavior of Markdown in many notebook interfaces.


MathJax configuration
=====================

There are a few extra modifications that Jupyter interfaces tend to use for
rendering markdown. Specifically, they automatically render mathematical
equations using `MathJax <https://www.mathjax.org/>`_.

This is currently the MathJax configuration that is used:

.. code:: javascript

    {
        tex2jax: {
            inlineMath: [ ['$','$'], ["\\(","\\)"] ],
            displayMath: [ ['$$','$$'], ["\\[","\\]"] ],
            processEscapes: true,
            processEnvironments: true
        },
        MathML: {
            extensions: ['content-mathml.js']
        },
        displayAlign: 'center',
        "HTML-CSS": {
            availableFonts: [],
            imageFont: null,
            preferredFont: null,
            webFont: "STIX-Web",
            styles: {'.MathJax_Display': {"margin": 0}},
            linebreaks: { automatic: true }
        },
    }

See the `MathJax script for the classic Notebook UI <https://github.com/jupyter/notebook/blob/6.4.x/notebook/static/notebook/js/mathjaxutils.js>`_
for one example.

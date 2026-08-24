from __future__ import annotations

from copy import deepcopy

import pytest

from nbformat.notebooknode import NotebookNode, from_dict


def test_no_instance_dict_by_default():
    """A fresh node must not carry a per-instance ``__dict__``.

    ``_allownew`` is already True as a class attribute, so setting it per
    instance would materialize a ``__dict__`` on every node in a notebook just
    to hold one redundant bool -- and that dict is larger than the node itself.
    """
    assert not NotebookNode({"a": 1}).__dict__


def test_from_dict_leaves_nodes_without_instance_dict():
    nb = from_dict({"cells": [{"cell_type": "code", "metadata": {"tags": ["t"]}}]})
    assert not nb.__dict__
    assert not nb["cells"][0].__dict__
    assert not nb["cells"][0]["metadata"].__dict__


def test_allow_new_attr_still_restricts():
    node = NotebookNode({"a": 1})
    node["b"] = 2  # new keys allowed by default

    node.allow_new_attr(False)
    assert node._allownew is False
    with pytest.raises(KeyError):
        node["c"] = 3
    node["a"] = 10  # existing keys still assignable
    assert node["a"] == 10


def test_deepcopy_preserves_allownew():
    node = NotebookNode({"a": 1})
    node.allow_new_attr(False)

    copied = deepcopy(node)
    assert copied == node
    assert copied._allownew is False
    with pytest.raises(KeyError):
        copied["c"] = 3


def test_deepcopy_of_default_node_stays_permissive():
    copied = deepcopy(NotebookNode({"a": 1}))
    assert not copied.__dict__
    copied["b"] = 2
    assert copied["b"] == 2

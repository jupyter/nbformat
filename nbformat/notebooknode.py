"""NotebookNode - adding attribute access to dicts"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy as _deepcopy

from ._struct import Struct

# Values `deepcopy` returns as-is, so they can be stored without recursing.
_ATOMIC_TYPES = (str, int, float, bool, bytes, type(None), complex)


class NotebookNode(Struct):
    """A dict-like node with attribute-access"""

    def __setitem__(self, key, value):
        """Set an item on the notebook."""
        if isinstance(value, Mapping) and not isinstance(value, NotebookNode):
            value = from_dict(value)
        super().__setitem__(key, value)

    def __deepcopy__(self, memo):
        """Deep-copy the node without going through `copy._reconstruct`.

        `copy.deepcopy` only takes its fast path for exact `dict`s, so a `dict`
        subclass falls back to the generic `__reduce_ex__` machinery once per
        node. Notebooks get deep-copied on every `isvalid`, `normalize` and
        `writes` call, which makes that fallback worth avoiding.
        """
        new = self.__class__()
        memo[id(self)] = new
        for key, value in self.items():
            value_type = type(value)
            if value_type in _ATOMIC_TYPES:
                dict.__setitem__(new, key, value)
            elif value_type is list:
                # a plain dict inside a list stays a plain dict, as it would
                # under the generic deepcopy
                dict.__setitem__(new, key, [_deepcopy(item, memo) for item in value])
            else:
                # assign through __setitem__ so a Mapping value is coerced to a
                # NotebookNode, which is what the generic deepcopy path did
                new[key] = _deepcopy(value, memo)
        # restore instance state (Struct's `_allownew`) last: with `_allownew`
        # False, __setitem__ refuses new keys.
        if self.__dict__:
            new.__dict__.update(_deepcopy(self.__dict__, memo))
        return new

    def update(self, *args, **kwargs):
        """
        A dict-like update method based on CPython's MutableMapping `update`
        method.
        """
        if len(args) > 1:
            raise TypeError("update expected at most 1 arguments, got %d" % len(args))
        if args:
            other = args[0]
            if isinstance(other, Mapping):  # noqa: SIM114
                for key in other:
                    self[key] = other[key]
            elif hasattr(other, "keys"):
                for key in other:
                    self[key] = other[key]
            else:
                for key, value in other:
                    self[key] = value
        for key, value in kwargs.items():
            self[key] = value


def from_dict(d):
    """Convert dict to dict-like NotebookNode

    Recursively converts any dict in the container to a NotebookNode.
    This does not check that the contents of the dictionary make a valid
    notebook or part of a notebook.
    """
    if isinstance(d, dict):
        return NotebookNode({k: from_dict(v) for k, v in d.items()})
    if isinstance(d, (tuple, list)):
        return [from_dict(i) for i in d]
    return d

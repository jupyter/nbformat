"""NotebookNode - adding attribute access to dicts"""

from ipython_genutils.ipstruct import Struct


class NotebookNode(Struct):
    """A dict-like node with attribute-access"""

    def __setitem__(self, key, value):
        """Set an item with check for allownew.
        Examples
        --------
        >>> s = Struct()
        >>> s['a'] = 10
        >>> s.allow_new_attr(False)
        >>> s['a'] = 10
        >>> s['a']
        10
        >>> try:
        ...     s['b'] = 20
        ... except KeyError:
        ...     print('this is not allowed')
        ...
        this is not allowed
        """
        if not self._allownew and key not in self:
            raise KeyError(
                "can't create new attribute %s when allow_new_attr(False)" % key)

        if isinstance(value, dict):
            dict.__setitem__(self, key, from_dict(value))
        else:
            dict.__setitem__(self, key, value)


def from_dict(d):
    """Convert dict to dict-like NotebookNode
    
    Recursively converts any dict in the container to a NotebookNode.
    This does not check that the contents of the dictionary make a valid
    notebook or part of a notebook.
    """
    if isinstance(d, dict):
        return NotebookNode({k:from_dict(v) for k,v in d.items()})
    elif isinstance(d, (tuple, list)):
        return [from_dict(i) for i in d]
    else:
        return d

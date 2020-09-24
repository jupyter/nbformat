# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""
Common validator wrapper to provide a uniform usage of other schema validation
libraries.
"""

from jsonschema import Draft4Validator as _JsonSchemaValidator
from jsonschema import ValidationError

try:
    import fastjsonschema
    from fastjsonschema import JsonSchemaException as _JsonSchemaException
except ImportError:
    fastjsonschema = None
    _JsonSchemaException = ValidationError


class Validator:
    """
    Common validator wrapper to provide a uniform usage of other schema validation
    libraries.
    """

    def __init__(self, schema):
        self._schema = schema

        # Validation libraries
        self._jsonschema = _JsonSchemaValidator(schema)  # Default
        self._fastjsonschema_validate = fastjsonschema.compile(schema) if fastjsonschema else None

    def validate(self, data):
        """
        Validate the schema of ``data``.

        Will use ``fastjsonschema`` if available.
        """
        if fastjsonschema:
            try:
                self._fastjsonschema_validate(data)
            except _JsonSchemaException as e:
                raise ValidationError(e.message)
        else:
            self._jsonschema.validate(data)

    def iter_errors(self, data, schema=None):
        return self._jsonschema.iter_errors(data, schema)

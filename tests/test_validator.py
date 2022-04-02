"""Test nbformat.validator"""

# Copyright (c) IPython Development Team.
# Distributed under the terms of the Modified BSD License.

import json
import os
import re

import pytest
from jsonschema import ValidationError

import nbformat
from nbformat import read
from nbformat.json_compat import VALIDATORS
from nbformat.validator import isvalid, iter_validate, validate

from .base import TestsBase


# Fixtures
@pytest.fixture(autouse=True)
def clean_env_before_and_after_tests():
    """Fixture to clean up env variables before and after tests."""
    os.environ.pop("NBFORMAT_VALIDATOR", None)
    yield
    os.environ.pop("NBFORMAT_VALIDATOR", None)


# Helpers
def set_validator(validator_name):
    os.environ["NBFORMAT_VALIDATOR"] = validator_name


@pytest.mark.parametrize("validator_name", VALIDATORS)
def test_nb2(validator_name):
    """Test that a v2 notebook converted to current passes validation"""
    set_validator(validator_name)
    with TestsBase.fopen("test2.ipynb", "r") as f:
        nb = read(f, as_version=4)
    validate(nb)
    assert isvalid(nb)


@pytest.mark.parametrize("validator_name", VALIDATORS)
def test_nb3(validator_name):
    """Test that a v3 notebook passes validation"""
    set_validator(validator_name)
    with TestsBase.fopen("test3.ipynb", "r") as f:
        nb = read(f, as_version=4)
    validate(nb)
    assert isvalid(nb)


@pytest.mark.parametrize("validator_name", VALIDATORS)
def test_nb4(validator_name):
    """Test that a v4 notebook passes validation"""
    set_validator(validator_name)
    with TestsBase.fopen("test4.ipynb", "r") as f:
        nb = read(f, as_version=4)
    validate(nb)
    assert isvalid(nb)


@pytest.mark.parametrize("validator_name", VALIDATORS)
def test_nb4_document_info(validator_name):
    """Test that a notebook with document_info passes validation"""
    set_validator(validator_name)
    with TestsBase.fopen("test4docinfo.ipynb", "r") as f:
        nb = read(f, as_version=4)
    validate(nb)
    assert isvalid(nb)


@pytest.mark.parametrize("validator_name", VALIDATORS)
def test_nb4custom(validator_name):
    """Test that a notebook with a custom JSON mimetype passes validation"""
    set_validator(validator_name)
    with TestsBase.fopen("test4custom.ipynb", "r") as f:
        nb = read(f, as_version=4)
    validate(nb)
    assert isvalid(nb)


@pytest.mark.parametrize("validator_name", VALIDATORS)
def test_nb4jupyter_metadata(validator_name):
    """Test that a notebook with a jupyter metadata passes validation"""
    set_validator(validator_name)
    with TestsBase.fopen("test4jupyter_metadata.ipynb", "r") as f:
        nb = read(f, as_version=4)
    validate(nb)
    assert isvalid(nb)


@pytest.mark.parametrize("validator_name", VALIDATORS)
def test_nb4jupyter_metadata_timings(validator_name):
    """Tests that a notebook with "timing" in metadata passes validation"""
    set_validator(validator_name)
    with TestsBase.fopen("test4jupyter_metadata_timings.ipynb", "r") as f:
        nb = read(f, as_version=4)
    validate(nb)
    assert isvalid(nb)


@pytest.mark.parametrize("validator_name", VALIDATORS)
def test_invalid(validator_name):
    """Test than an invalid notebook does not pass validation"""
    set_validator(validator_name)
    # this notebook has a few different errors:
    # - one cell is missing its source
    # - invalid cell type
    # - invalid output_type
    with TestsBase.fopen("invalid.ipynb", "r") as f:
        nb = read(f, as_version=4)
    with pytest.raises(ValidationError):
        validate(nb)
    assert not isvalid(nb)


@pytest.mark.parametrize("validator_name", VALIDATORS)
def test_validate_empty(validator_name):
    """Test that an empty notebook (invalid) fails validation"""
    set_validator(validator_name)
    with pytest.raises(ValidationError) as e:
        validate({})


@pytest.mark.parametrize("validator_name", VALIDATORS)
def test_future(validator_name):
    """Test that a notebook from the future with extra keys passes validation"""
    set_validator(validator_name)
    with TestsBase.fopen("test4plus.ipynb", "r") as f:
        nb = read(f, as_version=4)
    with pytest.raises(ValidationError):
        validate(nb, version=4, version_minor=3)

    assert not isvalid(nb, version=4, version_minor=3)
    assert isvalid(nb)


# This is only a valid test for the default validator, jsonschema
@pytest.mark.parametrize("validator_name", ["jsonschema"])
def test_validation_error(validator_name):
    set_validator(validator_name)
    with TestsBase.fopen("invalid.ipynb", "r") as f:
        nb = read(f, as_version=4)
    with pytest.raises(ValidationError) as exception_info:
        validate(nb)

    s = str(exception_info.value)
    assert re.compile(r"validating .required. in markdown_cell").search(s)
    assert re.compile(r"source.* is a required property").search(s)
    assert re.compile(r"On instance\[u?['\"].*cells['\"]\]\[0\]").search(s)
    assert len(s.splitlines()) < 10


# This is only a valid test for the default validator, jsonschema
@pytest.mark.parametrize("validator_name", ["jsonschema"])
def test_iter_validation_error(validator_name):
    set_validator(validator_name)
    with TestsBase.fopen("invalid.ipynb", "r") as f:
        nb = read(f, as_version=4)

    errors = list(iter_validate(nb))
    assert len(errors) == 3
    assert {e.ref for e in errors} == {"markdown_cell", "heading_cell", "bad stream"}


@pytest.mark.parametrize("validator_name", VALIDATORS)
def test_iter_validation_empty(validator_name):
    """Test that an empty notebook (invalid) fails validation via iter_validate"""
    set_validator(validator_name)
    errors = list(iter_validate({}))
    assert len(errors) == 1
    assert type(errors[0]) == ValidationError


@pytest.mark.parametrize("validator_name", VALIDATORS)
def test_validation_no_version(validator_name):
    """Test that an invalid notebook with no version fails validation"""
    set_validator(validator_name)
    with pytest.raises(ValidationError) as e:
        validate({"invalid": "notebook"})


def test_invalid_validator_raises_value_error():
    """Test that an invalid notebook with no version fails validation"""
    set_validator("foobar")
    with pytest.raises(ValueError):
        with TestsBase.fopen("test2.ipynb", "r") as f:
            nb = read(f, as_version=4)


def test_invalid_validator_raises_value_error_after_read():
    """Test that an invalid notebook with no version fails validation"""
    set_validator("jsonschema")
    with TestsBase.fopen("test2.ipynb", "r") as f:
        nb = read(f, as_version=4)

    set_validator("foobar")
    with pytest.raises(ValueError):
        validate(nb)


def test_fallback_validator_with_iter_errors_using_ref(recwarn):
    """
    Test that when creating a standalone object (code_cell etc)
    the default validator is used as fallback.
    """
    import nbformat

    set_validator("fastjsonschema")
    nbformat.v4.new_code_cell()
    nbformat.v4.new_markdown_cell()
    nbformat.v4.new_raw_cell()
    assert len(recwarn) == 0


def test_non_unique_cell_ids():
    """Test than a non-unique cell id does not pass validation"""
    import nbformat

    with TestsBase.fopen("invalid_unique_cell_id.ipynb", "r") as f:
        # Avoids validate call from `.read`
        nb = nbformat.from_dict(json.load(f))
    with pytest.raises(ValidationError):
        validate(nb, repair_duplicate_cell_ids=False)
    # try again to verify that we didn't modify the content
    with pytest.raises(ValidationError):
        validate(nb, repair_duplicate_cell_ids=False)


def test_repair_non_unique_cell_ids():
    """Test that we will repair non-unique cell ids if asked during validation"""
    import nbformat

    with TestsBase.fopen("invalid_unique_cell_id.ipynb", "r") as f:
        # Avoids validate call from `.read`
        nb = nbformat.from_dict(json.load(f))
    validate(nb)
    assert isvalid(nb)


def test_no_cell_ids():
    """Test that a cell without a cell ID does not pass validation"""
    import nbformat

    with TestsBase.fopen("v4_5_no_cell_id.ipynb", "r") as f:
        # Avoids validate call from `.read`
        nb = nbformat.from_dict(json.load(f))
    with pytest.raises(ValidationError):
        validate(nb, repair_duplicate_cell_ids=False)
    # try again to verify that we didn't modify the content
    with pytest.raises(ValidationError):
        validate(nb, repair_duplicate_cell_ids=False)


def test_repair_no_cell_ids():
    """Test that we will repair cells without ids if asked during validation"""
    import nbformat

    with TestsBase.fopen("v4_5_no_cell_id.ipynb", "r") as f:
        # Avoids validate call from `.read`
        nb = nbformat.from_dict(json.load(f))
    validate(nb)
    assert isvalid(nb)


def test_invalid_cell_id():
    """Test than an invalid cell id does not pass validation"""
    with TestsBase.fopen("invalid_cell_id.ipynb", "r") as f:
        nb = read(f, as_version=4)
    with pytest.raises(ValidationError):
        validate(nb)
    assert not isvalid(nb)


def test_notebook_invalid_without_min_version():
    with TestsBase.fopen("no_min_version.ipynb", "r") as f:
        nb = read(f, as_version=4)
    with pytest.raises(ValidationError):
        validate(nb)


def test_notebook_invalid_without_main_version():
    pass


def test_strip_invalid_metadata():
    with TestsBase.fopen("v4_5_invalid_metadata.ipynb", "r") as f:
        nb = nbformat.from_dict(json.load(f))
    assert not isvalid(nb)
    validate(nb, strip_invalid_metadata=True)
    assert isvalid(nb)

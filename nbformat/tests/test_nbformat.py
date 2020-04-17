import pytest

from nbformat import read


def test_read_invalid_iowrapper(tmpdir):
    config_filepath = tmpdir.join("empty.ipynb")
    config_filepath.write("{}")

    with pytest.raises(AttributeError) as excinfo:
        with open(config_filepath) as fp:
            read(fp, as_version=4)
    assert "cells" in str(excinfo.value)


def test_read_invalid_filepath(tmpdir):
    config_filepath = tmpdir.join("empty.ipynb")
    config_filepath.write("{}")

    with pytest.raises(AttributeError) as excinfo:
        read(str(config_filepath), as_version=4)
    assert "cells" in str(excinfo.value)


def test_read_invalid_pathlikeobj(tmpdir):
    config_filepath = tmpdir.join("empty.ipynb")
    config_filepath.write("{}")

    with pytest.raises(AttributeError) as excinfo:
        read(config_filepath, as_version=4)
    assert "cells" in str(excinfo.value)


def test_read_invalid_str(tmpdir):
    with pytest.raises(OSError) as excinfo:
        read("not_exist_path", as_version=4)
    assert "No such file or directory" in str(excinfo.value)


def test_read_invalid_type(tmpdir):
    with pytest.raises(OSError) as excinfo:
        read(123, as_version=4)
    assert "Bad file descriptor" in str(excinfo.value)

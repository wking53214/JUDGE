import json

import pytest

from judge.cli import _no_repeated_keys


def test_a_repeated_key_is_refused():
    with pytest.raises(ValueError):
        json.loads('{"a": 1, "a": 2}', object_pairs_hook=_no_repeated_keys)


def test_distinct_keys_still_load():
    assert json.loads('{"a": 1, "b": 2}', object_pairs_hook=_no_repeated_keys) == {"a": 1, "b": 2}

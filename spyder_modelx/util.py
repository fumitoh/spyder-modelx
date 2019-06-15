# -*- coding: utf-8 -*-

# Copyright (c) 2018-2019 Fumito Hamamura <fumito.ham@gmail.com>

# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation version 3.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import json

# Code below modified from
# https://stackoverflow.com/questions/15721363/preserve-python-tuples-with-json


class TupleEncoder(json.JSONEncoder):
    """JSON encoder preserving Python tuples"""
    def encode(self, obj):
        return super(TupleEncoder, self).encode(hint_tuples(obj))


def hint_tuples(item):
    if isinstance(item, tuple):
        return {'__tuple__': True, 'items': hint_tuples(list(item))}
    if isinstance(item, list):
        return [hint_tuples(e) for e in item]
    if isinstance(item, dict):
        return {key: hint_tuples(value) for key, value in item.items()}
    else:
        return item


def hinted_tuple_hook(obj):
    if '__tuple__' in obj:
        return tuple(obj['items'])
    else:
        return obj


def test_tuple_encoder():

    sample = (1, 2, '藍上夫', (3, 4.33), [5, 6, (7, 8, [9, 10], 'ABC')])

    enc = TupleEncoder(ensure_ascii=False)
    encoded = enc.encode(sample)
    print(encoded)

    decoded = json.loads(encoded, object_hook=hinted_tuple_hook)
    print("%s == %s" % (sample, decoded))
    assert sample == decoded


if __name__ == "__main__":
    test_tuple_encoder()

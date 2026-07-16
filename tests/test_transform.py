#!/usr/bin/env python3

# Part of the "perky" Python library
# Copyright 2018-2026 by Larry Hastings

import perkytestlib
perkytestlib.preload_local_perky()


import perky.transform
import unittest

class TestTransform(unittest.TestCase):

    def test_RecursiveChainMap(self):
        dict1 = {'a': 1, 'sub': {1: 2, 3:4, 5:6}}
        dict2 = {'b': 2, 'sub': {2: 3, 4:5, 6:7}}
        merged_sub = {a: a+1 for a in range(1, 7)}

        rcm = perky.RecursiveChainMap(dict1, dict2)
        self.assertEqual(rcm['a'], 1)
        self.assertEqual(rcm['b'], 2)

        sub = {n: v for n, v in rcm['sub'].items()}
        self.assertEqual(sub, merged_sub)

    def test_RecursiveChainMap_get_and_del(self):
        # regression: get() used to do `key[self]` (crash), and
        # __delitem__ used to demand a spurious second argument
        # (so `del rcm[key]` raised TypeError).
        rcm = perky.RecursiveChainMap({'a': 1}, {'b': 2})
        self.assertEqual(rcm.get('a'), 1)
        self.assertEqual(rcm.get('missing', 'dflt'), 'dflt')
        with self.assertRaises(KeyError):
            rcm.get('missing')
        del rcm['a']
        self.assertNotIn('a', rcm)
        with self.assertRaises(KeyError):
            rcm['a']

    def test_merge_one_dict(self):
        dict1 = {'a': 1, 'b': 2}
        d = perky.merge_dicts(dict1)

        self.assertEqual(d, dict1)

    def test_merge_two_simple_dicts(self):
        # (this test used to call merge_dicts() with no arguments
        # and assert nothing)
        dict1 = {'a': 1, 'b': 2}
        dict2 = {'c': 3}
        d = perky.merge_dicts(dict1, dict2)
        self.assertEqual(d, {'a': 1, 'b': 2, 'c': 3})

    def test_merge_two_dicts(self):
        dict1 = {'a': 1, 'sub': {1: 2, 3:4, 5:6}}
        dict2 = {'b': 2, 'sub': {2: 3, 4:5, 6:7}}
        merged_sub = {a: a+1 for a in range(1, 7)}

        d = perky.merge_dicts(dict1, dict2)
        d2 = dict(dict1)
        d2.update(dict2)
        d2['sub'] = merged_sub
        self.assertEqual(d, d2)

    def test_transform_dict(self):
        o = {'a': '3', 'b': '5.0', 'c': ['1', '2', 'None', '3'], 'd': {'e': 'f', 'g': 'True'}}
        schema = {'a': int, 'b': float, 'c': [perky.nullable(int)], 'd': {'e': str, 'g': perky.const}}
        test_func = perky.transform(o, schema)
        expected_dict = {'a': 3, 'b': 5.0, 'c': [1, 2, None, 3], 'd': {'e': 'f', 'g': True}}
        self.assertEqual(expected_dict, test_func)

    def test_transform_type_mismatch(self):
        o = {'a': '3', 'b': '5.0', 'c': ['1', '2', 'None', '3'], 'd': {'e': 'f', 'g': 'True'}}
        schema = [{'a': int, 'b': float, 'c': [perky.nullable(int)], 'd': {'e': str, 'g': perky.const}}]
        with self.assertRaises(perky.PerkyFormatError):
            perky.transform(o, schema)

    def test_transform_bad_obj(self):
        o2 = {'a': '44'}
        schema = [{'a': int, 'b': float, 'c': [perky.nullable(int)], 'd': {'e': str, 'g': perky.const}}]
        with self.assertRaises(perky.PerkyFormatError):
            perky.transform(o2, schema)

    def test_transform_none(self):
        o = None
        schema = {'a': int, 'b': float, 'c': [perky.nullable(int)], 'd': {'e': str, 'g': perky.const}}
        with self.assertRaises(perky.PerkyFormatError):
            perky.transform(o, schema)

    def test_RecursiveChainMap_mapping_protocol(self):
        rcm = perky.RecursiveChainMap({'a': 1, 'sub': {'x': 'y'}}, {'b': 2})

        # repr just has to work
        self.assertIn('RecursiveChainMap', repr(rcm))

        # setting a key stores it (and shadows the underlying dicts)
        rcm['a'] = 100
        self.assertEqual(rcm['a'], 100)

        # setting a previously deleted key resurrects it
        del rcm['b']
        self.assertNotIn('b', rcm)
        rcm['b'] = 200
        self.assertEqual(rcm['b'], 200)
        self.assertIn('b', rcm)

        # deleting an already-deleted key raises KeyError
        del rcm['a']
        with self.assertRaises(KeyError):
            del rcm['a']

        # len and iteration see the union of the maps, minus deletes
        rcm2 = perky.RecursiveChainMap({'a': 1, 'b': 2}, {'c': 3})
        self.assertEqual(len(rcm2), 3)
        self.assertEqual(set(rcm2), {'a', 'b', 'c'})
        self.assertEqual(set(rcm2.keys()), {'a', 'b', 'c'})
        self.assertEqual(set(rcm2.values()), {1, 2, 3})
        self.assertEqual(dict(rcm2.items()), {'a': 1, 'b': 2, 'c': 3})
        del rcm2['b']
        self.assertEqual(len(rcm2), 2)
        self.assertEqual(set(rcm2), {'a', 'c'})

        # get() with a present key returns the value
        self.assertEqual(rcm2.get('a'), 1)
        # a missing key raises KeyError on indexing
        with self.assertRaises(KeyError):
            rcm2['nonesuch']

    def test_RecursiveChainMap_bool(self):
        # no deletes: truthiness is "are there any maps with keys"
        self.assertFalse(bool(perky.RecursiveChainMap()))
        self.assertTrue(bool(perky.RecursiveChainMap({'a': 1})))

        # with deletes: true while undeleted keys remain
        rcm = perky.RecursiveChainMap({'a': 1, 'b': 2})
        del rcm['a']
        self.assertTrue(bool(rcm))

        # ...and false when every key has been deleted.
        # (regression: __bool__ used to fall off the end and return
        # None here, so bool() raised TypeError.)
        del rcm['b']
        self.assertFalse(bool(rcm))

    def test_map(self):
        double = lambda o: o * 2
        # scalars, lists, and dicts, recursively
        self.assertEqual(perky.map(3, double), 6)
        self.assertEqual(perky.map([1, 2, [3]], double), [2, 4, [6]])
        self.assertEqual(
            perky.map({'a': 1, 'b': {'c': 2}, 'd': [3]}, double),
            {'a': 2, 'b': {'c': 4}, 'd': [6]})

    def test_transform_with_default(self):
        # keys the schema doesn't mention go through the default
        o = {'a': '3', 'unlisted': '5'}
        schema = {'a': int}
        result = perky.transform(o, schema, default=float)
        self.assertEqual(result, {'a': 3, 'unlisted': 5.0})

    def test_transform_default_must_be_callable(self):
        with self.assertRaises(perky.PerkyFormatError):
            perky.transform({'a': '1'}, {'a': int}, default='not callable')

    def test_transform_bad_schema_value(self):
        # schema values must be dict, list, or callable
        with self.assertRaises(perky.PerkyFormatError):
            perky.transform({'a': '1'}, {'a': 42})

    def test_const(self):
        self.assertIs(perky.const('None'), None)
        self.assertIs(perky.const('True'), True)
        self.assertIs(perky.const('False'), False)
        with self.assertRaises(KeyError):
            perky.const('maybe')

    def test_nullable(self):
        fn = perky.nullable(int)
        self.assertEqual(fn('42'), 42)
        self.assertIs(fn('None'), None)

    def test_required_all_specified(self):
        required = perky.Required()
        schema = {
            'a': required(int),
            'sub': {'b': required(str)},
            'lst': [required(float)],
            }
        required.annotate(schema)
        o = {'a': '1', 'sub': {'b': 'x'}, 'lst': ['1.5', '2.5']}
        result = perky.transform(o, schema)
        self.assertEqual(result, {'a': 1, 'sub': {'b': 'x'}, 'lst': [1.5, 2.5]})
        required.verify()      # everything was specified: no complaint

    def test_required_unspecified(self):
        required = perky.Required()
        schema = {
            'a': required(int),
            'sub': {'b': required(str)},
            }
        required.annotate(schema)
        o = {'a': '1', 'sub': {}}      # sub.b never appears
        perky.transform(o, schema)
        with self.assertRaises(Exception) as cm:
            required.verify()
        # the exception names the missing value by its breadcrumb
        self.assertIn('sub{b}', str(cm.exception))
        self.assertIn('sub{b}', repr(cm.exception))

    def test_required_annotate_bad_schema(self):
        required = perky.Required()
        with self.assertRaises(perky.PerkyFormatError):
            required.annotate({'a': 42})


if __name__ == '__main__': # pragma: nocover
    unittest.main()

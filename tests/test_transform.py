#!/usr/bin/env python3

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

    def test_merge_one_dict(self):
        dict1 = {'a': 1, 'b': 2}
        d = perky.merge_dicts(dict1)

        self.assertEqual(d, dict1)

    def test_merge_two_simple_dicts(self):
        dict1 = {'a': 1, 'b': 2}
        dict2 = {'c': 3}
        d = perky.merge_dicts()

    def test_merge_two_dicts(self):
        dict1 = {'a': 1, 'sub': {1: 2, 3:4, 5:6}}
        dict2 = {'b': 2, 'sub': {2: 3, 4:5, 6:7}}
        merged_sub = {a: a+1 for a in range(1, 7)}

        d = perky.merge_dicts(dict1, dict2)
        d2 = dict(dict1)
        d2.update(dict2)
        d2['sub'] = merged_sub
        self.assertEqual(d, d2)

if __name__ == '__main__': # pragma: nocover
    unittest.main()

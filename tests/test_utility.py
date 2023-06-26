#!/usr/bin/env python3

import perkytestlib
perkytestlib.preload_local_perky()

import perky
import unittest


class TestUtility(unittest.TestCase):

    def test_merge_nothin(self):
        o = perky.merge_dicts_and_lists()
        self.assertIsNone(o)

    def test_merge_one_dict(self):
        dict1 = {'a': 1, 'b': 2}
        d = perky.merge_dicts_and_lists(dict1)

        self.assertEqual(d, dict1)

    def test_merge_one_list(self):
        l = [1, 2, 'c', 4]
        l2 = perky.merge_dicts_and_lists(l)

        self.assertEqual(l, l2)

    def test_merge_two_simple_dicts(self):
        dict1 = {'a': 1, 'b': 2}
        dict2 = {'c': 3}
        d = perky.merge_dicts_and_lists(dict1, dict2)
        manually_merged = dict(dict1)
        manually_merged.update(dict2)
        self.assertEqual(d, manually_merged)

    def test_merge_two_nested_dicts(self):
        dict1 = {'a': 1, 'sub': {1:2, 3:4, 5:6}}
        dict2 = {'b': 2, 'sub': {2:3, 4:5, 6:7}}
        d = perky.merge_dicts_and_lists(dict1, dict2)

        d2 = dict(dict1)
        d2.update(dict2)
        d2['sub'] = {a: a+1 for a in range(1, 7)}
        self.assertEqual(d, d2)

    def test_complex_merge_two_nested_dicts(self):
        dict1 = {'a': 1, 'sub': {1:2, 3:4, 5:6}}
        dict2 = {'b': 2, 'sub': {2:3, 4:5, 6:7}, 'l': [1, 2, 3]}
        dict3 = {'c': 3}
        dict4 = {'a': 5, 'd': 4, 'sub': {7:8, 8:9, 9:10}, 'l': [4, 5, 6]}
        d = perky.merge_dicts_and_lists(dict1, dict2, dict3, dict4)

        d2 = dict(dict1)
        d2.update(dict2)
        d2.update(dict3)
        d2.update(dict4)
        d2['sub'] = {a: a+1 for a in range(1, 10)}
        d2['l'] = list(range(1, 7))
        self.assertEqual(d, d2)


if __name__ == '__main__': # pragma: nocover
    unittest.main()


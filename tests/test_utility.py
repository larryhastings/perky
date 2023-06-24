#!/usr/bin/env python3


def preload_local_perky():
    """
    Pre-load the local "perky" module, to preclude finding
    an already-installed one on the path.
    """
    import pathlib
    import sys

    argv_0 = pathlib.Path(sys.argv[0])
    perky_dir = argv_0.resolve().parent
    while True:
        perky_init = perky_dir / "perky" / "__init__.py"
        if perky_init.is_file():
            break
        perky_dir = perky_dir.parent

    # this almost certainly *is* a git checkout
    # ... but that's not required, so don't assert it.
    # assert (perky_dir / ".git" / "config").is_file()

    if perky_dir not in sys.path:
        sys.path.insert(1, str(perky_dir))

    import perky
    assert perky.__file__.startswith(str(perky_dir))
    return perky_dir

import perky.utility



import unittest

dict1 = {'a': 1, 'sub': {1: 2, 3:4, 5:6}}
dict2 = {'b': 2, 'sub': {2: 3, 4:5, 6:7}}
merged_sub = {a: a+1 for a in range(1, 7)}

class TestUtility(unittest.TestCase):

    def test_RecursiveChainMap(self):
        rcm = perky.utility.RecursiveChainMap(dict1, dict2)
        self.assertEqual(rcm['a'], 1)
        self.assertEqual(rcm['b'], 2)

        sub = {n: v for n, v in rcm['sub'].items()}
        self.assertEqual(sub, merged_sub)

    def test_merge_dicts(self):
        d = perky.utility.merge_dicts(dict1, dict2)
        d2 = dict(dict1)
        d2.update(dict2)
        d2['sub'] = merged_sub
        self.assertEqual(d, d2)

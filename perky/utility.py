#!/usr/bin/env python3
#
# Part of the "perky" Python library
# Copyright 2018-2021 by Larry Hastings

import os


class RecursiveChainMap(dict):

    def __init__(self, *dicts):
        self.cache = {}
        self.maps = [self.cache]
        self.maps.extend(dicts)
        self.deletes = set()

    def __missing__(self, key):
        raise KeyError(key)

    def __getitem__(self, key):
        if key in self.deletes:
            raise self.__missing__(key)

        submaps = []
        for map in self.maps:
            try:
                # "key in dict" doesn't work with defaultdict!
                value = map[key]
                if isinstance(value, dict):
                    submaps.append(value)
                elif not submaps:
                    return value
            except KeyError:
                continue

        if not submaps:
            raise self.__missing__(key)

        value = RecursiveChainMap(*submaps)
        self.cache[key] = value
        return value

    def __setitem__(self, key, value):
        self.cache[key] = value
        self.deletes.discard(key)

    def __delitem__(self, key, value):
        if key in self.deletes:
            self.__missing__(key)
        self.deletes.add(key)

    __sentinel = object()

    def get(self, key, default=__sentinel):
        if key in self:
            return key[self]
        if default is not __sentinel:
            return default
        raise self.__missing__(key)

    def __len__(self):
        return len(set().union(*self.maps) - self.deletes)

    def __iter__(self):
        return iter(set().union(*self.maps) - self.deletes)

    def __contains__(self, key):
        if key in self.deletes:
            return False
        return any(key in map for map in self.maps)

    def __bool__(self):
        if not self.deletes:
            return any(self.maps)
        for map in self.maps:
            keys = set(map) - self.deletes
            if keys:
                return True


def _merge_dicts(rcm):
    d = {}
    for key in rcm:
        value = rcm[key]
        if isinstance(value, RecursiveChainMap):
            value = _merge_dicts(value)
        d[key] = value
    return d

def merge_dicts(*dicts):
    rcm = RecursiveChainMap(*dicts)
    return _merge_dicts(rcm)


def _mdal_dict(roots):
    for root in roots:
        assert isinstance(root, dict)
    if len(roots) == 1:
        return dict(roots[0])
    d = {}
    roots = list(roots)
    while roots:
        root0 = roots.pop(0)
        for key, value in root0.items():
            if isinstance(value, (dict, list)):
                if key in d:
                    # only merge once!
                    continue
                subroots = [value]
                t = type(value)
                for root in roots:
                    if key not in root:
                        continue
                    value = root[key]
                    assert isinstance(value, t)
                    subroots.append(value)
                if isinstance(value, list):
                    value = _mdal_list(subroots)
                else:
                    value = _mdal_dict(subroots)
            d[key] = value
    return d

def _mdal_list(roots):
    l = []
    for root in roots:
        assert isinstance(root, list)
        l.extend(root)
    return l

def merge_dicts_and_lists(*roots):
    """
    Takes a sequence of homogenous roots
    (either dicts or lists, with the same
    shape of dicts and lists inside).
    Merges all the roots together into a
    single data structure and returns the merged
    result.

    For dicts:
        Non-dict-or-list values are overwritten;
        values from later roots have higher priority.
        Child dicts and lists are recursively merged.
    For lists:
        All lists are concatenated, with later roots
        being appended after earlier roots.

    Values in lists aren't examined, just copied
    over.  This means if a root contains a list
    or a dict inside of a list, the merged result
    will have a reference to that existing dict
    or list.  This could be messy if the shared
    dict or dict is modified.  However, this function
    is only used internally (by pragma_include) and
    this behavior is fine.  (In fact, it's preferable,
    because it's faster, and the old "roots" are always
    thrown away immediately anyway.)
    """
    assert roots
    root0 = roots[0]
    assert isinstance(root0, (dict, list)), f"expected t to be dict or list, was {type(t)}, repr is {t!r}"
    if isinstance(root0, list):
        return _mdal_list(roots)
    return _mdal_dict(roots)


class pushd:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        self.old_path = os.getcwd()
        os.chdir(self.path)

    def __exit__(self, exc_type, exc_value, exc_tb):
        os.chdir(self.old_path)

if __name__ == "__main__":
    dict1 = {'a': 1, 'sub': {1: 2, 3:4, 5:6}}
    dict2 = {'b': 2, 'sub': {2: 3, 4:5, 6:7}}

    rcm = RecursiveChainMap(dict1, dict2)
    print(rcm['a'])
    print(rcm['b'])
    sub = rcm['sub']
    print([(name, sub[name]) for name in range(1, 7)])

    d = merge_dicts(dict1, dict2)
    print(d)

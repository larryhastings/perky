#!/usr/bin/env python3
#
# Part of the "perky" Python library
# Copyright 2018 by Larry Hastings


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

#!/usr/bin/env python3
#
# Part of the "perky" Python library
# Copyright 2018-2023 by Larry Hastings

import os
from collections.abc import Mapping, Sequence


class FormatError(Exception):
    def __init__(self, message, tokens=None, line=None):
        self.message = message
        if tokens:
            self.tokens = ''.join(t[1] for t in tokens)
        else:
            self.tokens = tokens
        self.line = line

    def __strings_for_repr__(self):
        strings = [f"{self.__class__.__name__} {self.message!r}"]
        if self.tokens is not None:
            strings.append(f"tokens={self.tokens!r}")
        if self.line is not None:
            strings.append(f"line={self.line!r}")
        return strings

    def __repr__(self):
        s = " ".join(self.__strings_for_repr__())
        return f"<{s}>"

    def __str__(self):
        return "\n".join(self.__strings_for_repr__())

# old name
PerkyFormatError = FormatError


def raise_if_false(expr, message, tokens, line):
    if not expr:
        raise FormatError(message, tokens, line)


def _merge_dicts_and_lists_recurse_dict(roots):
    sentinel = object()
    for root in roots:
        assert isinstance(root, Mapping)

    d = {}

    # why not just iterate over roots?
    # consider merging this list of root dicts:
    #   [
    #   {'a': 1},
    #   {'b': 2},
    #   {'a': 3, 'nested_dict':{'x': 4}},
    #   ...
    #   ]
    # when merging 'nested_dict', there's no
    # point in iterating over the first two dicts,
    # we already know it didn't appear there.
    roots = list(roots)
    while roots:
        root = roots.pop(0)
        for key, value in root.items():
            is_mapping = Mapping if isinstance(value, Mapping) else False
            is_sequence = Sequence if (isinstance(value, Sequence) and not isinstance(value, str)) else False
            value_type = is_mapping or is_sequence
            if not value_type:
                d[key] = value
                continue

            if key in d:
                # only merge once!
                continue
            subroots = [value]
            for root in roots:
                value = root.get(key, sentinel)
                if value is sentinel:
                    continue
                assert isinstance(value, value_type)
                subroots.append(value)
            if is_mapping:
                value = _merge_dicts_and_lists_recurse_dict(subroots)
            else:
                value = _merge_dicts_and_lists_recurse_list(subroots)
            d[key] = value
    return d

def _merge_dicts_and_lists_recurse_list(roots):
    l = []
    for root in roots:
        assert isinstance(root, Sequence) and not isinstance(root, str)
        l.extend(root)
    return l

def merge_dicts_and_lists(*roots):
    """
    Takes a sequence of homogenous roots
    (either Mapping or Sequence objects, with the same
    shape of Mapping and Sequence objects inside).
    Merges all the roots together into a
    single data structure and returns the merged
    result.

    For Mapping objects:
        Non-Mapping-or-Sequence values are overwritten;
        values from later roots have higher priority.
        Child Mappings and Sequences are recursively merged.
    For Sequence objects:
        All Sequence objects are concatenated, with later
        roots being appended after earlier roots.

    Values in Sequences aren't examined, just copied
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
    if not roots:
        return None

    root0 = roots[0]
    is_sequence = isinstance(root0, Sequence) and not isinstance(root0, str)
    is_mapping = isinstance(root0, Mapping)
    assert is_sequence or is_mapping, f"expected t to be Mapping or Sequence, type of t is {type(t)}, t is {t!r}"

    if len(roots) == 1:
        if is_mapping:
            return dict(root0)
        return list(root0)

    if is_mapping:
        return _merge_dicts_and_lists_recurse_dict(roots)
    return _merge_dicts_and_lists_recurse_list(roots)

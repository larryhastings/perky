#!/usr/bin/env python3
#
# Part of the "perky" Python library
# Copyright 2018-2023 by Larry Hastings

# TODO:
#
# should Perky happily parse this?
#
#     Apple ][ = {
#         bits = 8
#     }
#
# because right now it doesn't.

"""
A simple, Pythonic file format.  Same interface as the
"pickle" module (load, loads, dump, dumps).
"""

# leaving this in is sufficient to meet the binary distribution
# doc requirement
copyright = """
perky
Copyright 2018-2023 by Larry Hastings
All rights reserved.

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

__version__ = "0.9.2"

import ast
from collections.abc import MutableMapping, MutableSequence, Sequence
import os.path
from os.path import isfile, join, normpath
import re
import shlex
import sys
import textwrap
from .tokenize import *
from .utility import *

# the "transform" functions are *all* deprecated.
from .transform import *


__all__ = []

def export(fn):
    __all__.append(fn.__name__)
    return fn


class Parser:

    def __init__(self, s, *, pragmas=None, root=None, source=None):
        if not isinstance(s, str):
            raise TypeError('s must be str, not {type(s)}')
        self.lt = LineTokenizer(s, source=source)
        self.pragmas = pragmas or {}
        self.root = root if root is not None else {}
        self.source = source
        # new name
        self.stack = []
        # old name
        self.breadcrumbs = self.stack

    @property
    def line_number(self):
        return self.lt.line_number

    def _parse_pragma(self, line):
        original_line = line
        # skip the leading '='
        line = line.lstrip()[1:]

        fields = line.split(None, 1)
        pragma = fields[0].lower()
        if len(fields) == 1:
            argument = None
        else:
            argument = fields[1]
            tokens = list(tokenize(pushback_str_iterator(argument)))
            if len(tokens) != 1 or tokens[0][0] != STRING:
                raise PerkyFormatError(f"'{self.source}' line {self.line_number}: Invalid pragma argument {argument}", tokens, original_line)
            argument = tokens[0][1]

        fn = self.pragmas.get(pragma)
        if not fn:
            raise PerkyFormatError(f"'{self.source}' line {self.line_number}: Unknown pragma {pragma}", None, original_line)
        fn(self, argument)

    def _parse_value(self, t):
        tok, value = t
        if tok is LEFT_CURLY_BRACE:
            return self._read_mapping()
        if tok is LEFT_SQUARE_BRACKET:
            return self._read_sequence()
        if (tok is TRIPLE_SINGLE_QUOTE) or (tok is TRIPLE_DOUBLE_QUOTE):
            return self._read_textblock(value)
        if tok is EMPTY_CURLY_BRACES:
            return {}
        if tok is EMPTY_SQUARE_BRACKETS:
            return []
        return value

    def _read_mapping(self, starting_dict=None):
        d = starting_dict if starting_dict is not None else {}
        self.stack.append(d)

        keys_seen = set()

        d_setitem = d.__setitem__
        keys_seen_add = keys_seen.add
        self_parse_value = self._parse_value

        for line_number, line, tokens in self.lt:
            if not tokens:
                # whitespace line
                continue
            token, argument = tokens[0]
            if token is EQUALS:
                self._parse_pragma(line)
                continue
            if len(tokens) == 1:
                if token is RIGHT_CURLY_BRACE:
                    break
                if token is COMMENT:
                    continue

            if not (
                (2 <= len(tokens) <= 3)
                and (tokens[0][0] is STRING)
                and (tokens[1][0] is EQUALS)
                ):
                raise FormatError(
                    "Invalid token sequence: in mapping, expected STRING = or STRING == VALUE or }",
                    tokens, line)

            key = tokens[0][1]
            if key in keys_seen:
                raise FormatError(
                    f"Invalid Perky mapping: repeated key {key!r}",
                    tokens, line)
            keys_seen_add(key)
            if len(tokens) == 3:
                value = self_parse_value(tokens[2])
            else:
                value = ""
            # d[key] = value
            d_setitem(key, value)

        self.stack.pop()
        return d

    def _read_sequence(self, starting_list=None):
        l = starting_list if starting_list is not None else []
        l_append = l.append
        self_parse_value = self._parse_value
        self.stack.append(l)
        for line_number, line, tokens in self.lt:
            if not tokens:
                # blank line
                continue
            token, argument = tokens[0]
            if token is EQUALS:
                self._parse_pragma(line)
                continue
            if len(tokens) != 1:
                raise FormatError(
                    "Invalid token sequence: in sequence, expected one token",
                    tokens, line)
            if token is RIGHT_SQUARE_BRACKET:
                break
            if token is COMMENT:
                continue
            value = self_parse_value(tokens[0])
            l_append(value)
        self.stack.pop()
        return l

    def _read_textblock(self, marker):
        l = []
        l_append = l.append
        lt = self.lt
        next_line = self.lt.next_line
        while lt:
            line_number, line = next_line()
            line = line.rstrip()
            stripped = line.lstrip()
            if stripped == marker:
                break
            l_append(line)

        prefix = line.partition(stripped)[0]
        l2 = []
        l2_append = l2.append
        len_prefix = len(prefix)
        if prefix:
            # detect this error:
            #    a = '''
            #       outdenting sure is fun!
            #          '''
            for line in l:
                # line must either be empty or start with our prefix
                if line and (not line.startswith(prefix)):
                    raise FormatError(
                        "Format error: malformed line triple-quoted block",
                        None, line)
                line2 = line[len_prefix:]
                l2_append(line2)

        return "\n".join(l2)

    def parse(self):
        if isinstance(self.root, MutableMapping):
            return self._read_mapping(self.root)
        if isinstance(self.root, MutableSequence):
            return self._read_sequence(self.root)
        raise TypeError(f"root {self.root} is neither MutableMapping nor MutableSequence, don't know how to fill it")


class Serializer:
    def __init__(self, prefix="    "):
        self.prefix = prefix
        self.reset()

    def reset(self):
        self.indent = 0
        self.lines = []
        self.line = ''

    def dumps(self):
        s =  "\n".join(self.lines) + "\n"
        self.reset()
        return s

    def newline(self, s):
        line = self.line
        self.line = ''
        if s:
            line = line + s
        if self.indent:
            line = (self.indent * self.prefix) + line
        self.lines.append(line)

    @staticmethod
    def quoted_string(s):
        single = "'"
        double = '"'
        must_quote = (
            (s.strip() != s)
            or (s.startswith((single, double)))
            or any(c in s for c in non_quoting_operators) # non_quoting_operators is in tokenize
            or ("\n" in s)
            or ("\t" in s)
            )
        if not must_quote:
            return s

        # use the quote that will result in fewer escaped quote marks
        # (prefer double quotes)
        if len(s.split(double)) <= len(s.split(single)):
            quote = double
        else:
            quote = single

        for bad, good in (
            ("\\", "\\\\"),
            ("\t", "\\t"),
            ("\n", "\\n"),
            (quote, "\\" + quote),
            ):
            s = s.replace(bad, good)
        return quote + s + quote

    def serialize(self, d):
        for name, value in d.items():
            if not isinstance(name, str):
                raise TypeError(f"keys in Perky dicts must always be strings, not {name!r}")
            self.line = self.quoted_string(name) + " = "
            self.serialize_value(value)

    def serialize_dict(self, value):
        self.newline("{")
        self.indent += 1
        self.serialize(value)
        self.newline("}")
        self.indent -= 1

    def serialize_list(self, l):
        self.newline("[")
        self.indent += 1
        for value in l:
            self.serialize_value(value)
        self.newline("]")
        self.indent -= 1

    def serialize_quoted_string(self, s):
        self.newline(self.quoted_string(s))

    def serialize_textblock(self, s):
        self.newline('"""')
        self.indent += 1
        for line in s.split("\n"):
            self.newline(line)
        self.newline('"""')
        self.indent -= 1

    def serialize_value(self, value):
        if isinstance(value, MutableMapping):
            return self.serialize_dict(value)
        if isinstance(value, MutableSequence):
            return self.serialize_list(value)

        if isinstance(value, bytes):
            raise TypeError(f"Perky can't serialize bytes value {value!r}, please decode to str")

        if not isinstance(value, str):
            value = str(value)
        if '\n' in value:
            return self.serialize_textblock(value)
        if (value == value.strip()) and "".join(value.split()).isalnum():
            self.newline(value)
            return
        return self.serialize_quoted_string(value)


@export
def loads(s, *, pragmas=None, root=None, source="<string>"):
    p = Parser(s, pragmas=pragmas, root=root)
    d = p.parse()
    return d

@export
def load(filename, *, pragmas=None, root=None):
    with open(filename, "rt", encoding="utf-8") as f:
        text = f.read()
    p = Parser(text, pragmas=pragmas, root=root, source=filename)
    d = p.parse()
    return d

@export
def dumps(d):
    s = Serializer()
    s.serialize(d)
    return s.dumps()


@export
def dump(filename, d):
    text = dumps(d)
    with open(filename, "wt", encoding="utf-8") as f:
        f.write(text)


@export
def pragma_include(include_path=(".",)):
    include_path_ok = (
        isinstance(include_path, Sequence)
        and (not isinstance(include_path, str))
        and all(isinstance(s, str) for s in include_path)
        )
    if not include_path_ok:
        raise TypeError(f"include_path must be a sequence of strings, not {include_path!r}")

    include_path = tuple(include_path)

    def pragma_include(parser, filename):
        leaf = parser.stack[-1]
        leaf_is_mapping = isinstance(leaf, Mapping)
        included_root = {} if leaf_is_mapping else []

        for directory in include_path:
            path = normpath(join(directory, filename))
            if isfile(path):
                break
        else:
            raise FileNotFoundError(filename)

        load(path, pragmas=parser.pragmas, root=included_root)
        if leaf_is_mapping:
            # we can't just leaf.update(loaded_root),
            # we have to do this recursively.
            merged = merge_dicts_and_lists(leaf, included_root)
            leaf.clear()
            leaf.update(merged)
        else:
            leaf.extend(included_root)

    return pragma_include

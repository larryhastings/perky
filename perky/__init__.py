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

# YOU NEED more TESTS THAT TEST dump()
#
# inside dicts (and similarly without "value =" inside lists)
#
# what if ''' or """ appears inside the triple-quoted string?
#
# turn if 0 module-level tests into real tests, dude
#
# explicit fns for xform schema vs function
#  * need betterer names
#
# More library utility functions to manage
# perky dict/lists:
# * recursive "chain map"
# * recursive merge
#
# Ensure you can use multiple Required objects
# with the same function (e.g. "int")
#
# transform exceptions should print a breadcrumb
# trail so we know where the erroneous value lives

# TESTS NEEDED:
#
# make sure a quoted # works as a key
#
# ensure that unquoted string names can contain
#   [ { ''' """ #
# and unquoted string values can contain all those AND
#   =

# DONE
#
# this should fail:
#    a = '''
#       outdenting is fun
#          '''
#
# allow
#     value = []
#     value = [ ]
#     value = {}
#     value = { }
#
# pragma parser:
#  * handle quoted argument, e.g. =include " file starting with space.h"
#  * reserve all other perky syntax features, complain if they are used
#      * """ and '''
#      * {
#      * [
#
# add pragmas parameter to load / loads
#     {"prefix": fn(d, suffix)}
# prefix can be None in which case it's called for every comment line, first
#   fn is called with current dict and the rest of the line after whitespace
#     e.g.
#     load(filename, {"include": includify })
#   if filename contains the line
#     #include foo.txt
#   we'll call
#     includify(d, "foo.txt")
#
#   * idea for pragma: allow it to be a dict entry?
#     #include = filename
#     #include = [
#          ...
#          ]
#     I think this is maybe kinda icky.
#
# ALLOW EMPTY KEYS
#       foo =
# is currently an error, it should be an empty string
#
# Per-line callback function (for #include)
#   * and, naturally, an example callback function
#     for you to use (aka "#include")
#

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


__version__ = "0.8"

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

    def __init__(self, s, *, pragmas=None, encoding='utf-8', root=None):
        if not isinstance(s, str):
            raise TypeError('s must be str, not {type(s)}')
        self.lt = LineTokenizer(s)
        self.pragmas = pragmas or {}
        self.encoding = encoding
        self.root = root if root is not None else {}
        self.breadcrumbs = []

    def _parse_pragma(self, line):
        original_line = line
        line = line.strip()
        assert line[0] == '='
        line = line[1:].strip()

        fields = line.split(None, 1)
        pragma = fields[0].lower()
        if len(fields) == 1:
            argument = None
        else:
            argument = fields[1]
            tokens = list(tokenize(argument))
            if len(tokens) != 1 or tokens[0][0] != STRING:
                raise PerkyFormatError(f"Line {self.lt.line_number}: Invalid pragma argument {argument}", tokens, original_line)
            argument = tokens[0][1]

        fn = self.pragmas.get(pragma)
        if not fn:
            raise PerkyFormatError(f"Line {self.lt.line_number}: Unknown pragma {pragma}", None, original_line)
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
        self.breadcrumbs.append(d)

        keys_seen = set()

        for line_number, line, tokens in self.lt:
            if not tokens:
                # whitespace line
                continue
            token, argument = tokens[0]
            if token is EQUALS:
                self._parse_pragma(line)
                continue
            if len(tokens) == 1:
                token, argument = tokens[0]
                if token is RIGHT_CURLY_BRACE:
                    break
                if token is COMMENT:
                    continue
            tokens = [t for t in tokens if t[0] is not WHITESPACE]

            raise_if_false(
                (2 <= len(tokens) <= 3) and tokens[0][0] is STRING and tokens[1][0] is EQUALS,
                "Invalid token sequence: in mapping, expected STRING = or STRING == VALUE or }",
                tokens, line)
            key = tokens[0][1].strip()
            raise_if_false(
                key not in keys_seen,
                f"Invalid Perky mapping: repeated key {key!r}",
                tokens, line)
            keys_seen.add(key)
            if len(tokens) == 3:
                value = self._parse_value(tokens[2])
            else:
                value = ""
            d[key] = value

        self.breadcrumbs.pop()
        return d

    def _read_sequence(self, starting_list=None):
        l = starting_list if starting_list is not None else []
        self.breadcrumbs.append(l)
        for line_number, line, tokens in self.lt:
            if not tokens:
                # blank line
                continue
            token, argument = tokens[0]
            if token is EQUALS:
                self._parse_pragma(line)
                continue
            raise_if_false(
                len(tokens) == 1,
                "Invalid token sequence: in sequence, expected one token",
                tokens, line)
            token, argument = tokens[0]
            if token is RIGHT_SQUARE_BRACKET:
                break
            if token is COMMENT:
                continue
            value = self._parse_value(tokens[0])
            l.append(value)
        self.breadcrumbs.pop()
        return l

    def _read_textblock(self, marker):
        l = []
        while self.lt:
            line_number, line = self.lt.next_line()
            line = line.rstrip()
            stripped = line.lstrip()
            if stripped == marker:
                break
            l.append(line)

        prefix = line.partition(stripped)[0]
        if prefix:
            # detect this error:
            #    a = '''
            #       outdenting sure is fun!
            #          '''
            for line in l:
                raise_if_false(
                    # line must either be empty or start with our prefix
                    (not line) or line.startswith(prefix),
                    "Format error: malformed line triple-quoted block",
                    None, line)

        s = "\n".join(line for line in l)
        # this one line does all the
        # heavy lifting in textwrap.dedent()
        s = re.sub(r'(?m)^' + prefix, '', s)
        return s

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
                raise TypeError("keys in Perky dicts must always be strings")
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
            raise TypeError("Perky can't serialize bytes values, please decode to str")

        if not isinstance(value, str):
            value = repr(value)
        if '\n' in value:
            return self.serialize_textblock(value)
        if value == value.strip() and "".join(value.split()).isalnum():
            self.newline(value)
            return
        return self.serialize_quoted_string(value)


@export
def loads(s, *, pragmas=None, encoding='utf-8', root=None):
    p = Parser(s, pragmas=pragmas, encoding=encoding, root=root)
    d = p.parse()
    return d

@export
def dumps(d):
    s = Serializer()
    s.serialize(d)
    return s.dumps()


@export
def load(filename, *, pragmas=None, encoding="utf-8", root=None):
    with open(filename, "rt", encoding=encoding) as f:
        return loads(f.read(), pragmas=pragmas, encoding=encoding, root=root)

@export
def dump(filename, d, *, encoding="utf-8"):
    s = Serializer()
    s.serialize(d)
    with open(filename, "wt", encoding=encoding) as f:
        f.write(s.dumps())


@export
def pragma_include(include_path=(".",)):
    assert isinstance(include_path, Sequence)
    assert not isinstance(include_path, str)
    assert all(isinstance(s, str) for s in include_path)
    include_path = tuple(include_path)
    def pragma_include(parser, filename):
        leaf = parser.breadcrumbs[-1]
        leaf_is_list = isinstance(parser.breadcrumbs[-1], list)
        subroot = [] if leaf_is_list else {}
        for directory in include_path:
            path = normpath(join(directory, filename))
            if isfile(path):
                break
        else:
            raise FileNotFoundError(filename)
        load(path, pragmas=parser.pragmas, encoding=parser.encoding, root=subroot)
        merged = merge_dicts_and_lists(leaf, subroot)
        # print(f"\n\nXXX merge_dicts_and_lists({leaf=}, {subroot=}) -> {merged=}\n\n")
        leaf.clear()
        if isinstance(leaf, list):
            leaf.extend(merged)
        else:
            leaf.update(merged)
    return pragma_include

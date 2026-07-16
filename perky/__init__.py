#!/usr/bin/env python3
#
# Part of the "perky" Python library
# Copyright 2018-2026 by Larry Hastings

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
A simple, Pythonic file format.  Provides load, loads, dump, and
dumps, like the json and pickle modules.

Note one difference from json and pickle: perky.dump takes the
filename *first*, then the object--perky.dump(filename, d).  (Both
json.dump and pickle.dump take the object first, and a file object
rather than a filename.)
"""

# leaving this in is sufficient to meet the binary distribution
# doc requirement
copyright = """
perky
Copyright 2018-2026 by Larry Hastings
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

__version__ = "0.10"

import ast
from big.types import string as big_string
from collections.abc import MutableMapping, MutableSequence, Sequence
import os.path
from os.path import abspath, commonpath, isfile, join, normpath
import pathlib
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
            raise TypeError(f's must be str, not {type(s)}')

        # If s is a big.string, Perky parses *with provenance*:
        # every parsed str value comes back as a big.string slice
        # that knows its own source, line, and column, and error
        # messages know the line, column, and source of the problem
        # and show the offending line with a caret pointing at the
        # trouble.
        #
        # If s is a plain str, Perky parses at full speed and the
        # parsed values are plain strs, same as always.  (loads and
        # load still produce rich error messages for plain strs--if
        # parsing fails, they re-parse with provenance to generate
        # the good error.  Parsing is deterministic, and the error
        # path is not the fast path.)
        if (source is not None) and (not isinstance(source, str)):
            source = str(source)

        if isinstance(s, big_string) and s.source and (source in (None, '<string>')):
            # a big.string already knows its source; prefer it,
            # unless the caller explicitly specified another one
            source = s.source

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

    def _format_error(self, message, tokens=None, line=None, anchor=None):
        # Builds (but doesn't raise) a FormatError.
        #
        # anchor should be the string object closest to the trouble--
        # a token value if the problem is one token, or the whole
        # line.  If anchor has provenance, the error message gets
        # the source, line, *and column* of the trouble, plus the
        # offending line itself with a caret pointing at the anchor.
        if anchor is None:
            anchor = line
        where = getattr(anchor, 'where', None)
        if where is None:
            prefix = f"'{self.source}' line {self.line_number}"
        else:
            prefix = where
        text = f"{prefix}: {message}"
        context = getattr(anchor, 'context', None)
        if context:
            text = f"{text}\n{context}"
        return FormatError(text, tokens, line)

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
            tokens = list(tokenize(argument))
            if len(tokens) != 1 or tokens[0][0] != STRING:
                raise self._format_error(f"Invalid pragma argument {argument}", tokens, original_line, anchor=argument)
            argument = tokens[0][1]

        fn = self.pragmas.get(pragma)
        if not fn:
            raise self._format_error(f"Unknown pragma {pragma}", None, original_line, anchor=pragma)
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
                raise self._format_error(
                    "Invalid token sequence: in mapping, expected STRING = or STRING == VALUE or }",
                    tokens, line)

            key = tokens[0][1]
            if key in keys_seen:
                raise self._format_error(
                    f"Invalid Perky mapping: repeated key {str(key)!r}",
                    tokens, line, anchor=key)
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
                raise self._format_error(
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
        line = None
        stripped = None
        found = False
        while lt:
            line_number, line = next_line()
            line = line.rstrip()
            stripped = line.lstrip()
            if stripped == marker:
                found = True
                break
            l_append(line)

        if not found:
            # ran off the end of the file without a closing marker line.
            # anchor on the *opening* marker--the trouble is that this
            # block, opened here, never closed.
            raise self._format_error(
                f"unterminated triple-quoted block (expected a closing {str(marker)!r} line)",
                None, None, anchor=marker)

        prefix = line.partition(stripped)[0]
        if not prefix:
            # closing marker is at column 0: nothing to outdent,
            # the lines are the content, verbatim.
            # (this used to return "" -- the whole block's content,
            # silently thrown away!)
            return "\n".join(l)

        l2 = []
        l2_append = l2.append
        len_prefix = len(prefix)
        # detect this error:
        #    a = '''
        #       outdenting sure is fun!
        #          '''
        for line in l:
            # line must either be empty or start with our prefix
            if line and (not line.startswith(prefix)):
                raise self._format_error(
                    "malformed line in triple-quoted block (not indented as deep as the closing marker)",
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
    """
    Parses a string containing Perky text, returning the root object.

    Error messages always know the source, line, and column of the
    problem, and show the offending line with a caret pointing at
    the trouble.

    The *type* of s decides whether the parsed values carry
    provenance.  If s is a big.string, every str value in the
    parsed result is a big.string that knows its own source, line,
    and column--which means your *own* error messages can point
    into the config file too: if a value fails validation, its
    .where attribute is the location to blame.  If s is a plain
    str, the parsed values are plain strs, and parsing runs at
    full speed.
    """
    if isinstance(s, big_string):
        p = Parser(s, pragmas=pragmas, root=root, source=source)
        return p.parse()

    # fast path: parse the plain str at full speed.
    try:
        p = Parser(s, pragmas=pragmas, root=root, source=source)
        return p.parse()
    except (FormatError, ValueError):
        if pragmas or (root is not None):
            # re-parsing would re-run pragma side effects, or
            # double-fill the caller's root.  they get the
            # plain error, which still knows the line number.
            raise
        # cold path: the text has an error in it.  re-parse with
        # provenance, purely to raise a better error message--one
        # that knows the column and points a caret at the trouble.
        # parsing is deterministic, so this raises the same error,
        # in the rich format.
        p = Parser(big_string(s, source=source), source=source)
        p.parse()
        raise  # pragma: nocover -- the re-parse always raises

@export
def load(filename, *, pragmas=None, root=None):
    """
    Parses the Perky file at filename, returning the root object.

    Error messages always know the file, line, and column of the
    problem, and show the offending line with a caret pointing at
    the trouble.

    load always parses with provenance: every str value in the
    parsed result is a big.string that knows its own file, line,
    and column--which means your *own* error messages can point
    into the config file too: if a value fails validation, its
    .where attribute is the location to blame.

    If you don't want provenance, read the file yourself and pass
    a plain str to loads:

        with open(filename, "rt", encoding="utf-8") as f:
            config = perky.loads(f.read())
    """
    with open(filename, "rt", encoding="utf-8") as f:
        text = f.read()
    text = big_string(text, source=str(filename))
    return loads(text, pragmas=pragmas, root=root, source=str(filename))

@export
def dumps(d):
    s = Serializer()
    if isinstance(d, MutableMapping):
        s.serialize(d)
    elif isinstance(d, MutableSequence):
        # a top-level sequence: like a top-level mapping, it has no
        # enclosing brackets--just its values, one per line.  (This
        # mirrors load/loads, which already accept root=[].)
        for value in d:
            s.serialize_value(value)
    else:
        raise TypeError(
            f"the top level of a Perky document must be a mapping or a sequence, not {type(d).__name__}")
    return s.dumps()


@export
def dump(filename, d):
    text = dumps(d)
    with open(filename, "wt", encoding="utf-8") as f:
        f.write(text)


@export
def pragma_include(include_path=(".",), jail=False):
    Path = pathlib.Path
    include_path_ok = (
        isinstance(include_path, Sequence)
        and (not isinstance(include_path, str))
        and all(isinstance(s, (str, Path)) for s in include_path)
        )
    if not include_path_ok:
        raise TypeError(f"include_path must be a sequence of strings or pathlib.Path objects, not {include_path!r}")

    include_path = tuple(abspath(normpath(d)) for d in include_path)

    def pragma_include(parser, filename):
        leaf = parser.stack[-1]
        leaf_is_mapping = isinstance(leaf, Mapping)
        included_root = {} if leaf_is_mapping else []

        for directory in include_path:
            path = abspath(normpath(join(directory, filename)))
            if jail:
                common = commonpath([directory, path])
                if common != directory:
                    raise PermissionError(f"path {filename!r} illegal, it attempts to escape {directory!r} jail")
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

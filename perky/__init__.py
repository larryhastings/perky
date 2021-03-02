#!/usr/bin/env python3
#
# Part of the "perky" Python library
# Copyright 2018-2021 by Larry Hastings

# TODO:
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
# this should fail:
#    a = '''
#       outdenting is fun
#          '''
#
# make sure a quoted # works as a key
#
# ensure that unquoted string names can contain
#   [ { ''' """ #
# and unquoted string values can contain all those AND
#   =

# DONE
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
Copyright 2018-2021 by Larry Hastings
All rights reserved.
"""


__version__ = "0.5"

import ast
import os.path
from os.path import isfile, join, normpath
import re
import shlex
import sys
import textwrap
from .tokenize import *
from .utility import *


__all__ = []

def export(fn):
    __all__.append(fn.__name__)
    return fn

@export
class PerkyFormatError(Exception):
    def __init__(self, message, tokens=None, line=None):
        self.message = message
        self.tokens = tokens
        self.line = line

    def __repr__(self):
        strings = [f"<{self.__class__.__name__} {self.message!r}"]
        if self.tokens is not None:
            strings.append(f" tokens={self.tokens!r}")
        if self.line is not None:
            strings.append(f" line={self.line!r}")
        strings.append(">")
        return "".join(strings)

    def __str__(self):
        strings = [f"{self.__class__.__name__}: {self.message!r}"]
        if self.tokens is not None:
            strings.append(f"tokens={self.tokens!r}")
        if self.line is not None:
            strings.append(f"line={self.line!r}")
        return "\n".join(strings)

def assert_or_raise(expr, message, tokens, line):
    if not expr:
        raise PerkyFormatError(message, tokens, line)


class Parser:

    def __init__(self, s, *, pragmas=None, encoding='utf-8', root=None):
        self.lp = LineParser(s)
        self.pragmas = pragmas or {}
        self.encoding = encoding
        self.root = root if root is not None else {}
        self.breadcrumbs = []

    def assert_or_raise(self, expr, message, tokens, line):
        if not expr:
            raise PerkyFormatError(message, tokens, line)

    def _parse_pragma(self, line):
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
                raise PerkyFormatError(f"Line {self.lp.line_number}: Invalid pragma argument {argument}", tokens, line)
            argument = tokens[0][1]

        fn = self.pragmas.get(pragma)
        if not fn:
            raise PerkyFormatError(f"Line {self.lp.line_number}: Unknown pragma {pragma}", None, line)
        fn(self, argument)

    def _parse_value(self, t):
        tok, value = t
        if tok is LEFT_CURLY_BRACE:
            return self._read_dict()
        if tok is LEFT_SQUARE_BRACKET:
            return self._read_list()
        if (tok is TRIPLE_SINGLE_QUOTE) or (tok is TRIPLE_DOUBLE_QUOTE):
            return self._read_textblock(value)
        if tok is EMPTY_CURLY_BRACES:
            return {}
        if tok is EMPTY_SQUARE_BRACKETS:
            return []
        return value


    def _read_dict(self, starting_dict=None):
        d = starting_dict if starting_dict is not None else {}
        self.breadcrumbs.append(d)

        keys_seen = set()

        for tokens, line in self.lp:
            token, argument = tokens[0]
            if token is EQUALS:
                self._parse_pragma()
                continue
            if len(tokens) == 1:
                token, argument = tokens[0]
                if token is RIGHT_CURLY_BRACE:
                    break
                if token is COMMENT:
                    continue
            tokens = [t for t in tokens if t[0] is not WHITESPACE]

            self.assert_or_raise(
                (2 <= len(tokens) <= 3) and tokens[0][0] is STRING and tokens[1][0] is EQUALS,
                "Invalid token sequence: in dict, expected STRING = or STRING == VALUE or }",
                tokens, line)
            key = tokens[0][1].strip()
            self.assert_or_raise(
                key not in keys_seen,
                f"Invalid Perky dict: repeated key {key!r}",
                tokens, line)
            keys_seen.add(key)
            if len(tokens) == 3:
                value = self._parse_value(tokens[2])
            else:
                value = ""
            d[key] = value

        self.breadcrumbs.pop()
        return d

    def _read_list(self, starting_list=None):
        l = starting_list if starting_list is not None else []
        self.breadcrumbs.append(l)
        for tokens, line in self.lp:
            token, argument = tokens[0]
            if token is EQUALS:
                self._parse_pragma()
                continue
            self.assert_or_raise(
                len(tokens) == 1,
                "Invalid token sequence: in list, expected one token",
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
        while self.lp:
            line = self.lp.next_line().rstrip()
            stripped = line.lstrip()
            if stripped == marker:
                break
            l.append(line)

        prefix = line.partition(stripped)[0]
        if prefix:
            # detect this error:
            #    a = '''
            #       outdenting is fun
            #          '''
            for line in l:
                self.assert_or_raise(
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
        if isinstance(self.root, list):
            return self._read_list(self.root)
        return self._read_dict(self.root)


class Serializer:
    def __init__(self, prefix="    "):
        self.prefix = prefix
        self.reset()

    def reset(self):
        self.indent = 0
        self.lines = []
        self.line = ''

    def dumps(self):
        s =  "\n".join(self.lines)
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
            or any(c in s for c in non_quote_operators) # non_quote_operators is in tokenize
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
                raise RuntimeError("keys in perky dicts must always be strings!")
            if name == name.strip() and "".join(name.split()).isalnum():
                self.line = self.quoted_string(name)
            else:
                self.line = name
            self.line += " = "
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
        if isinstance(value, dict):
            return self.serialize_dict(value)
        if isinstance(value, list):
            return self.serialize_list(value)

        value = str(value)
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
        f.write(s.dumps() + "\n")



if 0:
    text = """

    a = b
    c = d
    dict = {
        inner1=value1
          inner 2 = " value 2  "
          list = [

          a
            b

        c
            ]
    }

    list = [

        1
        2
        3
    ]

    text = '''
        hello

        this is indented

        etc.
        '''

    """

    d = loads(text)
    print(d)
    print(serialize(d))


@export
def map(o, fn):
    if isinstance(o, dict):
        return {name: map(value, fn) for name, value in o.items()}
    if isinstance(o, list):
        return [map(value, fn) for value in o]
    return fn(o)


def _transform(o, schema, default):
    if isinstance(schema, dict):
        assert_or_raise(
            isinstance(o, dict),
            f"schema mismatch: schema is a dict, o should be a dict but is {o!r}",
            None, None)
        result = {}
        for name, value in o.items():
            handler = schema.get(name)
            if handler:
                value = _transform(value, handler, default)
            elif default:
                value = default(value)
            result[name] = value
        return result
    if isinstance(schema, list):
        assert_or_raise(
            isinstance(o, list) and (len(schema) == 1),
            f"schema mismatch: schema is a list, o should be a list but is {o!r}",
            None, None)
        handler = schema[0]
        return [_transform(value, handler, default) for value in o]
    assert_or_raise(
        callable(schema),
        f"schema mismatch: schema values must be dict, list, or callable, got {schema!r}",
        None, None)
    return schema(o)

@export
def transform(o, schema, default=None):
    assert_or_raise(
        isinstance(o, dict),
        "schema must be a dict",
        None, None)
    assert_or_raise(
        (not default) or callable(default),
        "default must be either None or a callable",
        None, None)
    return _transform(o, schema, default)


@export
def pragma_include(include_path=(".",)):
    assert isinstance(include_path, (list, tuple))
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
        leaf.clear()
        if isinstance(leaf, list):
            leaf.extend(merged)
        else:
            leaf.update(merged)
    return pragma_include

constmap = {
    'None': None,
    'True': True,
    'False': False,
}

@export
def const(s):
    return constmap[s]

@export
def nullable(type):
    def fn(o):
        if o == 'None':
            return None
        return type(o)
    return fn


class _AnnotateSchema:
    def __init__(self):
        self.reset()

    def reset(self):
        self.head = []
        self.tail = []

    def crawl(self, value, name=''):
        if isinstance(value, dict):
            self.head.append(name + "{")
            self.tail.append('}')
            d = value
            for name, value in d.items():
                self.crawl(value, name)
            self.head.pop()
            self.tail.pop()
            return

        if isinstance(value, list):
            self.head.append(name + "[")
            self.tail.append(']')
            self.crawl(value[0])
            self.head.pop()
            self.tail.pop()
            return

        assert_or_raise(
            callable(value),
            "Malformed schema error: " + repr(name) + " = " + repr(value) + ", value is not dict, list, or callable!",
            None, None)
        required = getattr(value, "_perky_required", None)
        if required:
            s = "".join(self.head) + name + "".join(reversed(self.tail))
            required[0] = s
            required[1] = False

class UnspecifiedRequiredValues(Exception):
    def __init__(self, breadcrumbs):
        self.breadcrumbs = breadcrumbs

    def __repr__(self):
        breadcrumbs = " ".join(shlex.quote(s) for s in self.breadcrumbs)
        return f"<UnspecifiedRequiredValues {breadcrumbs}>"

    def __str__(self):
        return repr(self)

@export
class Required:
    def __init__(self):
        self.markers = []

    def annotate(self, schema):
        annotator = _AnnotateSchema()
        annotator.crawl(schema)

    def __call__(self, fn):
        marker = ['', False]
        self.markers.append(marker)
        def wrapper(o):
            marker[1] = True
            return fn(o)
        wrapper._perky_required = marker
        return wrapper

    def verify(self):
        failed = []
        for breadcrumb, value in self.markers:
            if not value:
                failed.append(breadcrumb)
        if failed:
            failed.sort()
            raise UnspecifiedRequiredValues(failed)


if 0:
    o = {'a': '3', 'b': '5.0', 'c': ['1', '2', 'None', '3'], 'd': { 'e': 'f', 'g': 'True'}}
    schema = {'a': int, 'b': float, 'c': [nullable(int)], 'd': { 'e': str, 'g': const }}

    result = transform(o, schema)
    import pprint
    pprint.pprint(result)

    print("REQUIRED 1")
    r = Required()
    schema = {
        'a': r(int),
        'b': r(float),
        'c': [nullable(int)],
        'd': {
            'e': r(str),
            'g': const
            }
        }
    r.annotate(schema)
    print("schema", schema)
    result = transform(o, schema)
    print(result)
    r.verify()

    print("REQUIRED 2")
    r.annotate(schema)
    o2 = {'a': '44'}
    result = transform(o2, schema)
    r.verify()


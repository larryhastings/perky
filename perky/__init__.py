#!/usr/bin/env python3
#
# Part of the "perky" Python library
# Copyright 2018-2020 by Larry Hastings


# TODO:
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
# split include() into include() and includes()
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

__version__ = "0.1.3"

import ast
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
    pass

def assert_or_raise(*exprs):
    exprs = list(exprs)
    s = exprs.pop()
    if not all(exprs):
        raise PerkyFormatError(s)


class Parser:

    def __init__(self, s, *, pragmas=None, encoding='utf-8'):
        self.lp = LineParser(s)
        self.pragmas = pragmas or {}
        self.encoding = encoding
        self.root_dict = {}


    def assert_or_raise(self, *exprs):
        exprs = list(exprs)
        s = exprs.pop()
        if not all(exprs):
            raise PerkyFormatError(f"Line {self.lp.line_number}: {s}")

    def _parse_pragma(self):
        line = self.lp.line.strip()
        assert line[0] == '='
        line = line[1:].strip()

        fields = line.split(None, 1)
        pragma = fields[0].lower()
        arguments = fields[1] if len(fields) > 1 else None
        fn = self.pragmas.get(pragma)
        if not fn:
            raise PerkyFormatError(f"Line {self.lp.line_number}: Unknown pragma {pragma}")
        fn(self, arguments)

    def _parse_value(self, t):
        tok, value = t
        if tok is LEFT_CURLY_BRACE:
            return self._read_dict()
        if tok is LEFT_SQUARE_BRACKET:
            return self._read_list()
        if (tok is TRIPLE_SINGLE_QUOTE) or (tok is TRIPLE_DOUBLE_QUOTE):
            return self._read_textblock(value)
        return value


    def _read_dict(self, starting_dict=None):
        if starting_dict is None:
            d = {}
        else:
            d = starting_dict

        for tokens in self.lp:
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
                "Invalid token sequence: in dict, expected STRING = or STRING == VALUE or }, line = " + repr(self.lp.line))
            name = tokens[0][1].strip()
            if len(tokens) == 3:
                value = self._parse_value(tokens[2])
            else:
                value = ""
            d[name] = value
        return d

    def _read_list(self):
        l = []
        for tokens in self.lp:
            token, argument = tokens[0]
            if token is EQUALS:
                self._parse_pragma()
                continue
            self.assert_or_raise(
                len(tokens) == 1,
                "Invalid token sequence: in list, expected one token, line = " + repr(self.lp.line))
            token, argument = tokens[0]
            if token is RIGHT_SQUARE_BRACKET:
                break
            if token is COMMENT:
                continue
            value = self._parse_value(tokens[0])
            l.append(value)
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
                    "Format error: malformed line triple-quoted block, line is " + repr(line))

        s = "\n".join(line for line in l)
        # this one line does all the
        # heavy lifting in textwrap.dedent()
        s = re.sub(r'(?m)^' + prefix, '', s)
        return s

    def parse(self):
        return self._read_dict(self.root_dict)


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
        return shlex.quote(s)

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
def loads(s, *, pragmas=None, encoding='utf-8'):
    p = Parser(s, pragmas=pragmas, encoding=encoding)
    d = p.parse()
    return d

@export
def dumps(d):
    s = Serializer()
    s.serialize(d)
    return s.dumps()


@export
def load(filename, *, pragmas=None, encoding="utf-8"):
    with open(filename, "rt", encoding=encoding) as f:
        return loads(f.read(), pragmas=pragmas, encoding=encoding)

@export
def dump(filename, d, *, encoding="utf-8"):
    with open(filename, "wt", encoding=encoding) as f:
        f.write(serialize(d))




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
            f"schema mismatch: schema is a dict, o should be a dict but is {o!r}")
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
            isinstance(o, list),
            len(schema) == 1,
            f"schema mismatch: schema is a list, o should be a list but is {o!r}")
        handler = schema[0]
        return [_transform(value, handler, default) for value in o]
    assert_or_raise(
        callable(schema),
        f"schema mismatch: schema values must be dict, list, or callable, got {schema!r}")
    return schema(o)

@export
def transform(o, schema, default=None):
    assert_or_raise(
        isinstance(o, dict),
        "schema must be a dict")
    assert_or_raise(
        (not default) or callable(default),
        "default must be either None or a callable")
    return _transform(o, schema, default)


def _include(o, filenames, key, recursive, encoding):
    assert_or_raise(
        isinstance(o, dict),
        "object must be a dict")
    dicts = []
    for filename in filenames():
        d = load(filename, encoding=encoding)
        if recursive:
            d = include(d, include=include, includes=includes, recursive=True, encoding=encoding)
        dicts.append(d)
    dicts.append(o)
    final = dicts[0]
    for d in dicts[1:]:
        final.update(d)
    del final[key]
    return final

@export
def include(o, *, recursive=True, encoding="utf-8"):
    def filenames(o):
        include = o.get("include")
        if not include:
            return []
        return [include]
    return _include(o, filenames, "include", recursive=recursive, encoding=encoding)


@export
def includes(o, *, recursive=True, encoding="utf-8"):
    def filenames(o):
        includes = o.get("includes")
        if not include:
            return []
        return includes
    return _include(o, filenames, "includes", recursive=recursive, encoding=encoding)

@export
def pragma_include(parser, filename):
    sub_d = load(filename, pragmas=parser.pragmas, encoding=parser.encoding)
    parser.root_dict.update(sub_d)


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
            "Malformed schema error: " + repr(name) + " = " + repr(value) + ", value is not dict, list, or callable!")
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


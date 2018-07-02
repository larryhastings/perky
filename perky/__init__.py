#!/usr/bin/env python3
#
# Part of the "perky" Python library
# Copyright 2018 by Larry Hastings


# TODO:
#
# remove asserts
#
# remove tokens_match
#
# Per-line callback function (for #include)
#   * and, naturally, an example callback function
#     for you to use (aka "#include")
#
# More library utility functions to manage
# perky dict/lists:
# * A unary "transform" function--instead of a
#   whole schema, just a single function
# * recursive "chain map"
# * recursive merge
#
# Ensure you can use multiple Required objects
# with the same function (e.g. "int")

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


"""
A simple, Pythonic file format.  Same interface as the
"pickle" module (load, loads, dump, dumps).
"""

__version__ = "0.1.1"

import ast
import re
import shlex
import sys
import textwrap
from .tokenize import *
from .utility import *

class PerkyFormatError(Exception):
    pass


def _parse_value(t, lp):
    tok, value = t
    if tok == LEFT_CURLY_BRACE:
        return _read_dict(lp)
    if tok == LEFT_SQUARE_BRACKET:
        return _read_list(lp)
    if tok in (TRIPLE_SINGLE_QUOTE, TRIPLE_DOUBLE_QUOTE):
        return _read_textblock(lp, value)
    return value


def _read_dict(lp):
    d = {}
    # print("read_dict start, lp", lp)
    for tokens in lp:
        # print("read_dict TOKENS", tokens)
        if tokens_match(tokens, RIGHT_CURLY_BRACE):
            break
        assert len(tokens) == 3
        assert tokens[0][0] == STRING
        assert tokens[1][0] == EQUALS

        name = tokens[0][1].strip()
        value = _parse_value(tokens[2], lp)
        d[name] = value
        # print(f"NAME {name!r} = VALUE {value!r}")
    return d

def _read_list(lp):
    l = []
    for tokens in lp:
        # print("read_list TOKENS", tokens)
        if tokens_match(tokens, RIGHT_SQUARE_BRACKET):
            break
        assert len(tokens) == 1
        token = tokens[0]
        value = _parse_value(token, lp)
        l.append(value)
        # print(f"VALUE {value!r}")
    return l

def _read_textblock(lp, marker):
    l = []
    # print("read_textblock start, marker", marker)
    while lp:
        line = lp.line().rstrip()
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
            if line.strip() and not line.startswith(prefix):
                # print("RAISING PerkyFormatError")
                raise PerkyFormatError("Text in triple-quoted block before left margin")

    s = "\n".join(line for line in l)
    # this one line does all the
    # heavy lifting in textwrap.dedent()
    s = re.sub(r'(?m)^' + prefix, '', s)
    # print("read_textblock returning", repr(s))
    return s


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

def loads(s):
    lp = LineParser(s)
    d = _read_dict(lp)
    return d

def dumps(d):
    s = Serializer()
    s.serialize(d)
    return s.dumps()


def load(filename, encoding="utf-8"):
    with open(filename, "rt", encoding=encoding) as f:
        return loads(f.read())

def dump(filename, d, encoding="utf-8"):
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


constmap = {
    'None': None,
    'True': True,
    'False': False,
}

def const(s):
    return constmap[s]

def nullable(type):
    def fn(o):
        if o == 'None':
            return None
        return type(o)
    return fn


def _transform_function(o, fn):
    if isinstance(o, dict):
        return {name: _transform_function(value, fn) for name, value in o.items()}
    if isinstance(o, list):
        return [_transform_function(value, fn) for value in o]
    return fn(o)

def _transform_schema(o, schema):
    if isinstance(schema, dict):
        if not isinstance(o, dict):
            sys.exit("Schema mismatch, expected schema and o to both be dicts")
        newdict = {}
        for name, value in o.items():
            handler = schema.get(name)
            if handler:
                value = _transform_schema(value, handler)
            newdict[name] = value
        return newdict
    if isinstance(schema, list):
        if not isinstance(o, list):
            sys.exit("Schema mismatch, expected schema and o to both be lists")
        assert len(schema) == 1
        handler = schema[0]
        return [_transform_schema(value, handler) for value in o]
    return schema(o)

def transform(o, transformation=ast.literal_eval):
    if callable(transformation):
        return _transform_function(o, transformation)
    return _transform_schema(o, transformation)


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

        assert callable(value), "value " + repr(value) + " is not callable!"
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


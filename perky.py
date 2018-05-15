#!/usr/bin/env python3

# TODO:
#
# need write()
#
# aaaaaand now rename to load/loads dump/dumps *sob*
#
# define (and explicitly parse) the semantics
# for \ quoting in single-quoted strings

import re
import shlex
import sys
import textwrap

def _parse_value(value, lines):
    value = value.strip()
    if value == "{":
        return _read_dict(lines)
    if value == "[":
        return _read_list(lines)
    if value in ("'''", '"""'):
        return _read_textblock(lines, value)
    value = value.strip()
    if value.endswith(("'", '"')):
        return " ".join(shlex.split(value))
    return value

def _next_line(lines):
    while lines:
        line = lines.pop().strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        return line
    return None

def _read_dict(lines):
    d = {}
    while lines:
        line = _next_line(lines)
        if not line:
            break
        if line == "}":
            break
        name, equals, value = line.partition('=')
        assert equals, "no equals found on line " + repr(line)
        name = name.strip()
        value = _parse_value(value, lines)
        d[name] = value
    return d

def _read_list(lines):
    l = []
    while lines:
        line = lines.pop()
        _line = line.strip()
        if _line == ']':
            break
        if not _line or _line.startswith('#'):
            continue
        value = _parse_value(line, lines)
        l.append(value)
    return l

def _read_textblock(lines, marker):
    l = []
    while lines:
        line = lines.pop()
        stripped = line.strip()
        if stripped == marker:
            break
        l.append(line)
    prefix = line.partition(stripped)[0]
    s = "\n".join(line.rstrip() for line in l)
    if prefix:
        # this one line does all the
        # heavy lifting in textwrap.dedent()
        s = re.sub(r'(?m)^' + prefix, '', s)
    while s.startswith("\n"):
        s = s[1:]
    return s

def parse(s):
    lines = s.split("\n")
    lines.reverse()
    return _read_dict(lines)


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
            if name != name.strip():
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
        if ((value == value.strip())
            and (not value.startswith(('"', "'")))
            and (not value.endswith(  ('"', "'")))
            ):
            self.newline(value)
            return
        return self.serialize_quoted_string(value)

def serialize(d):
    s = Serializer()
    s.serialize(d)
    return s.dumps()


def read(filename, encoding="utf-8"):
    with open(filename, "rt", encoding=encoding) as f:
        parse(f.read())

if 1:
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

    d = parse(text)
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

def transform(o, schema):
    if isinstance(schema, dict):
        if not isinstance(o, dict):
            sys.exit("Schema mismatch, expected schema and o to both be dicts")
        newdict = {}
        for name, value in o.items():
            handler = schema.get(name)
            if handler:
                value = transform(value, handler)
            newdict[name] = value
        return newdict
    if isinstance(schema, list):
        if not isinstance(o, list):
            sys.exit("Schema mismatch, expected schema and o to both be lists")
        newlist = []
        assert len(schema) == 1
        handler = schema[0]
        for value in o:
            newlist.append(handler(value))
        return newlist
    return schema(o)

if 1:
    o = {'a': '3', 'b': '5.0', 'c': ['1', '2', 'None', '3'], 'd': { 'e': 'f', 'g': 'True'}}
    schema = {'a': int, 'b': float, 'c': [nullable(int)], 'd': { 'e': str, 'g': const }}

    result = transform(o, schema)
    import pprint
    pprint.pprint(result)

    print("SER 1")
    print(serialize(o))
    print("SER 2")
    print(serialize(result))
    print("END")



#!/usr/bin/env python3

# need write()
#
# dedent to level of first ending '''
#

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
        value = _parse_value(line, lines)
        l.append(value)
    return l

def _read_textblock(lines, marker):
    l = []
    while lines:
        line = lines.pop()
        if line.strip() == marker:
            break
        l.append(line)
    s = "\n".join(l)
    s = textwrap.dedent(s)
    s = "\n".join(line.rstrip() for line in s.split("\n"))
    while s.startswith("\n"):
        s = s[1:]
    return s

def parse(s):
    lines = s.split("\n")
    lines.reverse()
    return _read_dict(lines)

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

    print(parse(text))


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


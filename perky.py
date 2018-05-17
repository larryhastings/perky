#!/usr/bin/env python3

# TODO:
#
# define (and explicitly parse) the semantics
# for \ quoting in single-quoted strings
#   * reuse the python tokenizer!
#   * don't auto-merge multiple string literals,
#     the only supported things are
#           list of ids = a
#           "single quoted string" = b
#
# make sure a quoted # works as a key
#
# triple-quote string should complain if
# there are non-space characters to the
# left of the triple quote
#
# triple-quote string should only
#    * strip first leading \n
#    * strip last trailing \n
#    * strip trailing non-\n whitespace on last line
#
# More library utility functions to manage
# perky dict/lists:
# * A unary "transform" function--instead of a
#   whole schema, just a single function
# * recursive "chain map"
# * recursive merge
#
# Per-line callback function (for #include)
#
# Ensure you can use multiple Required objects
# with the same function (e.g. "int")



import re
import shlex
import sys
import textwrap

class PerkyFormatError(Exception):
    pass


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
    if prefix:
        # detect this error:
        #    a = '''
        #       outdenting is fun
        #          '''
        for line in l:
            if line.strip() and not line.startswith(prefix):
                raise PerkyFormatError("Text in triple-quoted block before left margin")

    s = "\n".join(line.rstrip() for line in l)
        # this one line does all the
        # heavy lifting in textwrap.dedent()
    s = re.sub(r'(?m)^' + prefix, '', s)
    while s.startswith("\n"):
        s = s[1:]
    return s

def loads(s):
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
            if not isinstance(name, str):
                raise RuntimeError("keys in perky dicts must always be strings!")
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

def dumps(d):
    s = Serializer()
    s.serialize(d)
    return s.dumps()


def load(filename, encoding="utf-8"):
    with open(filename, "rt", encoding=encoding) as f:
        return parse(f.read())

def dump(filename, d, encoding="utf-8"):
    with open(filename, "wt", encoding=encoding) as f:
        f.write(serialize(d))


# compatibility
parse = loads
read = load
serialize = dumps
write = dump


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


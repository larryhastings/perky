##############################################################################
##############################################################################
##
##  *Everything* in this file is *deprecated.*
##
##  If you're using any of this code, please stop.
##  Or fork off a copy and maintain it yourself.
##
##  If you haven't started using it, please don't start.
##
##  The entire "transformation" part of Perky will be *removed* before 1.0.
##
##############################################################################
##############################################################################

from .utility import *

__all__ = []

def export(fn):
    __all__.append(fn.__name__)
    return fn


@export
class RecursiveChainMap(dict):

    def __init__(self, *dicts):
        self.cache = {}
        self.maps = [self.cache]
        self.maps.extend(dicts)
        self.deletes = set()

    def __repr__(self):
        return "<RecursiveChainMap "  + " ".join(repr(d) for d in self.maps) + " cache=" + repr(self.cache) + ">"

    def __missing__(self, key):
        raise KeyError(key)

    def __getitem__(self, key):
        if key in self.deletes:
            raise self.__missing__(key)

        submaps = []
        for map in self.maps:
            try:
                # "key in dict" doesn't work with defaultdict!
                value = map[key]
                if isinstance(value, dict):
                    submaps.append(value)
                elif not submaps:
                    return value
            except KeyError:
                continue

        if not submaps:
            raise self.__missing__(key)

        value = RecursiveChainMap(*submaps)
        self.cache[key] = value
        return value

    def __setitem__(self, key, value):
        self.cache[key] = value
        self.deletes.discard(key)

    def __delitem__(self, key, value):
        if key in self.deletes:
            self.__missing__(key)
        self.deletes.add(key)

    __sentinel = object()

    def get(self, key, default=__sentinel):
        if key in self:
            return key[self]
        if default is not __sentinel:
            return default
        raise self.__missing__(key)

    def __len__(self):
        return len(set().union(*self.maps) - self.deletes)

    def __iter__(self):
        return iter(set().union(*self.maps) - self.deletes)

    def __contains__(self, key):
        if key in self.deletes:
            return False
        return any(key in map for map in self.maps)

    def __bool__(self):
        if not self.deletes:
            return any(self.maps)
        for map in self.maps:
            keys = set(map) - self.deletes
            if keys:
                return True

    def keys(self):
        yield from self

    def values(self):
        for k in self:
            yield self[k]

    def items(self):
        for k in self:
            yield k, self[k]


def _merge_dicts(rcm):
    d = {}
    for key in rcm:
        value = rcm[key]
        if isinstance(value, RecursiveChainMap):
            value = _merge_dicts(value)
        d[key] = value
    return d

@export
def merge_dicts(*dicts):
    rcm = RecursiveChainMap(*dicts)
    return _merge_dicts(rcm)



@export
def map(o, fn):
    if isinstance(o, dict):
        return {name: map(value, fn) for name, value in o.items()}
    if isinstance(o, list):
        return [map(value, fn) for value in o]
    return fn(o)


def _transform(o, schema, default):
    if isinstance(schema, dict):
        raise_if_false(
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
        raise_if_false(
            isinstance(o, list) and (len(schema) == 1),
            f"schema mismatch: schema is a list, o should be a list but is {o!r}",
            None, None)
        handler = schema[0]
        return [_transform(value, handler, default) for value in o]
    raise_if_false(
        callable(schema),
        f"schema mismatch: schema values must be dict, list, or callable, got {schema!r}",
        None, None)
    return schema(o)

@export
def transform(o, schema, default=None):
    raise_if_false(
        isinstance(o, dict),
        "schema must be a dict",
        None, None)
    raise_if_false(
        (not default) or callable(default),
        "default must be either None or a callable",
        None, None)
    return _transform(o, schema, default)


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

        raise_if_false(
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


# perky

## A friendly, easy, Pythonic text file format

##### Copyright 2018-2019 by Larry Hastings


### Overview

Perky is a new, simple "rcfile" text file format for Python programs.

The following are Perky features:

#### Perky syntax

Perky configuration files look something like JSON without the
quoting.

    example name = value
    example dict = {
        name = 3
        another name = 5.0
        }
    example list = [
        a
        b
        c
        ]
    # lines starting with hash are ignored

    # blank lines are ignored

    " quoted name " = " quoted value "

    triple quoted string = """

        indenting
            is preserved

        the string is automatically outdented
        to the leftmost character of the ending
        triple-quote

        <-- aka here
        """

#### Explicit transformation is better than implicit

One possibly-surprising design choice of Perky: the only
natively supported values for the Perky parser are dicts,
lists, and strings.  Other commonly-used types (ints, floats,
etc) are handled using a different mechanism: _transformation._

A Perky transformation takes a dict as input, and transforms
the contents of the dict based on a _schema_.  A Perky schema
is a dict with the same general shape as the dict produced
by the Perky parse, but it contains dicts, lists,
and *transformation functions*.
If you want *myvalue* in `{'myvalue':'3'}` to be a real integer,
transform it with the schema `{'myvalue': int}`.

Note that Perky doesn't care how or if you transform your
data.  You can use it as-is, or transform it, or transform
it with multiple passes, or use an external transformation technology like
[Marshmallow.](https://marshmallow.readthedocs.io/en/3.0/)

### API

`perky.loads(s) -> d`

Parses a string containing Perky-file-format settings.
Returns a dict.

`perky.load(filename, encoding="utf-8") -> d`

Parses a file containing Perky-file-format settings.
Returns a dict.

`perky.dumps(d) -> s`

Converts a dictionary to a Perky-file-format string.
Keys in the dictionary must all be strings.  Values
that are not dicts, lists, or strings will be converted
to strings using str.
Returns a string.

`perky.dump(filename, d, encoding="utf-8")`

Converts a dictionary to a Perky-file-format string
using `perky.dump`, then writes it to *filename*.

`perky.include(d, include=True, includes=False, recursive=True, encoding="utf-8") -> d`

Processes `include` directives inside a dictionary.  The first
argument `d` must be a dictionary.

If `include` is True, and `d['include']` is set, the value of
`d['include']` will be used as the first filename, see below.

If `includes` is True, and `d['includes']` is set, the value of
`d['includes']` will be used as an iterable of filenames, see below.

For every filename in the list of filenames, `perky.include()` will
`perky.load()` a dictionary from that filename, using the encoding
passed in.  If `recursive` is set, then `perky.include()` will
recursively process includes in those dictionaries.

After processing all filenames, `perky.include()` will merge the dictionaries
together.  The dictionaries are merged in this order: first "include",
then "includes", then the original `d` argument.
Returns this final merged dictionary.

`perky.map(d, fn) -> o`

Iterates over a dictionary.  Returns a new dictionary where,
for every *value*:
  * if it is a dict, replace with a new dict.
  * if it is a list, replace with a new list.
  * if it is neither a dict nor a list, replace with
    `fn(value)`.

The function passed in is called a *conversion function*.

`perky.transform(d, schema, default=None) -> o`

Recursively transforms a Perky dict into some other
object (usually a dict) using the provided schema.
Returns a new dict.

A *schema* is a data structure matching the general expected
shape of *d*, where the values are dicts, lists, and
callables.  The transformation is similar to `perky.map()`
except that individual values will have individual conversion
functions.  Also, a schema conversion function can be specified
for any value in *d*, even dicts or lists.

*default* is a default conversion function.  If there is a
value *v* in *d* that doesn't have an equivalent entry in *schema*,
and *v* is neither a list nor a dict, and if *default* is
a callable, *v* will be replaced with `default(v)` in the
output.

`perky.Required`

Experimental.

`perky.nullable(fn) -> fn`

Experimental.

`perky.const(fn) -> o`

Experimental.


### TODO

* Backslash quoting currently does "whatever your version of Python does".  Perhaps this should be explicit, and parsed by Perky itself?

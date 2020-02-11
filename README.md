# perky

## A friendly, easy, Pythonic text file format

##### Copyright 2018-2020 by Larry Hastings


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

    =pragma argument

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

### Pragmas

A *pragma* is a metadata directive for the Perky parser.
It's a way of sending instructions to the Perky parser from
inside a bit of Perky text.

Here's an example pragma directive:

`=foo bar bat`

The first word after the equals sign is the name of the pragma, in this case `"foo"`.
Everything after the name of the pragma is an argument, with all leading
and trailing whitespace removed, in this case `"bar bat"`.

By default, Perky doesn't have any pragma handlers.  And invoking a pragma
when Perky doesn't have a handler for it is a runtime error.
But you can define your own pragma handlers when you call `perky.load()`
or `perky.loads()`, using a named parameter called `pragmas`.
If you pass in a value for `pragmas`, it must be a mapping
of strings to functions.
The string name should be the name of the pragma (and must be lowercase).
The function it maps to will "handle" that pragma, and should look like this:

`def pragma_fn(parser, argument)`

`parser` is the internal Perky `Parser` object.  `argument` is the
rest of the relevant line, with leading & trailing whitespace stripped.

There's currently one predefined pragma handler, a function called
`perky.pragma_include()`.  This adds "include statement" functionality
to Perky.  If you call this:

`perky.load(filename, pragmas={'include': perky.pragma_include})`

then Perky will interpret lines inside `filename` starting with `=include`
as include statements, using the rest of the line as the name of a file.
For more information, see `pragma_include()` below.

The rules of pragmas:
* To invoke a pragma, use `=` as the first non-whitespace character
  on a line.
* pragmas must always be lowercase.
* pragmas are always global.  You can call pragmas
  inside a nested dict or list but, if they change data,
  they'll always operate on the outermost dict.
* You can't invoke a pragma inside a triple-quoted string.
* It's best to have all your pragmas at the top of your Perky text.

### API

`perky.loads(s, *, pragmas=None) -> d`

Parses a string containing Perky-file-format settings.
Returns a dict.

`perky.load(filename, *, pragmas=None, encoding="utf-8") -> d`

Parses a file containing Perky-file-format settings.
Returns a dict.

`perky.dumps(d) -> s`

Converts a dictionary to a Perky-file-format string.
Keys in the dictionary must all be strings.  Values
that are not dicts, lists, or strings will be converted
to strings using str.
Returns a string.

`perky.dump(filename, d, *, encoding="utf-8")`

Converts a dictionary to a Perky-file-format string
using `perky.dump`, then writes it to *filename*.

`perky.include(d, recursive=True, encoding="utf-8") -> d`

Processes an `include` directive inside a dictionary.  The first
argument `d` must be a dictionary.

If `d["include"]` is set, that value is used as a filename.
`perky.include()` will execute `perky.load(filename)` using the encoding
passed in, then merge dictionary into `d`--however existing values in `d`
take precedence.  If `recursive` is set, then `perky.include()` will
recursively process includes in those dictionaries.

Returns this final merged dictionary.

`perky.includes(d, recursive=True, encoding="utf-8") -> d`

Similar to `perky.include`, except the name of the key
is `d["includes"]`, and it must contain a *list* of filenames
rather than simply one filename.  `perky.includes()` will then
read in all those filenames, merge them together, then merge
that with the `d` passed in.

`pragma_include(...)`

A pre-written pragma handler for you.  If you use this function
to handle `"include"` pragmas, then the pragma `=include foo` will
`perky.load()` the file `foo` into the current (top-level) dictionary
being loaded.  `pragma_include()` will pass in the current pragma
handlers into `perky.load()`, allowing for (for example) recursive
incldues.

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

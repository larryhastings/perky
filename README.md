# perky

## A friendly, easy, Pythonic text file format

##### Copyright 2018-2021 by Larry Hastings


### Overview

Perky is a new, simple "rcfile" text file format for Python programs.
It solves the same problem as "INI" files, "TOML" files, and "JSON"
files, but with its own opinion about how to best solve the problem.

Perky's goals:

* Minimal, human-friendly syntax.  Perky files are easy to write by hand.
* Explicit minimal data type support.  Rather than guess at the types
  of your data, Perky lets you handle the final transformation.
* Lightweight, simple, and fast.  Perky's implementation is small
  and straightforward.  Ignoring comments and test code, it's about
  1k lines of Python.  Fewer lines means fewer bugs!  (Hopefully!)
* Flexible and extensible.  Perky permits extending the semantics of
  Perky files through a "pragma" mechanism.

#### Perky syntax

Perky configuration files look something like JSON without the
quoting.  It supports only a surprisingly small set of value
types:

* strings, including quoted strings and
  "triple-quoted strings" (multi-line strings),
* "lists" (arrays),
* and "dicts" (associative arrays).

Perky is line-oriented; individual values go on a single
line.  Container objects use one line per internal value.

You may nest lists and dicts as deeply as memory permits.

Unlike Python itself, leading whitespace is ignored.  You
are free to use leading whitespace to show structure but
this is optional.

Blank lines and comment lines (lines starting with `#`)
are ignored.

Perky also supports "pragmas", which are lines that start
with an equals sign.  By default Perky doesn't define any
pragmas--it's an extension mechanism for your use.

Here's a sample Perky configuration file exercising all
the things you can do in Perky:

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
    nested dict = {
        name = value
        nesting level 2 = {
            nesting level 3 = {
                and = so on!
                }
            }
        list inside the dict = [
            value in the list
                [
                and this is in a nested list!
                this is another value.
                you see?
                ]
            ]
        }
    # lines starting with hash are comments and are ignored!

    # blank lines are ignored too!

    " quoted name " = " quoted value "

    triple quoted string = """

        indenting
            is preserved

        the string is automatically outdented
        to the leftmost character of the *ending*
        triple-quote

        <-- aka here
        """

    one-line empty list = []
    one-line empty dict = {}
    one-line empty list with whitespace = [ ]
    one-line empty dict with whitespace = { }
    multi-line empty list = [
        ]
    multi-line empty dict = {
        }

    =pragma
    =pragma with argument

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
it with multiple passes.  You don't even need to use Perky's
simple transformation mechanisms--you can ignore them completely
and use an external transformation library like
[Marshmallow.](https://marshmallow.readthedocs.io/)

### Pragmas

A *pragma* is a metadata directive for the Perky parser.
It's a way of sending instructions to the Perky parser from
inside a bit of Perky text.

Here's an example pragma directive:

`=command argument here`

The first word after the equals sign is the name of the pragma, in this case `"command"`.
Everything after the name of the pragma is an argument, with all leading
and trailing whitespace removed, in this case `"argument here"`.

By default, Perky doesn't have any pragma handlers.  And invoking a pragma
when Perky doesn't have a handler for it is a runtime error.
But you can define your own pragma handlers when you call `perky.load()`
or `perky.loads()`, using a named parameter called `pragmas`.
If you pass in a value for `pragmas`, it must be a mapping
of strings to functions.
The string name should be the name of the pragma and must be lowercase.
The function it maps to will "handle" that pragma, and should match this
prototype:

`def pragma_fn(parser, argument)`

`parser` is the internal Perky `Parser` object.  `argument` is the
rest of the relevant line, with leading & trailing whitespace stripped.
(If the rest of the line was empty, `argument` will be `None`).
The return value of the pragma function is ignored.

There's currently only one predefined pragma handler, a function called
`perky.pragma_include()`.  This adds "include statement" functionality
to Perky.  If you call this:

`perky.load(filename, pragmas={'include': perky.pragma_include()})`

then Perky will interpret lines inside `filename` starting with `=include`
as include statements, using the rest of the line as the name of a file.
For more information, see `pragma_include()` below.

The rules of pragmas:
* To invoke a pragma, use `=` as the first non-whitespace character
  on a line.
* The names of pragmas must always be lowercase.
* You can't invoke a pragma inside a triple-quoted string.
* Pragmas can be "context-sensitive": they can be aware of where
  they are run inside a file, and e.g. modify the current dict
  or list.  The pragma function can see the entire current nested
  list of dicts and lists being parsed (via `parser.breadcrumbs`).
* The rest of the line after the name of the pragma is the
  pragma argument value, if any.  This is always a string.  It can
  be a quoted string.

### Parsing Errors

There are only a few errors possible when parsing a Perky text:

* Obviously, syntax errors, for example:
    * A line in a dict that doesn't have an unquoted equals sign
    * A line in a list that looks like a dict line (`name = value`).
      (If you want a value like that inside a list, simply put it in quotes.)
    * A triple-quoted string where any line is outdented past
      the ending triple quotes line.
* Defining the same value twice in the same dict.  This is flagged
  as an error, because it could easily be a mistake, and in Python
  we don't want to let errors pass silently.
* Using an undefined pragma.
* Using one of Perky's special tokens as a pragma argument, like
  `{`, `[`, `'''`, `"""`, `[]`, or `{}`.

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

`perky.dump(filename, d, *, pragmas=None, encoding="utf-8")`

Converts a dictionary to a Perky-file-format string
using `perky.dump`, then writes it to *filename*.

`perky.pragma_include(include_path=(".",))`

This function generates a pragma handler that adds "include"
functionality.  "Including" means lexically inserting one Perky
file inside another, contextually at the spot where the pragma
exists.

For example:

    d = perky.loads("a=3\n" "=include data.pky\n" "c=5\n",
        pragmas={"include": perky.pragma_include()},
        )

If *data.pky* contained the following:

    b=4

then `d` would be set to the dictionary:

    {'a': '3', 'b': '4', 'c': '5'}

`perky.pragma_include()` is not the pragma handler itself;
it returns a function (a closure) which remembers the `include_path`
you pass in.  This allows you to use it for multiple pragmas that
include from different paths, e.g.:

    include_dirs = [appdirs.user_data_dir(myapp_name)]
    config_dirs = [appdirs.user_config_dir(myapp_name)]
    pragmas = {
        'include': perky.pragma_include(include_dirs),
        'config': perky.pragma_include(config_dirs),
    }

Notes:

* The pragma handler is context-sensitive; the included
file will be included as if it was copied-and-pasted replacing
the pragma line.  Among other things, this means that if the pragma
is invoked inside a list context, the included file must *start*
in a list context.

* When loading the file, the pragma handler will pass in the
current pragma handlers into `perky.load()`.  Among other things,
this allows for recursive includes.

* When including inside a dict context, you're explicitly permitted
to re-define existing keys if they were previously defined in
another file.

* The default value for `include_path` only searches the
current directory (`"."`).  If you override the default
and pass in your own include path, the pragma handler
won't search the current directory unless you add `"."`
to the include path yourself.


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

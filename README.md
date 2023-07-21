# perky

## A friendly, easy, Pythonic text file format

##### Copyright 2018-2023 by Larry Hastings

[![# test badge](https://img.shields.io/github/actions/workflow/status/larryhastings/perky/test.yml?branch=master&label=test)](https://github.com/larryhastings/perky/actions/workflows/test.yml) [![# coverage badge](https://img.shields.io/github/actions/workflow/status/larryhastings/perky/coverage.yml?branch=master&label=coverage)](https://github.com/larryhastings/perky/actions/workflows/coverage.yml) [![# python versions badge](https://img.shields.io/pypi/pyversions/perky.svg?logo=python&logoColor=FBE072)](https://pypi.org/project/perky/)

### Overview

Perky is a new, simple "rcfile" text file format for Python programs.
It solves the same problem as "INI" files, "TOML" files, and "JSON"
files, but with its own opinion about how to best solve the problem.

Perky's features:

* Minimal, human-friendly syntax.  Perky files are easy to write by hand.
* Explicit minimal data type support.  Rather than guess at the types
  of your data, Perky lets you handle the final transformation.
* Lightweight, simple, and fast.  Perky's implementation is small
  and straightforward.  Ignoring comments and test code, it's about
  1k lines of Python.  Fewer lines means fewer bugs!  (Hopefully!)
* Flexible and extensible.  Perky permits extending the semantics of
  Perky files through a "pragma" mechanism.
* Written in 100% pure Python, but still parses >300k lines per
  second on a modern desktop.
* Perky supports Python 3.6+, and passes its unit test suite with
  100% coverage (excluding the deprecated portions).

#### Perky syntax

Perky configuration files look something like JSON without the
quoting.  It supports only a surprisingly small set of value
types:

* strings, including quoted strings and
  "triple-quoted strings" (multi-line strings),
* "mappings" (dicts), and
* "sequences" (lists).

Perky is line-oriented; individual values go on a single
line.  Container objects use one line per internal value.

You may nest lists and dicts as deeply as memory permits.

Unlike Python itself, leading whitespace is ignored.
You can use leading whitespace however you like but it's
optional.  (Leading whitespace is preserved for
triple-quoted strings, though with a clever syntax
that allows outdenting the actual value.)

Blank lines and comment lines (lines starting with `#`)
are ignored, except inside triple-quoted strings.

Perky also supports "pragmas", lines that start
with an equals sign that can perform special runtime
behavior.  By default Perky doesn't define any
pragmas--it's an extension mechanism for your use.

Here's a sample configuration file exercising all
the things Perky can do:

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
lists, and strings.  What about ints? floats? dates?
booleans?  `NULL`?  `None`?

Perky deliberately leaves that up to you.  As the Zen
Of Python says:

*In the face of ambiguity, refuse the temptation to guess.*

Perky doesn't know what types your program needs.  So,
rather than guess and be wrong, Perky keeps things simple:
just lists, dicts, and strings.  For any other type,
it's up to you to transform it from a string into the type
you want, and back again.

Note that Perky doesn't care how or if you transform your
data.  You can use the strings as-is or transform them
however you like.  You can transform them by hand,
or with a third-party data transformation library like
[Marshmallow.](https://marshmallow.readthedocs.io/)

(Perky used to support an experimental API for automated
data transformation.  But this was never fully fleshed-out,
and there are better versions of that technology out there.
I've deprecated the "transformation" submodule and will
remove it before 1.0.)


### Pragmas

A *pragma* is a metadata directive for the Perky parser.
It's a way of sending instructions to the Perky parser from
inside a bit of Perky text.  In Perky, a pragma is a line
that starts with an unquoted equals sign.

Here's an example pragma directive:

`=command argument here`

The first word after the equals sign is the name of the pragma, in this case `"command"`.
Everything after the name of the pragma is an argument, with all leading
and trailing whitespace removed, in this case `"argument here"`.

By default, Perky doesn't have any pragma handlers.  And invoking a pragma
when Perky doesn't have a handler for it is a runtime error.
But you can define your own pragma handlers when you call `load()`
or `loads()`, using a named parameter called `pragmas`.
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
`pragma_include()`.  This adds "include statement" functionality
to Perky.  If you call this:

`load(filename, pragmas={'include': pragma_include()})`

then Perky will interpret lines inside `filename` starting with `=include`
as include statements, using the rest of the line as the name of a file.
For more information, see `pragma_include()` below.

The rules of pragmas:
* To invoke a pragma, use `=` as the first non-whitespace character
  on a line.
* The names of pragmas must always be lowercase.
* You can invoke a pragma inside a sequence or mapping context.
  But you can't invoke a pragma inside a triple-quoted string.
* Pragmas can be "context-sensitive": they can be aware of where
  they are run inside a file, and e.g. modify the current dict
  or list.  The pragma function can see the entire current nested
  list of dicts and lists being parsed (via `parser.breadcrumbs`).
* The rest of the line after the name of the pragma is the
  pragma argument value, if any.  This is always a string, which
  can be either unquoted or single-quoted; if it's unquoted, it
  can't contain any special symbols (`{ } = ''' """`).
* If you want a line to start with an equals sign (a `value`, or
  a `name=value`), but you *don't* want it to be a pragma, just
  put quotes around it.  Likewise, if you want to use special
  symbols in the pragma argument, just put (single) quotes around
  it.

### The Parser object

Pragma functions recieve the Perky `Parser` object as an
argument.  This object encapsulates all the current state
of parsing the Perky file at the current time.  Here are
the relevant attributes you may want to use from your
pragma:

* `parser.source` contains the source of the current
  Perky text, either a filename or the string '<string>'.
* `parser.line_number` contains the line number of
  the current line being parsed.  The first line of the
  Perky text is line 1.
* `parser.stack` is a stack of references to collection
  objects--the stack of nested dicts and lists from the
  top to where we are now in the Perky file.
  `parser.stack[0]` is always the root, and will be the
  object returned by `load` or `loads`.  `parser.stack[-1]`
  is always the current context the pragma was run in.
  It can be either a list or a dict.  You should determine
  which using
  `isinstance(parser.stack[-1], collections.abc.Mapping)`;
  if this is `True`, the current context is a mapping
  context (a dict), and if this is `False` the current
  context is a sequence context (a list).

### Parsing Errors

There are only a few errors possible when parsing a Perky text:

* Obviously, syntax errors, for example:
    * A line in a dict that doesn't have an unquoted equals sign
    * A line in a list that looks like a dict line (`name = value`).
      (If you want a value containing an equals sign inside a list,
      simply put it in quotes.)
    * A triple-quoted string where any line is outdented past
      the ending triple quotes line.
* Defining the same value twice in the same dict.  This is flagged
  as an error, because it could easily be a mistake, and like Python
  we don't want to let errors pass silently.
* Using an undefined pragma.
* Using one of Perky's special tokens as a pragma argument, like
  `{`, `[`, `'''`, `"""`, `[]`, or `{}`.

### API

#### `loads(s, *, pragmas=None, root=None)`

Parses a Perky-format string, and returns a container filled
with the values parsed from that string.

If `pragmas` is not `None`, it must be a mapping of
strings to pragma handler functions.  Please see the
**Pragmas** section of the documentation.

If `root` is `None`, `loads` behaves as if you passed in an
empty `dict`.

If `root` is not `None`, it should be a container, either
a mutable mapping (`dict`) or a mutable sequence (`list`).
This affects how the data is parsed; if `root` is a
mutable mapping, the top level of the Perky file must be
a "mapping context" (a series of `name=value` lines);
if `root` is a mutable sequence, the top level of the Perky
file is assumed to be a "sequence context"
(a series of `value` lines).

#### `load(filename, *, pragmas=None, root=None)`

Loads a file containing Perky-file-format settings.
Returns a dict.

The text in the file must be encoded using
[UTF-8](https://en.wikipedia.org/wiki/UTF-8).

If `root` is `None`, `loads` behaves as if you passed in an
empty `dict`.

If `root` is not `None`, it should be a container, either
a mutable mapping (`dict`) or a mutable sequence (`list`).
This affects how the data is parsed; if `root` is a
mutable mapping, the top level of the Perky file must be
a "mapping context" (a series of `name=value` lines);
if `root` is a mutable sequence, the top level of the Perky
file is assumed to be a "sequence context"
(a series of `value` lines).

If `pragmas` is not `None`, it must be a mapping of
strings to pragma handler functions.  Please see the
**Pragmas** section of the documentation.

#### `dumps(d)`

Converts a dictionary to a Perky-file-format string.
Keys in the dictionary must all be strings.  Values
that are not dicts, lists, or strings will be converted
to strings using str.
Returns a string.

#### `dump(filename, d)`

Converts a dictionary to a Perky-file-format string
using `dump`, then writes it to *filename*.

The text in the file will be encoded using
[UTF-8](https://en.wikipedia.org/wiki/UTF-8).

#### `pragma_include(include_path=(".",))`

This function generates a pragma handler that adds "include"
functionality.  "Including" means lexically inserting one Perky
file inside another, contextually at the spot where the pragma
exists.

For example, if you ran this:

    d = loads("a=3\n" "=include data.pky\n" "c=5\n",
        pragmas={"include": pragma_include()},
        )

And *data.pky* in the current directory was readable and
contained the following text:

    b=4

then `d` would be set to the dictionary:

    {'a': '3', 'b': '4', 'c': '5'}

`pragma_include()` is not the pragma handler itself;
it returns a function (a closure) which remembers the `include_path`
you pass in.  This allows you to use it for multiple pragmas that
include from different paths, e.g.:

    include_dirs = [appdirs.user_data_dir(myapp_name)]
    config_dirs = [appdirs.user_config_dir(myapp_name)]
    pragmas = {
        'include': pragma_include(include_dirs),
        'config': pragma_include(config_dirs),
    }

Notes:

* The pragma handler is context-sensitive; the included
file will be included as if it was copied-and-pasted replacing
the pragma line.  Among other things, this means that if the pragma
is invoked inside a sequence context, the included file must *start*
in a sequence context.

* When loading the file, the pragma handler will pass in the
current pragma handlers into `load()`.  Among other things,
this allows for recursive includes.

* When including inside a dict context, you're explicitly permitted
to re-define existing keys if they were previously defined in
another file.

* The default value for `include_path` only searches the
current directory (`"."`).  If you override the default
and pass in your own include path, the pragma handler
won't search the current directory unless you explicitly
add `"."` to the include path yourself.

* If `pragma_include` can't find the requested file on
its search path, it raises `FileNotFoundError`.


#### Deprecated API

Perky has a "transformation" submodule.
The idea is, you load a Perky file,
then run `transform` on that dictionary to
convert the strings into native values.

These functions are no longer maintained or supported,
are excluded from
[coverage](https://github.com/nedbat/coveragepy)
testing, and will be removed before 1.0.
Why?  This part of Perky was always
an experiment... and the experiment never really paid
off.  There are better implementations of this idea,
like [Marshmallow](https://marshmallow.readthedocs.io/)--you
you should use those instead.  (If you're relying on
this code in Perky, I encourage you to fork
off a copy and maintain it yourself.  But I doubt
anybody is.)

For posterity's sakes, here's documentation of the
now-deprecated API.

`map(d, fn) -> o`

Iterates over a dictionary.  Returns a new dictionary where,
for every *value*:
  * if it's a dict, replace with a new dict.
  * if it's a list, replace with a new list.
  * if it's neither a dict nor a list, replace with
    `fn(value)`.

The function passed in is called a *conversion function*.

`transform(d, schema, default=None) -> o`

Recursively transforms a Perky dict into some other
object (usually a dict) using the provided schema.
Returns a new dict.

A *schema* is a data structure matching the general expected
shape of *d*, where the values are dicts, lists, and
callables.  The transformation is similar to `map()`
except that individual values will have individual conversion
functions.  Also, a schema conversion function can be specified
for any value in *d*, even dicts or lists.

*default* is a default conversion function.  If there is a
value *v* in *d* that doesn't have an equivalent entry in *schema*,
and *v* is neither a list nor a dict, and if *default* is
a callable, *v* will be replaced with `default(v)` in the
output.

`Required`

Experimental.

`nullable(fn) -> fn`

Experimental.

`const(fn) -> o`

Experimental.


### TODO

* Backslash quoting currently does "whatever your version of Python does".  Perhaps this should be explicit, and parsed by Perky itself?

### Changelog

**0.9.2** *2023/07/22*

Extremely minor release.  No new features or bug fixes.

* Added GitHub Actions integration.  Tests and
  coverage are run in the cloud after every checkin.
  Thanks to [Dan Pope](https://github.com/lordmauve)
  for gently walking me through this!
* Fixed metadata in the `pyproject.toml` file.
* Dropped support for Python 3.5.  (I assumed I already
  had, but it was still listed as being supported
  in the project metadata.)
* Added badges for testing, coverage,
  and supported Python versions.


**0.9.1** *2023/07/03*

* API change: the `Parser` attribute `breadcrumbs` has been
  renamed to `stack`.  It was previously undocumented anyway,
  though as of 0.9.1 it's now documented.  The previous name
  `breadcrumbs` has been kept as an alias for now, but will
  be removed before 1.0.
* Added the `line_number` and `source` attributes to the
  `Parser` object, for the convenience of pragma handlers.
* Refactored `parser_include` slightly.  No change to
  functionality or behavior, just a small code cleanup pass.
* Added a "lines per second" output metric to the
  benchmark program.

**0.9** *2023/07/02*

Breaking API change: removed the `encoding` argument entirely.

* From this point forward, Perky only supports reading and
  writing files in
  [UTF-8](https://en.wikipedia.org/wiki/UTF-8).
  If you need to work with a different encoding, you'll have
  to handle loading it form and saving it to disk yourself.
  You'll have to use `loads` and `dumps` to handle converting
  between Perky string format and native Python objects.

* Optimized Perky some more.  It's roughly 11% faster than 0.8.1.

**0.8.2** *2023/06/30*

* Minor API changes:

  - You can now pass an `encoding` keyword argument
    into `pragma_include`.  This is now the only way
    to specify the encoding used to decode files
    loaded from disk by `pragma_include`.
  - Removed the (undocumented) `encoding` attribute
    of Perky's `Parser` object.
  - Removed the `encoding` parameter for `loads`.
  - The `encoding` parameter for `load` is now only
    used by `load` itself when loading the top-level
    Perky file.

**0.8.1** *2023/06/26*

* Whoops!  A major regression: I inadveretently changed the default
  conversion of non-string values from `str` to `repr`.  Bad move!
  `str` is much better.  Added a test so I don't do this again.

**0.8** *2023/06/25*

* Perky now explicitly performs its `isinstance` checks using
  `collections.abc.MutableMapping` and `collections.abc.MutableSequence`
  instead of `dict` and `list`.  This permits you to use
  your own mapping and sequence objects that *don't* inherit from
  `dict` and `list`.
* Renamed `PerkyFormatError` to `FormatError`.  The old name is
  supported for now, but please transition to the new name.
  The old name will be removed before 1.0.
* The "transformation" submodule is now deprecated and unsupported.
  Please either stop using it or fork and maintain it yourself.
  This includes `map`, `transform`, `Required`,
  `nullable`, and `const`.
* Perky now has a proper unit test suite, which it passes with 100%
  coverage--except for the unsupported `transform` submodule.
* While working towards 100% coverage, also cleaned up the code
  a little in spots.

  - Retooled `LineTokenizer`:

    - Changed its name from `LineParser` is now `LineTokenizer`.
      It never parsed anything, it just tokenized.
    - Made its API a little more uniform: now, the
      only function that will raise `StopIteration` is `__next__`.
    - The other functions that used to maybe raise `StopIteration`
      now return a tuple of `None` values when the iterator is empty.
      This means you can safely write `for a, b, c in line_tokenizer:`.
    - `bool(lt)` is now accurate; if it returns `True`,
      you can call `next(lt)` or `lt.next_line()` or `lt.tokens()`
      and be certain you'll get a value back.

  - Replaced `RuntimeError` exceptions with more appropriate
    exceptions (`ValueError`, `TypeError`).

# perky

## Because the world needed another configuration file format

##### Copyright 2018 by Larry Hastings


### Overview

Perky is a new, simple rcfile format for Python programs.

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

`perky.transform(d, schema) -> o`

Recursively transforms a Perky dict into some other
object (usually a dict) using the provided schema.

`perky.Required`

`perky.nullable(fn) -> fn`

`perky.const(fn) -> o`


### TODO

* Backslash quoting currently does "whatever your version of Python does".  Perhaps this should be explicit, and parsed by Perky itself?

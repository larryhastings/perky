#
# tokenize.py
#
# Part of the "perky" Python library
# Copyright 2018-2023 by Larry Hastings
#

import ast
import collections
import sys


c_to_tokens = collections.defaultdict(list)
tokens = {}
# token_to_name = {}


def token(s, description):
    base = description.replace(" ", "_")
    token = "<" + base + "_token>"
    name = base.upper()

    tokens[token] = (name, s)
    # token_to_name[token] = name

    if s:
        value = (token, s)
        c_to_tokens[s[0]].append(value)

    return token

# abstract tokens
WHITESPACE            = token(None, 'whitespace')
STRING                = token(None, 'string')
COMMENT               = token(None, 'comment')

NUMBER_SIGN           = token('#', 'number sign')
EQUALS                = token('=', 'equals')
LEFT_CURLY_BRACE      = token('{', 'left curly brace')
RIGHT_CURLY_BRACE     = token('}', 'right curly brace')
LEFT_SQUARE_BRACKET   = token('[', 'left square bracket')
RIGHT_SQUARE_BRACKET  = token(']', 'right square bracket')
SINGLE_QUOTE          = token("'", 'single quote')
DOUBLE_QUOTE          = token('"', 'double quote')
TRIPLE_SINGLE_QUOTE   = token("'''", 'triple single quote')
TRIPLE_DOUBLE_QUOTE   = token('"""', 'triple double quote')
EMPTY_CURLY_BRACES    = token('{}', 'empty curly braces')
EMPTY_SQUARE_BRACKETS = token('[]', 'empty square brackets')

non_quoting_operators = set(c for c in c_to_tokens if c not in ('"', "'"))
# non_quoting_operators = "".join(c for c in c_to_tokens if c not in ('"', "'"))

# c_to_tokens maps characters to lists of tokens that start with that charcter.
# It's always true that there are either exactly zero, one, or two tokens that
# start with any particular character.  If there are two, it's always true that
# the two tokens are different lengths, and the shorter token is exactly one
# character long.
#
# Sort the list of tokens by length, longest first, and also verify these
# invariants.
for value in c_to_tokens.values():
    length = len(value)
    assert 1 <= length <= 2
    if len(value) == 2:
        value.sort(key=lambda o:len(o[0]), reverse=True)
        assert len(value[0][1]) > 1, f"unexpected value {value}, should be a token of 2 or more characters"
        assert len(value[1][1]) == 1, f"unexpected value {value}, should be a token that is a single character"

_sentinel = object()

class pushback_str_iterator:
    """
    A specialized iterator for strings that permits a
    form of rewinding: while iterating over a string,
    you can "push" strings back onto the iterator,
    which will be yielded first.  (The pushed-back
    strings go on a stack, and are LIFO.)  Technically
    you can "push" any string, though in practice Perky
    only pushes back values yielded by the iterator.
    """

    # look! a go-faster stripe!
    __slots__ = ('i', 'stack', 'push_c')

    def __init__(self, s):
        # iterate over s
        self.i = iter(s)

        # but maintain a stack for pushbacks
        self.stack = []

        # Optimized version of push that only handles strings of length 1.
        # Most of the time, Perky pushes individual characters, and push_c
        # is much faster than push.  This optimization brings a measurable
        # performance gain.  (Between this and switching to slots, I saw a
        # 22% *overall* improvement in Perky!)
        #
        # This method would be unsafe for public use; it doesn't validate
        # its input.  Calling push_c with something besides a length-1 string
        # will result in it yielding garbage.  But pushback_str_iterator
        # is an internal data structure, unsupported for public use, and
        # Perky is careful.  So it's fine.
        self.push_c = self.stack.append

    def reset(self, s):
        self.i = iter(s)
        self.stack.clear()

    def __repr__(self):
        return f'<pushback i={self.i} stack={list(self.stack)}>'

    def push(self, s):
        """
        Pushes a string (or list) back onto the iterator.

        The following code:
            i = pushback_str_iterator('XY')
            print(next(i))
            i.push('abcde')
            for c in i:
                print(c)

        prints 'X', 'a', 'b', 'c', 'd', 'e', and 'Y'
        in that order.
        """
        if len(s) == 1:
            self.push_c(s[0])
            return
        self.stack.extend(reversed(s))

    def __next__(self):
        if self.stack:
            s = self.stack.pop()
            return s
        if not self.i:
            raise StopIteration
        try:
            s = next(self.i)
            return s
        except StopIteration as e:
            self.i = None
            raise e

    def __iter__(self):
        return self

    def __bool__(self):
        if self.stack:
            return True
        if not self.i:
            return False

        c = next(self.i, _sentinel)
        if c is _sentinel:
            self.i = None
            return False
        self.push_c(c)
        return True

    def drain(self):
        """
        Return all remaining characters as a string.
        """
        if self.stack:
            s = "".join(reversed(self.stack))
            self.stack.clear()
        else:
            s = ""

        if self.i:
            t = "".join(self.i)
            if s:
                s += t
            else:
                s = t
            self.i = None

        return s


def tokenize(i, suppress_whitespace=True):
    """
    Tokenizer for individual lines of a Perky file.
    Hand-written, designed specifically for Perky syntax.

    i should be a pushback_str_iterator iterating over the
    string you want tokenized.

    This function is a generator; it yields tokens from
    the line until the line is exhausted.

    If suppress_whitespace is true (the default),
    this generator will not yield WHITESPACE tokens.
    (Trailing whitespace is generally discarded anyway.)
    """

    # cache looked-up methods in fast locals
    i_push = i.push
    i_push_c = i.push_c

    buffer = []
    buffer_append = buffer.append
    buffer_clear = buffer.clear

    empty_string_join = "".join

    for c in i:
        if c.isspace():
            if buffer:
                buffer_clear()
            buffer_append(c)
            for c in i:
                if not c.isspace():
                    i_push_c(c)
                    break
                buffer_append(c)
            if not suppress_whitespace:
                yield (WHITESPACE, empty_string_join(buffer))
            continue

        candidates = c_to_tokens.get(c, None)
        if candidates:
            if len(candidates) == 1:
                t = candidates[0]
            else:
                multi, single = candidates
                multi_string = multi[1]
                if buffer:
                    buffer_clear()
                buffer_append(c)
                for c in i:
                    buffer_append(c)
                    if len(buffer) == len(multi_string):
                        break
                token = empty_string_join(buffer)
                if token == multi_string:
                    t = multi
                else:
                    t = single
                    i_push(token)
                    # now throw away c, we just pushed it again
                    c = next(i)

            token, s = t

            if token is NUMBER_SIGN:
                yield (COMMENT, i.drain())
                return

            if (token is SINGLE_QUOTE) or (token is DOUBLE_QUOTE):
                # Parse a quoted string.  The ending quote
                # must match the starting quote character
                # passed in.  Handles all the Python escape
                # sequences: all the single-character ones,
                # octal, and the extra-special x u U N ones.
                if buffer:
                    buffer_clear()
                quote = c
                buffer_append(quote)
                backslash = False
                for c in i:
                    if c == '\\':
                        backslash = not backslash
                        continue
                    if backslash:
                        buffer_append('\\')
                    elif c == quote:
                        buffer_append(quote)
                        break
                    buffer_append(c)
                    backslash = False

                s = ast.literal_eval(empty_string_join(buffer))
                yield (STRING, s)
                continue

            if (token is TRIPLE_SINGLE_QUOTE) or (token is TRIPLE_DOUBLE_QUOTE):
                # triple quote MUST be last thing on line (except possibly-ignored trailing whitespace)
                trailing = i.drain()
                if trailing and not trailing.isspace():
                    raise ValueError("tokenizer found triple-quote followed by non-whitespace string " + repr(trailing))
                yield t
                return

            token_is_left_curly_brace = token is LEFT_CURLY_BRACE
            if token_is_left_curly_brace or (token is LEFT_SQUARE_BRACKET):
                # handle flattening [] and [   ] into a EMPTY_SQUARE_BRACKETS token
                # (and similarly for {} and { } and EMPTY_CURLY_BRACES)
                if token_is_left_curly_brace:
                    right_bracket = '}'
                    empty_brackets = (EMPTY_CURLY_BRACES, '{}')
                else:
                    right_bracket = ']'
                    empty_brackets = (EMPTY_SQUARE_BRACKETS, '[]')
                if buffer:
                    buffer_clear()
                for c in i:
                    if c.isspace():
                        buffer_append(c)
                        continue
                    if c == right_bracket:
                        t = empty_brackets
                        break
                    i_push_c(c)
                    i_push(buffer)
                    break

            yield t
            continue

        # Parse an unquoted string.
        # Note that it *is* permitted to have spaces.
        #
        # Returns the unquoted string.
        # If there were no characters to be read, returns an
        # empty string.
        # Note that trailing whitespace is stripped.
        # (If you want trailing whitespace preserved,
        # use a quoted string.)
        #
        # Stops the unquoted string at EOL, or the first
        # character used in Perky syntax (=, {, [, etc).
        # (If you need to use one of those inside your string,
        # use a quoted string.)
        if buffer:
            buffer_clear()
        i_push_c(c)
        for c in i:
            if c in non_quoting_operators:
                i_push_c(c)
                break
            buffer_append(c)
        s = empty_string_join(buffer).rstrip()
        yield (STRING, s)


class LineTokenizer:
    """
    A simple tokenizing iterator for Perky.
    It's line-oriented; you can get the next
    line either as a string, or as a sequence
    of tokens.
    """

    # go-faster stripe!
    __slots__ = ('_lines', 'source', 'suppress_whitespace', 'waiting', 'line_number', '_repr', 'i')

    def __init__(self, s, suppress_whitespace=True, source='<string>'):
        lines = s.split("\n")
        self._lines = enumerate(lines, 1)
        self.suppress_whitespace = suppress_whitespace
        self.waiting = None
        self.source = source
        self.line_number = 0

        repr_lines = str(lines[:5])
        if len(repr_lines) > 50:
            repr_lines = repr_lines[:47] + "..."
        self._repr = f"<LineTokenizer '{self.source}' {{self.line_number}}/{len(lines)} lines {repr_lines}>"

        self.i = pushback_str_iterator('')

    def __repr__(self):
        return self._repr.format(self=self)

    def __iter__(self):
        return self

    def __bool__(self):
        if self.waiting is not None:
            return True
        if self._lines is None:
            return False

        result = next(self._lines, _sentinel)
        if result is _sentinel:
            self._lines = self.waiting = None
            return False
        self.waiting = result
        return True

    def next_line(self):
        """
        Returns the 2-tuple
            line_number, line

        If the iterator is exhausted,
        does *not* raise StopIteration.
        Instead, it returns (None, None).
        """
        failure = (None, None)

        if self.waiting is not None:
            t = self.waiting
            self.waiting = None
        else:
            if self._lines is None:
                return failure
            t = next(self._lines, _sentinel)
            if t is _sentinel:
                self._lines = None
                return failure

        self.line_number = t[0]
        return t

    def tokens(self):
        """
        Returns the 3-tuple
            line_number, line, tokens

        If the iterator is exhausted,
        does *not* raise StopIteration.
        Instead, it returns (None, None, None).
        """
        failure = (None, None, None)

        if self.waiting is not None:
            t = self.waiting
            self.waiting = None
        else:
            if self._lines is None:
                return failure
            t = next(self._lines, _sentinel)
            if t is _sentinel:
                self._lines = None
                return failure

        line_number, line = t
        self.line_number = line_number
        i = self.i
        i.reset(line)
        tokens = list(tokenize(i, suppress_whitespace=self.suppress_whitespace))
        return (line_number, line, tokens)

    def __next__(self):
        t = self.tokens()
        if t == (None, None, None):
            raise StopIteration()
        return t

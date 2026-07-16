#
# tokenize.py
#
# Part of the "perky" Python library
# Copyright 2018-2026 by Larry Hastings
#

from big.builtin import literal_eval
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

    Deprecated.  Perky's tokenizer no longer iterates
    character by character, so it no longer needs pushback;
    nothing in Perky uses this class anymore.  It'll be
    removed before 1.0.
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


def tokenize(s, suppress_whitespace=True):
    """
    Tokenizer for individual lines of a Perky file.
    Hand-written, designed specifically for Perky syntax.

    s should be the line you want tokenized: a str,
    or a big.string if you want the tokens to know
    where they came from.

    This function is a generator; it yields tokens from
    the line until the line is exhausted.

    Token values are always slices of s.  So if s is a
    big.string, every token value--including the decoded
    value of a quoted string--knows its own source, line,
    and column.

    If suppress_whitespace is true (the default),
    this generator will not yield WHITESPACE tokens.
    (Trailing whitespace is generally discarded anyway.)
    """

    # We scan the plain-str version of the line--at C speed--
    # and slice tokens out of s itself, by position.  Slicing
    # is the only operation here that manufactures new string
    # objects.  So when s is a big.string, we pay for one
    # provenance-tracking object per *token*, instead of one
    # per *character*.  (An earlier version of this tokenizer
    # iterated over the line character by character, collecting
    # characters in a buffer; iterating a big.string manufactures
    # a provenance-tracking object for every character, which
    # made that design roughly 3x slower.)
    raw = str(s)
    length = len(raw)
    pos = 0

    while pos < length:
        c = raw[pos]

        if c.isspace():
            start = pos
            pos += 1
            while (pos < length) and raw[pos].isspace():
                pos += 1
            if not suppress_whitespace:
                yield (WHITESPACE, s[start:pos])
            continue

        candidates = c_to_tokens.get(c, None)
        if candidates:
            if len(candidates) == 1:
                t = candidates[0]
            else:
                # two candidates.  they're sorted longest first,
                # and the shorter one is always exactly one character.
                multi, single = candidates
                t = multi if raw.startswith(multi[1], pos) else single

            token, token_string = t

            if token is NUMBER_SIGN:
                yield (COMMENT, s[pos + 1:])
                return

            if (token is SINGLE_QUOTE) or (token is DOUBLE_QUOTE):
                # Parse a quoted string.  The ending quote must match
                # the starting quote character.  We scan *verbatim*--
                # including backslash escapes--until the matching
                # unescaped closing quote, then let literal_eval do
                # all the unescaping.  literal_eval handles every
                # Python escape sequence: the single-character ones,
                # octal, and the special x u U N ones.
                #
                # The 'backslash' flag only tracks whether the next
                # character is escaped, so that an escaped quote (\")
                # doesn't end the string and an escaped backslash (\\)
                # doesn't escape the character after it.  (An earlier
                # version tried to rewrite escapes by hand here, and
                # silently ate '\\' down to nothing.)
                j = pos + 1
                backslash = False
                terminated = False
                while j < length:
                    ch = raw[j]
                    j += 1
                    if backslash:
                        backslash = False
                        continue
                    if ch == '\\':
                        backslash = True
                        continue
                    if ch == c:
                        terminated = True
                        break
                if not terminated:
                    fragment = s[pos:]
                    where = getattr(fragment, 'where', None)
                    prefix = f"{where}: " if where else ""
                    raise ValueError(f"{prefix}unterminated quoted string: {str(fragment)}")

                # big.types.literal_eval: if s is a big.string, the
                # decoded value comes back knowing its own position.
                yield (STRING, literal_eval(s[pos:j]))
                pos = j
                continue

            if (token is TRIPLE_SINGLE_QUOTE) or (token is TRIPLE_DOUBLE_QUOTE):
                # triple quote MUST be last thing on line (except possibly-ignored trailing whitespace)
                trailing = raw[pos + 3:]
                if trailing and not trailing.isspace():
                    raise ValueError("tokenizer found triple-quote followed by non-whitespace string " + repr(trailing))
                # yield the marker as a slice of s, not the constant--
                # so an "unterminated triple-quoted block" error can
                # point at the opening quote.
                yield (token, s[pos:pos + 3])
                return

            pos += len(token_string)

            if (token is LEFT_CURLY_BRACE) or (token is LEFT_SQUARE_BRACKET):
                # handle flattening [] and [   ] into a EMPTY_SQUARE_BRACKETS token
                # (and similarly for {} and { } and EMPTY_CURLY_BRACES)
                if token is LEFT_CURLY_BRACE:
                    right_bracket = '}'
                    empty_brackets = (EMPTY_CURLY_BRACES, '{}')
                else:
                    right_bracket = ']'
                    empty_brackets = (EMPTY_SQUARE_BRACKETS, '[]')
                j = pos
                while (j < length) and raw[j].isspace():
                    j += 1
                if (j < length) and (raw[j] == right_bracket):
                    t = empty_brackets
                    pos = j + 1

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
        start = pos
        pos += 1
        while (pos < length) and (raw[pos] not in non_quoting_operators):
            pos += 1
        yield (STRING, s[start:pos].rstrip())


class LineTokenizer:
    """
    A simple tokenizing iterator for Perky.
    It's line-oriented; you can get the next
    line either as a string, or as a sequence
    of tokens.
    """

    # go-faster stripe!
    __slots__ = ('_lines', 'source', 'suppress_whitespace', 'waiting', 'line_number', '_repr')

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
        tokens = list(tokenize(line, suppress_whitespace=self.suppress_whitespace))
        return (line_number, line, tokens)

    def __next__(self):
        t = self.tokens()
        if t == (None, None, None):
            raise StopIteration()
        return t

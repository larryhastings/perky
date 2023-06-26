#
# tokenize.py
#
# Part of the "perky" Python library
# Copyright 2018-2023 by Larry Hastings
#

import ast
import collections
import sys


token_first_characters = set()
c_to_tokens = collections.defaultdict(list)
s_to_token = {}
tokens = {}
token_to_name = {}


def token(s, description):
    base = description.strip().lower().replace(" ", "_")
    token = "<" + base + "_token>"
    name = base.upper()

    tokens[token] = (name, s)
    token_to_name[token] = name

    if s:
        value = (token, s)
        c_to_tokens[s[0]].append(value)
        s_to_token[s] = value

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

single_quote_tokens = set((SINGLE_QUOTE, DOUBLE_QUOTE))
triple_quote_tokens = set((TRIPLE_SINGLE_QUOTE, TRIPLE_DOUBLE_QUOTE))
left_bracket_tokens = set((LEFT_SQUARE_BRACKET, LEFT_CURLY_BRACE))
left_bracket_to_right_bracket = {
    '[': ']',
    '{': '}',
}
left_bracket_to_empty_bracket_token = {
    '[': (EMPTY_SQUARE_BRACKETS, '[]'),
    '{': (EMPTY_CURLY_BRACES, '{}'),
}

non_quoting_operators = set(c for c in c_to_tokens if c not in ('"', "'"))

# sort tokens in c_to_tokens by length, longest first
for value in c_to_tokens.values():
    value.sort(key=lambda o:len(o[0]), reverse=True)
    # the parsing code is special-cased to assume:
    #   * there are either one or two possible tokens for each initial character
    #   * if there are two, the first token is always multiple characters
    #     and the second token is always a single character
    assert 1 <= len(value) <= 2
    if len(value) == 2:
        assert len(value[0][1]) > 1, f"unexpected value {value}"
        assert len(value[1][1]) == 1, f"unexpected value {value}"

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
    __slots__ = ('i', 'stack')

    def __init__(self, s):
        # iterate over s
        self.i = iter(s)
        # but maintain a stack for pushbacks
        self.stack = []

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
        # assert isinstance(s, (str, list)), f"expected str or list, got s={s} (type(s)={type(s)})"
        if len(s) == 1:
            self.stack.append(s[0])
            return
        self.stack.extend(reversed(s))

    def push_c(self, c):
        """
        Optimized version of push that only handles strings of length 1.
        Most of the time, Perky pushes individual characters, and push_c
        is much faster than push.  This optimization brings a measurable
        performance gain.  (Between this and switching to slots, I saw a
        22% *overall* improvement in Perky!)

        This method would be unsafe for public use; it doesn't validate
        its input.  Calling push_c with something besides a length-1 string
        will result in it yielding garbage.  But pushback_str_iterator
        is an internal data structure, unsupported for public use, and
        Perky is careful.  So it's fine.
        """
        # assert isinstance(c, str) and (len(c) == 1), f"expected str of len 1, got c={c} (type(c)={type(c)})"
        self.stack.append(c)

    def __next__(self):
        if self.stack:
            x = self.stack.pop()
            return x
        if not self.i:
            raise StopIteration
        try:
            x = next(self.i)
            return x
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

        try:
            c = next(self.i)
            self.push_c(c)
            return True
        except StopIteration:
            self.i = None
            return False

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

    This function is a generator; it yields tokens from
    the line until the line is exhausted.

    If suppres_whitespace is true (the default),
    this generator will not yield WHITESPACE tokens.
    (Trailing whitespace is generally discarded anyway.)
    """

    # assert "\n" not in s

    i = pushback_str_iterator(s)

    def parse_unquoted_string():
        """
        Parse an unquoted string.
        Note that it *is* permitted to have spaces.

        Returns the unquoted string.
        If there were no characters to be read, returns an
        empty string.
        Note that trailing whitespace is stripped.
        (If you want trailing whitespace preserved,
        use a quoted string.)

        Stops the unquoted string at EOL, or the first
        character used in Perky syntax (=, {, [, etc).
        (If you need to use one of those inside your string,
        use a quoted string.)

        """
        buffer = []
        for c in i:
            if c in non_quoting_operators:
                i.push_c(c)
                break
            buffer.append(c)
        return "".join(buffer).rstrip()

    def parse_quoted_string(quote):
        """
        Parse a quoted string.  The ending quote
        must match the starting quote character
        passed in.  Handles all the Python escape
        sequences: all the single-character ones,
        octal, and the extra-special x u U N ones.
        """
        buffer = [quote]
        backslash = False
        for c in i:
            if c == '\\':
                backslash = not backslash
                continue
            if (c == quote) and (not backslash):
                buffer.append(quote)
                break
            if backslash:
                buffer.append('\\')
            buffer.append(c)
            backslash = False

        return ast.literal_eval("".join(buffer))

    for c in i:
        if c.isspace():
            whitespace = [c]
            for c in i:
                if not c.isspace():
                    i.push_c(c)
                    break
                whitespace.append(c)
            if not suppress_whitespace:
                yield WHITESPACE, "".join(whitespace)
            continue

        t = c_to_tokens.get(c, None)
        if t:
            if len(t) > 1:
                multi, single = t
                multi_string = multi[1]
                token = [c]
                for c in i:
                    token.append(c)
                    if len(token) == len(multi_string):
                        break
                token = "".join(token)
                if token == multi_string:
                    t = multi
                else:
                    t = single
                    i.push(token)
                    # now throw away c, we just pushed it again
                    c = next(i)
            else:
                t = t[0]

            token, s = t

            if token == NUMBER_SIGN:
                yield COMMENT, i.drain()
                return

            if token in single_quote_tokens:
                yield STRING, parse_quoted_string(c)
                continue

            if token in triple_quote_tokens:
                # triple quote MUST be last thing on line (except possibly-ignored trailing whitespace)
                trailing = i.drain()
                if trailing and not trailing.isspace():
                    raise ValueError("tokenizer found triple-quote followed by non-whitespace string " + repr(trailing))
                yield t
                # don't yield trailing whitespace here--we never do anywhere else!
                # if trailing and not suppress_whitespace:
                #     yield WHITESPACE, trailing
                return

            if token in left_bracket_tokens:
                # handle flattening [] and [   ] into a EMPTY_SQUARE_BRACKETS token
                # (and similarly for {} and { } and EMPTY_CURLY_BRACES)
                right_bracket = left_bracket_to_right_bracket[s]
                characters = []
                for c in i:
                    if c.isspace():
                        characters.append(c)
                        continue
                    if c == right_bracket:
                        t = left_bracket_to_empty_bracket_token[s]
                        break
                    i.push_c(c)
                    i.push(characters)
                    break

            yield t
            continue

        i.push_c(c)
        s = parse_unquoted_string()
        yield STRING, s


class LineTokenizer:
    """
    A simple tokenizing iterator for Perky.
    It's line-oriented; you can get the next
    line either as a string, or as a sequence
    of tokens.
    """

    def __init__(self, s, suppress_whitespace=True):
        lines = s.split("\n")
        self._lines = enumerate(lines, 1)
        self.suppress_whitespace = suppress_whitespace
        self.waiting = None
        self.line_number = 0

        repr_lines = str(lines[:5])
        if len(repr_lines) > 50:
            repr_lines = repr_lines[:47] + "..."
        self._repr = f"<LineTokenizer {{self.line_number}}/{len(lines)} lines {repr_lines}>"

    def __repr__(self):
        return self._repr.format(self=self)

    def __iter__(self):
        return self

    def __bool__(self):
        if self.waiting is not None:
            return True
        if self._lines is None:
            return False

        try:
            self.waiting = next(self._lines)
            return True
        except StopIteration:
            self._lines = self.waiting = None
            return False

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
            try:
                t = next(self._lines)
            except StopIteration as e:
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
            try:
                t = next(self._lines)
            except StopIteration as e:
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

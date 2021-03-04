#
# tokenize.py
#
# Part of the "perky" Python library
# Copyright 2018-2021 by Larry Hastings
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
    def __init__(self, s):
        # self.iterators is a stack, growing to the right.
        # each entry is an iterator that yields individual
        # characters.
        # remove iterators from the end (-1) and yield
        # until exhausted.
        self.iterators = [iter(s)]

    def __repr__(self):
        return f'<pushback {len(self.iterators)!r} iterators>'

    def push(self, s):
        self.iterators.append(iter(s))

    def __next__(self):
        # the general case here is that the first
        # iterator we try works.  so, instead of
        # a "while True" loop that we nearly never
        # loop on, use recursion to handle the
        # edge case where the top iterator
        # is exhausted.
        if not self.iterators:
            raise StopIteration()
        try:
            i = self.iterators[-1]
            return next(i)
        except StopIteration:
            self.iterators.pop()
            return self.__next__()

    def __iter__(self):
        return self

    def __bool__(self):
        # can't just return bool(self.iterators),
        # as all the iterators in that list might
        # be exhausted.
        try:
            c = next(self)
            self.push(c)
            return True
        except StopIteration:
            return False

    def drain(self):
        """
        Return all remaining characters as a string.
        """
        strings = ["".join(i) for i in reversed(self.iterators)]
        s = "".join(strings)
        self.iterators.clear()
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
                i.push(c)
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

        try:
            return ast.literal_eval("".join(buffer))
        except SyntaxError as e:
            raise e

    for c in i:
        if c.isspace():
            whitespace = [c]
            for c in i:
                if not c.isspace():
                    i.push(c)
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
                    for c in reversed(token):
                        i.push(c)
                    # now throw away c, we just pushed it again
                    next(i)
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
                    raise RuntimeError("tokenizer: found triple-quote followed by non-whitespace string " + repr(trailing))
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
                    i.push(c)
                    for c in reversed(characters):
                        i.push(c)
                    break

            yield t
            continue

        i.push(c)
        s = parse_unquoted_string()
        yield STRING, s


class LineParser:

    def __init__(self, s, suppress_whitespace=True):
        self._lines = s.split("\n")
        self.lines = enumerate(self._lines, 1)
        self.suppress_whitespace = suppress_whitespace

    def __repr__(self):
        return f"<LineParser {self._lines}>"

    def __iter__(self):
        return self

    def __bool__(self):
        return bool(self.lines)

    def next_line(self):
        line_number, line = next(self.lines)
        self.line_number = line_number
        return line

    def tokens(self):
        while self.lines:
            line = self.line = self.next_line()
            l = list(tokenize(line, suppress_whitespace=self.suppress_whitespace))
            if l:
                return l, line
            if l is None:
                return None
        return None

    def __next__(self):
        while True:
            t = self.tokens()
            if t is None:
                raise StopIteration()
            return t

if __name__ == "__main__":
    want_print = "-v" in sys.argv
    # want_print = True
    test_number = 1
    def _test(s, tokens_and_values, suppress_whitespace):
        global test_number
        def fail(message):
            print(message)
            print("s:", repr(s))
            print("tokens_and_values:", tokens_and_values)
            sys.exit(-1)
        tokens = []
        values = []
        tokens_with_values = set((STRING, COMMENT))
        expect_token = True
        for t in tokens_and_values:
            is_token = token_to_name.get(t)
            if expect_token:
                assert is_token, "expected token, got " + str(t)
                tokens.append(t)
                if t in tokens_with_values:
                    expect_token = False
            else:
                values.append(t)
                expect_token = True
        if want_print:
            if suppress_whitespace is None:
                suffix = ""
            else:
                modifier = "suppressing" if suppress_whitespace else "keeping"
                suffix = f", {modifier} whitespace tokens"
            print(f"test #{test_number}{suffix}:\n  input:\n\t", repr(s), "\n  should match:\n\t", " ".join(x if x in token_to_name else repr(x) for x in tokens_and_values))
            test_number += 1
            print()
        for tok, s in tokenize(s, suppress_whitespace=suppress_whitespace):
            t = tokens.pop(0)
            if want_print:
                print("  [want]", t, end="")
            if tok in tokens_with_values:
                v = values.pop(0)
                print(f" {s!r}")
            else:
                print()
                v = None
            if want_print:
                print("  [ got]", tok, repr(s))
            if tok != t:
                fail("token doesn't match, expected " + str(token_to_name[t]) + " got " + str(token_to_name.get(tok)))
            if (v is not None) and (v != s):
                fail("token value doesn't match, expected " + repr(v) + " got " + repr(s))

        if want_print:
            print()

    def test(s, *tokens_and_values):
        without_whitespace = tuple(x for x in tokens_and_values if x != WHITESPACE)
        tests_differ = without_whitespace != tokens_and_values
        if tests_differ:
            _test(s, tokens_and_values, suppress_whitespace=False)
            _test(s, without_whitespace, suppress_whitespace=True)
        else:
            _test(s, without_whitespace, suppress_whitespace=None) # dumb flag!

    test(r"hey party people ", STRING, "hey party people")
    test(r"  hey party people ", WHITESPACE, STRING, "hey party people")
    test(r"# hey party people ", COMMENT, " hey party people ")
    test(r" # hey party people ", WHITESPACE, COMMENT, " hey party people ")
    test(r""" "quoted \u1234 string" """, WHITESPACE, STRING, "quoted \u1234 string", WHITESPACE)
    test(r""" "quoted \N{END OF LINE} string" """, WHITESPACE, STRING, "quoted \n string", WHITESPACE)
    test(r""" "quoted string" = value """, WHITESPACE, STRING, "quoted string", WHITESPACE, EQUALS, WHITESPACE, STRING, "value", WHITESPACE)
    test(r""" "quoted string"=value """, WHITESPACE, STRING, "quoted string", EQUALS, STRING, "value", WHITESPACE)
    test(r""" "quoted string"={""", WHITESPACE, STRING, "quoted string", EQUALS, LEFT_CURLY_BRACE)
    test(r""" "quoted string" = {""", WHITESPACE, STRING, "quoted string", WHITESPACE, EQUALS, WHITESPACE, LEFT_CURLY_BRACE)
    test(r""" "quoted string"=[""", WHITESPACE, STRING, "quoted string", EQUALS, LEFT_SQUARE_BRACKET)
    test(r""" "quoted string" = [""", WHITESPACE, STRING, "quoted string", WHITESPACE, EQUALS, WHITESPACE, LEFT_SQUARE_BRACKET)
    test(r"x=y", STRING, "x", EQUALS, STRING, "y")
    test(r"x={", STRING, "x", EQUALS, LEFT_CURLY_BRACE)
    test(r"x=[", STRING, "x", EQUALS, LEFT_SQUARE_BRACKET)
    test(r'''x="quoted string"''', STRING, "x", EQUALS, STRING, "quoted string")

    test(r'''[]''', EMPTY_SQUARE_BRACKETS)
    test(r'''[ ]''', EMPTY_SQUARE_BRACKETS)
    test(r'''{}''', EMPTY_CURLY_BRACES)
    test(r'''{ }''', EMPTY_CURLY_BRACES)

    # and now, the big finish
    test(r""" 'quoted string' "quoted string 2" [ { = "quoted value" [ { ] } = "yes!" [{}] ''' """,
        WHITESPACE,
        STRING, "quoted string",
        WHITESPACE,
        STRING, "quoted string 2",
        WHITESPACE,
        LEFT_SQUARE_BRACKET,
        WHITESPACE,
        LEFT_CURLY_BRACE,
        WHITESPACE,
        EQUALS,
        WHITESPACE,
        STRING, "quoted value",
        WHITESPACE,
        LEFT_SQUARE_BRACKET,
        WHITESPACE,
        LEFT_CURLY_BRACE,
        WHITESPACE,
        RIGHT_SQUARE_BRACKET,
        WHITESPACE,
        RIGHT_CURLY_BRACE,
        WHITESPACE,
        EQUALS,
        WHITESPACE,
        STRING, "yes!",
        WHITESPACE,
        LEFT_SQUARE_BRACKET,
        EMPTY_CURLY_BRACES,
        RIGHT_SQUARE_BRACKET,
        WHITESPACE,
        TRIPLE_SINGLE_QUOTE,
        WHITESPACE,
        )

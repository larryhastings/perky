#
# tokenize.py
#
# Part of the "perky" Python library
# Copyright 2018 by Larry Hastings
#

import ast
import sys

WHITESPACE = '<whitespace>'
STRING = '<string>'
EQUALS = '<equals>'
LEFT_CURLY_BRACE = '<left_curly_brace>'
RIGHT_CURLY_BRACE = '<right_curly_brace>'
LEFT_SQUARE_BRACKET = '<left_square_bracket>'
RIGHT_SQUARE_BRACKET = '<right_square_bracket>'
COMMENT = '<comment>'
TRIPLE_SINGLE_QUOTE = "<triple_single_quote>"
TRIPLE_DOUBLE_QUOTE = '<triple_double_quote>'

c_to_token = {
    '=': EQUALS,
    '{': LEFT_CURLY_BRACE,
    '}': RIGHT_CURLY_BRACE,
    '[': LEFT_SQUARE_BRACKET,
    ']': RIGHT_SQUARE_BRACKET,
    '#': COMMENT,
}

c_to_triple_quote = {
    "'": TRIPLE_SINGLE_QUOTE,
    '"': TRIPLE_DOUBLE_QUOTE,
}


token_to_name = {
    WHITESPACE: "WHITESPACE",
    STRING: "STRING",
    EQUALS: "EQUALS",
    LEFT_CURLY_BRACE: "LEFT_CURLY_BRACE",
    RIGHT_CURLY_BRACE: "RIGHT_CURLY_BRACE",
    LEFT_SQUARE_BRACKET: "LEFT_SQUARE_BRACKET",
    RIGHT_SQUARE_BRACKET: "RIGHT_SQUARE_BRACKET",
    COMMENT: "COMMENT",
    TRIPLE_SINGLE_QUOTE: "TRIPLE_SINGLE_QUOTE",
    TRIPLE_DOUBLE_QUOTE: "TRIPLE_DOUBLE_QUOTE",
}


class pushback_str_iterator:
    def __init__(self, s):
        self.characters = list(reversed(s))

    def __repr__(self):
        contents = "".join(reversed(self.characters))
        return f'<pushback {contents!r}>'

    def push(self, s):
        # print("PUSH ->", repr(s))
        for c in s:
            self.characters.append(c)

    def __next__(self):
        # print("I -> ", self.characters)
        if not self.characters:
            raise StopIteration()
        return self.characters.pop()

    def __iter__(self):
        return self

    def __bool__(self):
        return bool(self.characters)

    def drain(self):
        """
        Return all remaining characters as a string.
        """
        s = "".join(reversed(self.characters))
        self.characters.clear()
        return s



def microtokenizer(s):
    """
    Breaks up a string into pre-tokens for the proper tokenizer to digest.
    """

    tokens = []
    token = []
    score = None

    def flush():
        if token:
            tokens.append(''.join(token))
            token.clear()

    for c in s:
        c_score = score_character(c)
        if score != c_score:
            flush()
            score = c_score
        token.append(c)
    flush()

    return tokens


def tokenize(s, skip_whitespace=True, in_dict=False):
    """
    Tokenizes a line.  Handles two types of lines:
        * lines in a dict
            name = value
        * lines in a list
            value

    Returns a list of tokens.  Each token is a tuple
    of length two: the first element is one of the
    predefined tokens at the top of this file, and
    the second is the "value" of that token (e.g
    if the token is STRING, value is the value of
    that string).

    There's a little context smarts necessary here.
    For a dict line, the first = delimits the name,
    and all subsequent unquoted = are part of an
    unquoted string (if that's the value).
    For a list line, all = are part of the unquoted
    string.  Similarly, if you're already in an
    unquoted string, { and [ and ' and " and even '''
    aren't special.
    """

    i = pushback_str_iterator(s)

    def parse_unquoted_string():
        """
        Parse an unquoted string.  In Perky, this is a string
        without quote marks, but *with* spaces.  The string
        stops at the first (unquoted) equals sign.

        Returns the unquoted string parsed.
        If there were no characters to be read, returns an
        empty string.

        The first character of an unquoted string cannot be
        a quote character.  After that, quote characters
        are permitted, e.g.
            that's a nice hat
        So, ' " [ { and even ''' and even... uh, the other
        one (" " ") aren't special inside an unquoted string.

        That's fine, unquoted strings are only delimited by
        EOL and =.  Except... = should also work in unquoted
        strings when they are values!  This is why we have
        this slightly-messy in_dict hack. For dict lines,
        unquoted strings should be delimited by EOL, *and*
        if they're the *first* token on the line they should
        also be delimited by = .

        """
        nonlocal in_dict
        buffer = []
        for c in i:
            if (in_dict and c == '='):
                in_dict = False
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
            if backslash:
                backslash = False
            elif c == '\\':
                backslash = True
                continue
            buffer.append(c)
            if c == quote:
                break

        try:
            return ast.literal_eval("".join(buffer))
        except SyntaxError as e:
            print("FAILED AT BUFFER", buffer)
            raise e


    # turn off in_dict after the first token
    in_dict_countdown = 2

    def flush():
        t = "".join(token)
        token.clear()
        return t

    whitespace = None

    for c in i:

        token = [c]

        if c.isspace():
            # whitespace
            for c in i:
                if not c.isspace():
                    i.push(c)
                    break
                token.append(c)
            if not skip_whitespace:
                yield WHITESPACE, flush()
            continue

        if in_dict_countdown:
            in_dict_countdown -= 1
            if in_dict_countdown == 0:
                in_dict = False

        tok = c_to_token.get(c, None)
        if tok:
            if tok == COMMENT:
                yield COMMENT, i.drain()
                return

            yield tok, flush()
            continue

        tok = c_to_triple_quote.get(c, None)
        if tok:
            # it's a quote character, but is it a triple-quote?
            is_triple_quote = False
            if i:
                c2 = next(i)
                if i:
                    c3 = next(i)
                    is_triple_quote = c == c2 == c3
                    if not is_triple_quote:
                        i.push(c3)
                        i.push(c2)
                else:
                    i.push(c2)

            if is_triple_quote:
                # triple quote must be last thing on line (except maybe ignored trailing whitespace)
                trailing = i.drain()
                if trailing and not trailing.isspace():
                    raise RuntimeError("tokenizer: found triple-quote followed by non-whitespace string " + repr(trailing))
                yield tok, c*3
                if trailing:
                    yield WHITESPACE, trailing
                return

            yield STRING, parse_quoted_string(c)
            continue

        i.push(c)
        s = parse_unquoted_string()
        yield STRING, s

class LineParser:

    def __init__(self, s):
        self._lines = s.split("\n")
        self.lines = enumerate(self._lines)

    def __iter__(self):
        return self

    def __bool__(self):
        return bool(self.lines)

    def line(self):
        line_number, line = next(self.lines)
        self.line_number = line_number
        return line

    def tokens(self, in_dict=False):
        while self.lines:
            line = self.line()
            # print("TOKENS 221 LINE", self.line_number, repr(line))
            sys.stdout.flush()
            l = list(tokenize(line, skip_whitespace=True, in_dict=in_dict))
            if l:
                # print("LINE_NUMBER", self.line_number, "TOKENS", l)
                sys.stdout.flush()
                return l
        return None

    def __next__(self):
        while self.lines:
            yield self.tokens()


def tokens_match(tokens, *t):
    """
    tokens_match(tok, STRING, EQUALS, STRING)
    tok is a list, all subsequent arguments are tokens.
    returns True if the tok contains that list of tokens.
    (ignores the values of the tokens.)
    """
    if len(tokens) == len(t):
        for tok, t2 in zip(tokens, t):
            t1, value = tok
            if t1 != t2:
                break
        else:
            return True
    return False


if __name__ == "__main__":
    want_print = False
    # want_print = True
    def test(s, *tokens_and_values, in_dict=False):
        tokens = []
        values = []
        tokens_with_values = set((STRING, COMMENT))
        expect_token = True
        for t in tokens_and_values:
            # print("t", t, "expect_token", expect_token)
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
            print("test input:\n\t", s, "\nshould match:\n\t", " ".join(x if x in token_to_name else repr(x) for x in tokens_and_values))
        for tok, s in tokenize(s, in_dict):
            if want_print:
                print("  >>", tok, repr(s))
            t = tokens.pop(0)
            if tok != t:
                sys.exit("TOKEN DOESN'T MATCH, EXPECTED " + str(token_to_name[t]) + " GOT " + str(token_to_name.get(tok)))
            if tok in tokens_with_values:
                v = values.pop(0)
                if v != s:
                    sys.exit("TOKEN VALUE DOESN'T MATCH, EXPECTED " + repr(v) + " GOT " + repr(s))

        if want_print:
            print()

    test(r"hey party people ", STRING, "hey party people")
    test(r"  hey party people ", WHITESPACE, STRING, "hey party people")
    test(r"# hey party people ", COMMENT, " hey party people ")
    test(r" # hey party people ", WHITESPACE, COMMENT, " hey party people ")
    test(r""" "quoted \\u1234 string" """, WHITESPACE, STRING, "quoted \u1234 string", WHITESPACE)
    test(r""" "quoted \\N{END OF LINE} string" """, WHITESPACE, STRING, "quoted \n string", WHITESPACE)
    test(r""" "quoted string" = value """, WHITESPACE, STRING, "quoted string", WHITESPACE, EQUALS, WHITESPACE, STRING, "value", WHITESPACE, in_dict=True)
    test(r""" "quoted string"=value """, WHITESPACE, STRING, "quoted string", EQUALS, STRING, "value", WHITESPACE, in_dict=True)
    test(r""" "quoted string"={""", WHITESPACE, STRING, "quoted string", EQUALS, LEFT_CURLY_BRACE, in_dict=True)
    test(r""" "quoted string" = {""", WHITESPACE, STRING, "quoted string", WHITESPACE, EQUALS, WHITESPACE, LEFT_CURLY_BRACE, in_dict=True)
    test(r""" "quoted string"=[""", WHITESPACE, STRING, "quoted string", EQUALS, LEFT_SQUARE_BRACKET, in_dict=True)
    test(r""" "quoted string" = [""", WHITESPACE, STRING, "quoted string", WHITESPACE, EQUALS, WHITESPACE, LEFT_SQUARE_BRACKET, in_dict=True)
    test(r"x=y", STRING, "x", EQUALS, STRING, "y", in_dict=True)
    test(r"x={", STRING, "x", EQUALS, LEFT_CURLY_BRACE, in_dict=True)
    test(r"x=[", STRING, "x", EQUALS, LEFT_SQUARE_BRACKET, in_dict=True)
    test(r'''x="quoted string"''', STRING, "x", EQUALS, STRING, "quoted string", in_dict=True)

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
        LEFT_CURLY_BRACE,
        RIGHT_CURLY_BRACE,
        RIGHT_SQUARE_BRACKET,
        WHITESPACE,
        TRIPLE_SINGLE_QUOTE,
        WHITESPACE,
        )

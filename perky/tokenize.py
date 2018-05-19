#
# tokenize.py
#
# Part of the "perky" Python library
# Copyright 2018 by Larry Hastings
#

import ast

STRING = 'string'
EQUALS = '='
LEFT_CURLY_BRACE = '{'
LEFT_SQUARE_BRACKET = '['
COMMENT = '#'
TRIPLE_SINGLE_QUOTE = "'''"
TRIPLE_DOUBLE_QUOTE = '"""'

s_to_token = {
    '=': EQUALS,
    '{': LEFT_CURLY_BRACE,
    '[': LEFT_SQUARE_BRACKET,
}


class pushback_str_iterator:
    def __init__(self, s):
        self.characters = list(reversed(s))

    def __repr__(self):
        contents = "".join(reversed(self.characters))
        return f'<pushback {contents!r}>'

    def push(self, s):
        # print("PUSH ->", repr(s))
        self.characters.append(s)

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


def tokenize(s, in_dict=False):
    """
    Tokenizes a line.  Handles two types of lines:
        * lines in a dict
            name = value
        * lines in a list
            value

    There's a little context smarts necessary here.
    For a dict line, the first = delimits the name,
    and all subsequent unquoted = are part of an
    unquoted string (if that's the value).
    For a list line, all = are part of the unquoted
    string.  Similarly, if you're already in an
    unquoted string, { and [ and ' and " and even '''
    all aren't special.
    """
    buffer = []
    type = None

    i = pushback_str_iterator(s)

    def skip_whitespace():
        """
        Skips whitespace.  Returns whitespace skipped.
        If the next character is non-whitespace or the
        iterator is empty, returns an empty string.
        """
        buffer = []
        for c in i:
            if not c.isspace():
                i.push(c)
                break
            buffer.append(c)
        return "".join(buffer)

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

        return ast.literal_eval("".join(buffer))


    # turn off in_dict after the first token
    in_dict_countdown = 1
    while i:
        skip_whitespace()

        if in_dict_countdown:
            in_dict_countdown -= 1
        elif in_dict:
            in_dict = False

        try:
            c = next(i)
        except StopIteration:
            break

        tok = s_to_token.get(c, None)
        if tok:
            yield tok, c
            continue

        if c in '"\'':
            yield STRING, parse_quoted_string(c)
            continue

        if c == '#':
            comment = i.drain()
            yield COMMENT, comment
            continue

        i.push(c)
        s = parse_unquoted_string()
        yield STRING, s

if __name__ == "__main__":
    def test(s, in_dict=False):
        print("test input:", s)
        for tok, s in tokenize(s, in_dict):
            print("  >>", tok, repr(s))
        print()

    test(r"  hey party people ")
    test(r" # hey party people ")
    test(r""" "quoted \\u1234 string" """)
    test(r""" "quoted \\N{END OF LINE} string" """)
    test(r""" "quoted string" = value """, True)
    test(r""" "quoted string" = { """, True)
    test(r""" "quoted string" = [ """, True)
    test(r"x=y", True)
    test(r"x={", True)
    test(r"x=[", True)
    test(r'''x="quoted string"''', True)

    # and now, the big finish
    test(r""" unquoted string ' " [ { = unquoted value ' " [ { = yes! """, True)

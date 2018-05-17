#
# tokenize.py
#
# Part of the "perky" Python library
# Copyright 2018 by Larry Hastings
#

WHITESPACE = 'whitespace'
UNQUOTED_STRING = 'unquoted string'
QUOTED_STRING = 'quoted string'
EQUALS = '='
LEFT_CURLY_BRACE = '{'
LEFT_SQUARE_BRACKET = '['
COMMENT = '#'

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


escape_sequence_map = {
    '\\': '\\',
    "'": "'",
    '"': '"',
    'a': '\a',
    'b': '\b',
    'f': '\f',
    'n': '\n',
    'r': '\r',
    't': '\t',
    'v': '\v',
}

def tokenize(s):
    """
    Handles two types of lines:
        * lines in a dict
            name = value
        * lines in a list
            value
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
        Parse an unquoted string, aka an "identifier" in
        most langauges.  Returns the unquoted string parsed.
        If there were no characters to be read, returns an
        empty string.
        """
        buffer = []
        for c in i:
            if c in '"\'':
                raise RuntimeError("quote character used in unquoted string")
            if c.isspace() or (c == '='):
                i.push(c)
                break
            buffer.append(c)
        return "".join(buffer)

    def parse_quoted_string(quote):
        """
        Parse a quoted string.  The ending quote
        must match the starting quote character
        passed in.  Handles all the Python escape
        sequences: all the single-character ones,
        octal, and the extra-special x u U N ones.
        """
        buffer = []
        special = []
        special_length = 0
        backslash = False
        for c in i:
            # print("c", repr(c))
            if backslash:
                if backslash == '\\':
                    # print("backslash", repr(backslash), "c", repr(c))
                    value = escape_sequence_map.get(c, None)
                    if value:
                        buffer.append(value)
                        backslash = None
                        continue

                    backslash = c
                    if c == 'x':
                        special_length = 2
                        special.append('0x')
                        continue
                    if c in '01234567':
                        special_length = 3
                        special.append('0o')
                        special.append(c)
                        continue
                    if c == 'u':
                        special_length = 2
                        special.append('"\\u')
                        continue
                    if c == 'U':
                        special_length = 4
                        special.append('"\\U')
                        continue
                    if c == 'N':
                        special.append('"\\N{')
                        continue
                    raise RuntimeError("Unsupported escape sequence: \\" + c)

                if special_length:
                    if not c.isalnum():
                        raise RuntimeError("Invalid character in \\" + backslash + " sequence")
                    special.append(c)
                    special_length -= 1
                    if not special_length:
                        if backslash in 'x01234567':
                            buffer.append(chr(int("".join(special))))
                        elif backslash in 'Uu':
                            special.append('"')
                            buffer.append(eval(special))
                        special = []
                        backslash = None
                    continue

                if backslash == 'N':
                    if c != '{':
                        raise RuntimeError("Invalid \\N escape sequence")
                    backslash = c
                    continue

                if backslash == '{':
                    special.append(c)
                    if c != '}':
                        continue
                    buffer.append(eval("".join(special)))
                    special = []
                    backslash = None
                    continue

            if c == '\\':
                backslash = c
                continue

            if c == quote:
                break

            buffer.append(c)
        else:
            raise RuntimeError("Unterminated quoted string")

        if backslash:
            raise RuntimeError("Unfinished escape sequence " + backslash)

        return "".join(buffer)

    # while i:
    #     skip_whitespace()
    #     print(parse_unquoted_string())
    # for j in range(8):
    while i:
        ws = skip_whitespace()
        if ws:
            yield WHITESPACE, ws
        try:
            c = next(i)
        except StopIteration:
            break

        tok = s_to_token.get(c, None)
        if tok:
            yield tok, c
            continue

        if c in '"\'':
            yield QUOTED_STRING, parse_quoted_string(c)
            continue

        if c == '#':
            comment = i.drain()
            print(i)
            yield COMMENT, comment
            continue

        i.push(c)
        s = parse_unquoted_string()
        yield UNQUOTED_STRING, s

if __name__ == "__main__":
    def test(s):
        for tok, s in tokenize(s):
            print(tok, repr(s))
        print("***")

    test("  hey party people ")
    test(" # hey party people ")
    test("  \"quoted \N{END OF LINE} string\" ")
    test("  \"quoted string\" = value ")
    test("  \"quoted string\" = { ")
    test("  \"quoted string\" = [ ")
    test("x=y")
    test("x={")
    test("x=[")
    test("x=\"quoted string\"")

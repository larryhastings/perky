#!/usr/bin/env python3


def preload_local_perky():
    """
    Pre-load the local "perky" module, to preclude finding
    an already-installed one on the path.
    """
    import pathlib
    import sys

    argv_0 = pathlib.Path(sys.argv[0])
    perky_dir = argv_0.resolve().parent
    while True:
        perky_init = perky_dir / "perky" / "__init__.py"
        if perky_init.is_file():
            break
        perky_dir = perky_dir.parent

    # this almost certainly *is* a git checkout
    # ... but that's not required, so don't assert it.
    # assert (perky_dir / ".git" / "config").is_file()

    if perky_dir not in sys.path:
        sys.path.insert(1, str(perky_dir))

    import perky
    assert perky.__file__.startswith(str(perky_dir))
    return perky_dir

preload_local_perky()


import perky
import unittest

from perky.tokenize import WHITESPACE
from perky.tokenize import STRING
from perky.tokenize import COMMENT
from perky.tokenize import NUMBER_SIGN
from perky.tokenize import EQUALS
from perky.tokenize import LEFT_CURLY_BRACE
from perky.tokenize import RIGHT_CURLY_BRACE
from perky.tokenize import LEFT_SQUARE_BRACKET
from perky.tokenize import RIGHT_SQUARE_BRACKET
from perky.tokenize import SINGLE_QUOTE
from perky.tokenize import DOUBLE_QUOTE
from perky.tokenize import TRIPLE_SINGLE_QUOTE
from perky.tokenize import TRIPLE_DOUBLE_QUOTE
from perky.tokenize import EMPTY_CURLY_BRACES
from perky.tokenize import EMPTY_SQUARE_BRACKETS

from perky.tokenize import token_to_name, tokenize


want_print = False


class TestTokenizer(unittest.TestCase):

    def test_tokenizer(self):

        def _test(s, tokens_and_values, suppress_whitespace):
            tokens = []
            values = []
            tokens_with_values = set((STRING, COMMENT))
            expect_token = True
            for t in tokens_and_values:
                is_token = token_to_name.get(t)
                if expect_token:
                    self.assertTrue(is_token, "expected token, got " + str(t))
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
                if want_print:
                    print(f"test #{test_number}{suffix}:\n  input:\n\t", repr(s), "\n  should match:\n\t", " ".join(x if x in token_to_name else repr(x) for x in tokens_and_values), end="\n\n")
                test_number += 1
            for tok, s in tokenize(s, suppress_whitespace=suppress_whitespace):
                t = tokens.pop(0)
                if want_print:
                    print("  [want]", t, end="")
                if tok in tokens_with_values:
                    v = values.pop(0)
                    if want_print:
                        print(f" {s!r}")
                else:
                    if want_print:
                        print()
                    v = None
                if want_print:
                    print("  [ got]", tok, repr(s))
                self.assertEqual(tok, t, "token doesn't match, expected " + str(token_to_name[t]) + " got " + str(token_to_name.get(tok)))
                if v is not None:
                    self.assertEqual(v, s, "token value doesn't match, expected " + repr(v) + " got " + repr(s))

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


def run_tests():
    unittest.main()

if __name__ == '__main__':
    run_tests()


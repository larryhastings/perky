#!/usr/bin/env python3

import perkytestlib
perkytestlib.preload_local_perky()


import perky
import unittest

class PerkyTestCase(unittest.TestCase):
    maxDiff = None

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

from perky.tokenize import token_to_name, tokenize, LineTokenizer


want_print = False


class TestTokenizer(PerkyTestCase):

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
            if want_print: # pragma: nocover
                if suppress_whitespace is None:
                    suffix = ""
                else:
                    modifier = "suppressing" if suppress_whitespace else "keeping"
                    suffix = f", {modifier} whitespace tokens"
                print(f"test #{test_number}{suffix}:\n  input:\n\t", repr(s), "\n  should match:\n\t", " ".join(x if x in token_to_name else repr(x) for x in tokens_and_values), end="\n\n")
                test_number += 1
            for tok, s in tokenize(s, suppress_whitespace=suppress_whitespace):
                t = tokens.pop(0)
                if want_print: # pragma: nocover
                    print("  [want]", t, end="")
                if tok in tokens_with_values:
                    v = values.pop(0)
                    if want_print: # pragma: nocover
                        print(f" {s!r}")
                else:
                    if want_print: # pragma: nocover
                        print()
                    v = None
                if want_print: # pragma: nocover
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

    def test_invalid_string(self):
        s = '''
        x = """
          abc
          """ what's this?
        '''
        tokens = []
        with self.assertRaises(ValueError):
            for t in tokenize(s):
                tokens.append(t)
        self.assertEqual(tokens, [(STRING, 'x'), (EQUALS, '=')])


class TestLineTokenizer(PerkyTestCase):
    def test_empty_line_tokenizer(self):
        lt = LineTokenizer('')
        self.assertTrue(lt)
        line_number, line = lt.next_line()
        self.assertEqual(line, '')

        line_number, line = lt.next_line()
        self.assertFalse(lt)
        self.assertEqual(lt.tokens(), (None, None, None))

        for t in lt: # pragma: no cover
            self.assertTrue(False)
        else:
            self.assertTrue(True)


    def test_line_tokenizer(self):
        expected_results = [
            (1, 'a=1', [(STRING, 'a'), (EQUALS, '='), (STRING, '1')]),
            (2, 'b=2', [(STRING, 'b'), (EQUALS, '='), (STRING, '2')]),
            ]

        input_lines = "\n".join(t[1] for t in expected_results)
        lt = LineTokenizer(input_lines)
        self.assertIn('<LineTokenizer 0/2 lines [', repr(lt))
        self.assertTrue(lt)
        for expected in expected_results:
            self.assertTrue(lt)
            got = lt.tokens()
            line_number = expected[0]
            self.assertIn(f'<LineTokenizer {line_number}/2 lines [', repr(lt))
            self.assertEqual(expected, got)

        self.assertFalse(lt)
        self.assertIn('<LineTokenizer 2/2 lines [', repr(lt))
        got = lt.next_line()
        self.assertEqual(got, (None, None))

        self.assertFalse(lt)
        self.assertIn('<LineTokenizer 2/2 lines [', repr(lt))
        got = lt.next_line()
        self.assertEqual(got, (None, None))

        self.assertFalse(lt)


if __name__ == '__main__': # pragma: nocover
    unittest.main()

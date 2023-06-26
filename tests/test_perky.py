#!/usr/bin/env python3

import perkytestlib
perky_dir = perkytestlib.preload_local_perky()

import os
import pathlib
import perky
import tempfile
import unittest

os.chdir(perky_dir / "tests")

class pushd:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        self.old_path = os.getcwd()
        os.chdir(self.path)

    def __exit__(self, exc_type, exc_value, exc_tb):
        os.chdir(self.old_path)


TEST_INPUT_TEXT = """

a = b
c = d
# comment inside dict
key with empty value =
dict = {
    inner1=value1
      inner 2 = " value 2  "
      list = [

      a
        b
      # comment inside list


    c
        ]
}

list = [

    1
    2
    3
]

text = '''
    hello

    this is indented

    etc.
    '''

"""

TEST_INPUT_TEXT_TRIPLE_Q_ERROR = """

a = b
c = d
dict = {
    inner1=value1
      inner 2 = " value 2  "
      list = [

      a
        b

    c
        ]
}

list = [

    1
    2
    3
]

text = '''
    hello

    this is indented

    etc.
        '''

"""

TEST__PARSE_OUTPUT = {
                'a': 'b', 'c': 'd', 'key with empty value': '',
                'dict': {'inner1': 'value1', 'inner 2': ' value 2  ', 'list': ['a', 'b', 'c']},
                'list': ['1', '2', '3'],
                'text': 'hello\n\nthis is indented\n\netc.'
               }


class TestParse(unittest.TestCase):
    def test_parse_illegal_input(self):
        with self.assertRaises(TypeError):
            perky.loads(None)
        with self.assertRaises(TypeError):
            perky.loads(3)

    def test_parse_invalid_root(self):
        with self.assertRaises(TypeError):
            perky.loads(TEST_INPUT_TEXT, root=3.14159)

    def test_parse(self):
        test = perky.loads(TEST_INPUT_TEXT)
        self.assertEqual(test, TEST__PARSE_OUTPUT)

    def test_parse_values(self):
        test = perky.loads(TEST_INPUT_TEXT)
        self.assertEqual(type(test), dict)
        self.assertEqual(test['a'], 'b')
        self.assertEqual(test['c'], 'd')
        self.assertEqual(test['key with empty value'], '')
        self.assertEqual(test['list'], ['1', '2', '3'])

        d = test['dict']
        self.assertEqual(type(d), dict)
        self.assertEqual(d['inner1'], 'value1')
        self.assertEqual(d['inner 2'], ' value 2  ')
        self.assertEqual(d['list'], ['a', 'b', 'c'])

    def test_parse_quoted_tokens_ok(self):
        key = 'a {} " "" """ # []'
        value = 'b {} " "" """ # [] ='
        result = perky.loads(f" '{key}' = '{value}' ")
        self.assertIn(key, result)
        self.assertEqual(result[key], value)

        key = "a {} ' '' ''' # []"
        value = "b {} ' '' ''' # [] ="
        result = perky.loads(f' "{key}" = "{value}" ')
        self.assertIn(key, result)
        self.assertEqual(result[key], value)

    def test_parse_unterminated_quoted_string(self):
        with self.assertRaises(SyntaxError):
            perky.loads("""
'quoted' = 'unterminated quoted string
""")

    def test_parse_triple_quote(self):
        # ensure we have some real trailing whitespace.
        # modern editors will strip that for you,
        # so we programmatically ensure it for testing purposes.
        d = perky.loads('''
a = """

    this is flush left__
    note the          ^^
    intentional trailing whitespace!

      it looks like underscores,
      but we change it to spaces down below
      vvvv
    """

'''.replace('_', ' '))
        self.assertEqual(d['a'], "\nthis is flush left\nnote the          ^^\nintentional trailing whitespace!\n\n  it looks like underscores,\n  but we change it to spaces down below\n  vvvv")

    def test_empty_dicts_and_lists(self):
        d = perky.loads('''
a = []
b = [ ]
c = {}
d = { }

list = [
    []
    [ ]
    {}
    { }
    ]

''')
        self.assertEqual(d['a'], [])
        self.assertEqual(d['b'], [])
        self.assertEqual(d['c'], {})
        self.assertEqual(d['d'], {})
        self.assertEqual(d['list'], [ [], [], {}, {} ])

    def test_parse_trip_q_error(self):
        with self.assertRaises(perky.FormatError):
            perky.loads(TEST_INPUT_TEXT_TRIPLE_Q_ERROR)
        try:
            perky.loads(TEST_INPUT_TEXT_TRIPLE_Q_ERROR)

        # examine the str and repr
        except perky.PerkyFormatError as e:
            s = str(e)
            r = repr(e)
            self.assertIn('Format error: malformed line triple-quoted block', s)
            self.assertIn('Format error: malformed line triple-quoted block', r)
            self.assertIn('hello', s)
            self.assertIn('hello', r)

    def test_undefined_pragma(self):
        line = '=balloon'
        try:
            perky.loads(line)
        except perky.FormatError as e:
            self.assertEqual(None, e.tokens)
            self.assertIn('unknown pragma', str(e).lower())
            self.assertEqual(line, e.line)
            return
        if 1: # pragma: no cover
            self.assertEqual(True, False, "exception not raised!")

    def test_pragma_format_error(self):
        bad_pragma = '[{=}]'
        line = f'=pragma {bad_pragma}'
        try:
            perky.loads(line)
        except perky.FormatError as e:
            self.assertEqual(bad_pragma, e.tokens)
            self.assertIn('invalid pragma argument', str(e).lower())
            self.assertEqual(line, e.line)
            return
        if 1: # pragma: no cover
            self.assertEqual(True, False, "exception not raised!")

    def test_parse_trip_repeated_key_error(self):
        # perky doesn't like it if you redefine the same key in a dict
        # twice in the same file.
        # note that perky explicitly doesn't complain if you
        # redefine a key in a different (as in, =include'd) file.
        # test_perky_include_nested tests redefining in different files.
        with self.assertRaises(perky.PerkyFormatError):
            perky.loads("a=3\na=5")

# TODO: check if there are any other formats that would cause a failure
    def test_read_file(self):
        test_input = perky.load("test_input.txt", encoding="utf-8")
        self.assertIsNotNone(self, test_input)

    def test_transform_dict(self):
        o = {'a': '3', 'b': '5.0', 'c': ['1', '2', 'None', '3'], 'd': {'e': 'f', 'g': 'True'}}
        schema = {'a': int, 'b': float, 'c': [perky.nullable(int)], 'd': {'e': str, 'g': perky.const}}
        test_func = perky.transform(o, schema)
        expected_dict = {'a': 3, 'b': 5.0, 'c': [1, 2, None, 3], 'd': {'e': 'f', 'g': True}}
        self.assertEqual(expected_dict, test_func)

    def test_transform_type_mismatch(self):
        o = {'a': '3', 'b': '5.0', 'c': ['1', '2', 'None', '3'], 'd': {'e': 'f', 'g': 'True'}}
        schema = [{'a': int, 'b': float, 'c': [perky.nullable(int)], 'd': {'e': str, 'g': perky.const}}]
        with self.assertRaises(perky.PerkyFormatError):
            perky.transform(o, schema)

    def test_transform_bad_obj(self):
        o2 = {'a': '44'}
        schema = [{'a': int, 'b': float, 'c': [perky.nullable(int)], 'd': {'e': str, 'g': perky.const}}]
        with self.assertRaises(perky.PerkyFormatError):
            perky.transform(o2, schema)

    def test_transform_none(self):
        o = None
        schema = {'a': int, 'b': float, 'c': [perky.nullable(int)], 'd': {'e': str, 'g': perky.const}}
        with self.assertRaises(perky.PerkyFormatError):
            perky.transform(o, schema)

    def test_perky_include_list(self):
        with pushd("include_list"):
            root = perky.load("main.pky", root=[], pragmas={'include':perky.pragma_include()})
        self.assertEqual(root, list("abcd"))

    def test_perky_include_dict(self):
        with pushd("include_dict"):
            root = perky.load("main.pky", pragmas={'include':perky.pragma_include()})
        self.assertEqual(root, dict(zip("abcd", "1234")))

    def test_perky_include_nested(self):
        with pushd("include_nested"):
            root = perky.load("main.pky", pragmas={'include':perky.pragma_include()})
        self.assertEqual(root,
            {
                'a': '1',
                'b': {
                    'ba': '1',
                    'bb': '2',
                    'bc': '3',
                    'bd': '4',
                    'nested_dict': {
                        'x': '3',
                        'y': '2',
                        'z': ['1', '2', '3', '4']
                        },
                    'nested_list': ['a', 'b', 'c'],
                    },
                'c': '3',
                'd': '4'}
            )

    def test_perky_include_path(self):
        with pushd("include_path"):
            root = perky.load("dir1/main.pky", pragmas={'include':perky.pragma_include( ['dir1', 'dir2'] )})
        self.assertEqual(root, dict(zip("abc", "345")))

    def test_perky_invalid_pragma(self):
        with self.assertRaises(perky.PerkyFormatError):
            root = perky.loads("a=b\n=include '''\nc=d\n", pragmas={'include':perky.pragma_include()})

    def test_perky_roundtrip(self):
        for i in range(1, 300):
            c = chr(i)
            if c.isspace():
                continue
            hex_digits = hex(i).partition("x")[2].rjust(4, "0")
            s = f"U+{hex_digits} {c}"

            d1 = {s:s}
            s1 = perky.dumps(d1)
            d2 = perky.loads(s1)
            s2 = perky.dumps(d2)
            self.assertEqual(d1, d2)
            self.assertEqual(s1, s2)

        d1 = perky.loads(TEST_INPUT_TEXT)
        s1 = perky.dumps(d1)
        d2 = perky.loads(s1)
        s2 = perky.dumps(d2)
        self.assertEqual(d1, d2)
        self.assertEqual(s1, s2)

    def test_pushback_str_iterator(self):
        i = perky.pushback_str_iterator("")
        self.assertIn('<pushback i=', repr(i))
        self.assertFalse(i)

        i = perky.pushback_str_iterator("c")
        self.assertIn('<pushback i=', repr(i))
        i.push('d')
        self.assertTrue(i)
        d = next(i)
        self.assertTrue(i)
        c = next(i)
        self.assertFalse(i)
        with self.assertRaises(StopIteration):
            e = next(i)
        self.assertFalse(i)

        self.assertEqual(c, 'c')
        self.assertEqual(d, 'd')

        i = perky.pushback_str_iterator("abcde")
        self.assertIn('<pushback i=', repr(i))
        self.assertTrue(i)
        strings = []
        strings.append(next(i)) # a
        strings.append(next(i)) # b
        i.push_c("X")
        strings.append(next(i)) # X
        strings.append(next(i)) # c
        i.push("YZ")
        for c in i:
            strings.append(c) # Y Z d e
        self.assertEqual("".join(strings), "abXcYZde")

        i = perky.pushback_str_iterator("abcde")
        i.push_c("X")
        i.push("nozzle")
        i.push(['Y', 'Z'])
        self.assertEqual(i.drain(), "YZnozzleXabcde")

    def test_pushback_str_iterator_bool_regression(self):
        for push_in_the_middle in (False, True):
            i = perky.pushback_str_iterator("abc")
            assert i

            assert next(i) == 'a'
            assert i

            assert next(i) == 'b'
            assert i

            if push_in_the_middle:
                i.push('X')
                assert next(i) == 'X'
                assert i

            assert next(i) == 'c'
            assert not i


class TestDump(unittest.TestCase):

    # we already exercise most of dumps in the parse tests.
    # this just gets us the last little bit of coverage.

    def test_dump_with_fewest_quote_marks(self):
        d = {
            'a': 'a " " " "" """ ',
            "b": "b ' ' ' '' ''' ",
            }
        s = perky.dumps(d)
        d2 = perky.loads(s)
        self.assertEqual(d, d2)

    def test_dump_invalid_keys(self):
        with self.assertRaises(TypeError):
            perky.dumps({3: '14'})
        with self.assertRaises(TypeError):
            perky.dumps({b'3': 14})
        with self.assertRaises(TypeError):
            perky.dumps({b'3': 14})

    def test_dump_invalid_values(self):
        with self.assertRaises(TypeError):
            perky.dumps({'a': b'14'})

    def test_dump_non_str_values(self):
        s = perky.dumps({'a': 22})
        d = perky.loads(s)
        self.assertEqual(d['a'], '22')

    def test_dump_to_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = pathlib.Path(tmpdir)

            d = perky.loads(TEST_INPUT_TEXT)
            filename = tmpdir / "temp.pky"
            perky.dump(filename, d)

            d2 = perky.load(filename)
            self.assertEqual(d, d2)


class TestPragmaInclude(unittest.TestCase):
    def test_include(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = pathlib.Path(tmpdir)
            x = tmpdir / "x.pky"
            with x.open('wt') as f:
                f.write('# a comment!\n')
                f.write('x = y\n')
                f.write('# an empty line!\n\n')
            s = "a = b\n=include 'x.pky'\nc = d"
            d = perky.loads(s, pragmas={'include': perky.pragma_include(include_path=(str(tmpdir),))})
            self.assertEqual(d['a'], 'b')
            self.assertEqual(d['c'], 'd')
            self.assertEqual(d['x'], 'y')

    def test_non_existent_file(self):
        s = "a = b\n=include 'non existent file.pky'\nc = d"

        with self.assertRaises(FileNotFoundError):
            d = perky.loads(s, pragmas={'include': perky.pragma_include()})


if __name__ == '__main__': # pragma: no cover
    unittest.main()

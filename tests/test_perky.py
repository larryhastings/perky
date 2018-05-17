#!/usr/bin/env python3

# use a crowbar on sys.path
# to let this script import perky
# without any additional work
assert __name__ == "__main__"
import os.path
from os.path import abspath, dirname
import sys
perky_dir = dirname(dirname(abspath(sys.argv[0])))
sys.path.insert(0, perky_dir)
os.chdir(perky_dir + "/tests")

import perky
import unittest


TEST_INPUT_TEXT = """

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
                'a': 'b', 'c': 'd', 'dict': {'inner1': 'value1', 'inner 2': ' value 2  ', 'list': ['a', 'b', 'c']},
                'list': ['1', '2', '3'],
                'text': 'hello\n\nthis is indented\n\netc.'
               }


class TestParseMethods(unittest.TestCase):

    def test_parse_type(self):
        test = perky.parse(TEST_INPUT_TEXT)
        self.assertEqual(type(test), dict)

    def test_parse(self):
        test = perky.parse(TEST_INPUT_TEXT)
        self.assertEqual(test, TEST__PARSE_OUTPUT)

    def test_parse_no_input(self):
        with self.assertRaises(AttributeError):
            perky.parse(None)

    def test_parse_bad_input(self):
        with self.assertRaises(AttributeError):
            perky.parse(3)

# TODO: add code changes to perky.py to raise an assertion error.
    def test_parse_trip_q_error(self):
        with self.assertRaises(perky.PerkyFormatError):
            perky.parse(TEST_INPUT_TEXT_TRIPLE_Q_ERROR)

# TODO: check if there are any other formats that would cause a failure
    def test_read_file(self):
        test_input = perky.read("test_input.txt", encoding="utf-8")
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
        with self.assertRaises(SystemExit):
            perky.transform(o, schema)

    def test_transform_bad_obj(self):
        o2 = {'a': '44'}
        schema = [{'a': int, 'b': float, 'c': [perky.nullable(int)], 'd': {'e': str, 'g': perky.const}}]
        with self.assertRaises(SystemExit):
            perky.transform(o2, schema)

    def test_transform_none(self):
        o = None
        schema = {'a': int, 'b': float, 'c': [perky.nullable(int)], 'd': {'e': str, 'g': perky.const}}
        with self.assertRaises(SystemExit):
            perky.transform(o, schema)

# TODO: parts to test
# perky.loads
# perky.dumps
# perky.requires
#
# perky.transform(list, list)
# perky.transform('a', str)

# if 1:
#     o = {'a': '3', 'b': '5.0', 'c': ['1', '2', 'None', '3'], 'd': { 'e': 'f', 'g': 'True'}}
#     schema = {'a': int, 'b': float, 'c': [nullable(int)], 'd': { 'e': str, 'g': const }}
#
#     result = transform(o, schema)
#     import pprint
#     pprint.pprint(result)
#
#     print("REQUIRED 1")
#     r = Required()
#     schema = {
#         'a': r(int),
#         'b': r(float),
#         'c': [nullable(int)],
#         'd': {
#             'e': r(str),
#             'g': const
#             }
#         }
#     r.annotate(schema)
#     print("schema", schema)
#     result = transform(o, schema)
#     print(result)
#     r.verify()
#
#     print("REQUIRED 2")
#     r.annotate(schema)
#     o2 = {'a': '44'}
#     result = transform(o2, schema)
#     r.verify()


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3

import unittest

def run_tests():
    successes = modules = 0
    for test_module in (
        'test_perky',
        'test_tokenize',
        'test_transform',
        'test_utility',
        ):
        print()
        print(test_module)
        print('-' * len(test_module))
        module = __import__(test_module)
        result = unittest.main(module=module, exit=False)
        modules += 1
        successes += result.result.wasSuccessful()

    print()
    if successes == modules:
        print("Unit tests passed.")
    else: # pragma: nocover
        print("Unit tests failed.")

if __name__ == '__main__':
    run_tests()

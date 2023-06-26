#!/usr/bin/env python3

import pathlib
import sys

def preload_local_perky():
    """
    Pre-load the local "perky" module, to preclude finding
    an already-installed one on the path.
    """

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


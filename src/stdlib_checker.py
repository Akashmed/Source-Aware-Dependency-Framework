from __future__ import annotations

import sys


STANDARD_LIBRARY_NAMES = frozenset(getattr(sys, "stdlib_module_names", set())) | {"__future__"}


def is_standard_library(top_level_name: str) -> bool:
    return top_level_name in STANDARD_LIBRARY_NAMES

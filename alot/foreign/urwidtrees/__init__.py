try:
    # lru_cache is part of the stdlib from v3.2 onwards
    import functools.lru_cache as lru_cache
except:
    # on older versions we use a backport
    import lru_cache as lru_cache

from tree import Tree, SimpleTree
from decoration import DecoratedTree, CollapsibleTree
from decoration import IndentedTree, CollapsibleIndentedTree
from decoration import ArrowTree, CollapsibleArrowTree
from nested import NestedTree
from widgets import TreeBox

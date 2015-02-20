try:
    from functoons import lru_cache
except ImportError:
    from .lru_cache import lru_cache

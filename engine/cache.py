import os
from utils import CACHE


def cache_lookup(key):

    path = os.path.join(CACHE, key)

    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()

    return None


def cache_store(key, digest):

    path = os.path.join(CACHE, key)

    with open(path, "w") as f:
        f.write(digest)

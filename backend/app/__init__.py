"""On Vercel only /tmp is writable, but huggingface_hub (which fastembed uses
to download the embedding model) caches and logs under ~/.cache, so every
cold start failed with "Read-only file system". The cache locations are
read when those libraries are imported, and every app module is imported
after this package, so this is the earliest place that covers all of them.
VERCEL is set by Vercel itself; the Docker image bakes the model in and
local dev has a writable home, so neither is affected."""

import os

if os.environ.get("VERCEL"):
    os.environ.setdefault("HF_HOME", "/tmp/huggingface")
    os.environ.setdefault("FASTEMBED_CACHE_PATH", "/tmp/fastembed_cache")

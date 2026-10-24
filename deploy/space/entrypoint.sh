#!/bin/sh
# Space startup: Qdrant, the private index bundle, then the API (+ web).
#
# Bundle source, in order:
#   1. /home/user/app/bundle (mounted for a local test: make space-run)
#   2. RAG_BUNDLE_REPO: a PRIVATE Hugging Face dataset, downloaded with
#      HF_TOKEN (a Space secret). The bundle holds raw CV text.
set -e

# torch sizes its thread pool from the host's cores, not the container's
# CPU quota: with 2 vCPUs on a 24-core host it ran 12 threads and was
# ~3.5x slower (measured, docs/changelog/FASE_6.md). Use the cgroup quota
# (cpu.max = "<quota> <period>"), else nproc. An explicit value wins.
if [ -z "$OMP_NUM_THREADS" ]; then
    THREADS=$(nproc)
    if [ -r /sys/fs/cgroup/cpu.max ]; then
        read -r QUOTA PERIOD < /sys/fs/cgroup/cpu.max
        if [ "$QUOTA" != "max" ]; then
            THREADS=$(( (QUOTA + PERIOD - 1) / PERIOD ))
        fi
    fi
    export OMP_NUM_THREADS="$THREADS" MKL_NUM_THREADS="$THREADS"
fi
echo "CPU threads: $OMP_NUM_THREADS"

# Qdrant runs from a writable copy of its config (the container user
# cannot write to /opt) with its storage in /tmp (rebuilt every start).
STORAGE=/tmp/qdrant
mkdir -p "$STORAGE" /tmp/qdrant-run
cp -r /opt/qdrant/config /tmp/qdrant-run/
QDRANT__STORAGE__STORAGE_PATH="$STORAGE" \
QDRANT__STORAGE__SNAPSHOTS_PATH="$STORAGE/snapshots" \
QDRANT__TELEMETRY_DISABLED=true \
    sh -c 'cd /tmp/qdrant-run && exec qdrant' > /tmp/qdrant.log 2>&1 &

echo "Waiting for Qdrant..."
for i in $(seq 1 60); do
    curl -sf http://127.0.0.1:6333/readyz > /dev/null && break
    sleep 1
done

BUNDLE=/home/user/app/bundle
if [ ! -f "$BUNDLE/bundle.json" ]; then
    if [ -z "$RAG_BUNDLE_REPO" ]; then
        echo "No bundle: mount one at $BUNDLE or set RAG_BUNDLE_REPO." >&2
        exit 1
    fi
    BUNDLE=/tmp/bundle
    echo "Downloading the index bundle from $RAG_BUNDLE_REPO..."
    uv run --no-sync python -c "
import os
from huggingface_hub import snapshot_download
snapshot_download(repo_id=os.environ['RAG_BUNDLE_REPO'], repo_type='dataset',
                  local_dir='$BUNDLE', token=os.environ.get('HF_TOKEN'))"
fi

uv run --no-sync python -m src bundle_restore --bundle_dir "$BUNDLE"
# The models are baked into the image: no Hub calls at runtime.
HF_HUB_OFFLINE=1 exec uv run --no-sync python -m src.api --host 0.0.0.0 --port 7860

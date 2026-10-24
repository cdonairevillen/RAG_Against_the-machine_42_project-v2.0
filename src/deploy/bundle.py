"""Prebuilt index bundle: build once on the GPU, serve it anywhere.

Indexing with bge-m3 takes ~6 min on the 3080 Ti and hours on a CPU, so
the deployment never indexes: it restores the bundle built here.

A bundle is a directory with:
    snapshots/<collection>.snapshot   Qdrant snapshot of each domain
    processed/<domain>/               BM25 indices and manifest
    bundle.json                       domains, embedding model, git
                                      revision and the SHA256 of every file

Privacy: the CV chunks hold the raw text (phone, old e-mail); they are
masked only when answering. The bundle must therefore stay private (a
private Hugging Face dataset, downloaded by the Space with a token),
never be committed or published. See docs/decisions.md.
"""
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime
from typing import Any, Optional

import httpx

from src.config import RagConfig, get_config

BUNDLE_FILE = "bundle.json"


def sha256(path: str) -> str:
    """Hex SHA256 of a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    """Short commit hash of the working tree ('unknown' outside git)."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True,
            text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def indexed_domains(config: RagConfig) -> list[str]:
    """Domains with a BM25 manifest (i.e. indexed)."""
    return [
        d for d in config.sources
        if os.path.isfile(os.path.join(config.paths.processed_dir, d,
                                       "manifest.json"))
    ]


def export_bundle(out_dir: str, config: Optional[RagConfig] = None,
                  domains: Optional[list[str]] = None) -> dict[str, Any]:
    """Snapshot every indexed domain into a bundle directory.

    Args:
        out_dir: Directory to write (replaced if it exists).
        config: Pipeline configuration (Qdrant URL, processed_dir).
        domains: Domains to include (default: every indexed one).

    Returns:
        The bundle manifest (also written as bundle.json).
    """
    config = config or get_config()
    domains = domains or indexed_domains(config)
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(os.path.join(out_dir, "snapshots"))
    url = config.qdrant.url.rstrip("/")
    files: dict[str, str] = {}
    with httpx.Client(base_url=url, timeout=600) as http:
        for domain in domains:
            collection = config.qdrant.collection(domain)
            print(f"Snapshotting {collection}...")
            created = http.post(f"/collections/{collection}/snapshots",
                                params={"wait": "true"})
            created.raise_for_status()
            name = created.json()["result"]["name"]
            target = os.path.join(out_dir, "snapshots",
                                  f"{collection}.snapshot")
            with http.stream(
                    "GET", f"/collections/{collection}/snapshots/{name}"
            ) as response:
                response.raise_for_status()
                with open(target, "wb") as fh:
                    for block in response.iter_bytes(1 << 20):
                        fh.write(block)
            # The snapshot also stays on the server: remove it there.
            http.delete(f"/collections/{collection}/snapshots/{name}")
            shutil.copytree(
                os.path.join(config.paths.processed_dir, domain),
                os.path.join(out_dir, "processed", domain),
            )
    for root, _, names in os.walk(out_dir):
        for name in names:
            path = os.path.join(root, name)
            rel = os.path.relpath(path, out_dir).replace("\\", "/")
            files[rel] = sha256(path)
    manifest = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "commit": git_commit(),
        "domains": domains,
        "collection_prefix": config.qdrant.collection_prefix,
        "embedding_model": config.embeddings.model,
        "files": files,
    }
    with open(os.path.join(out_dir, BUNDLE_FILE), "w", encoding="utf-8",
              newline="\n") as fh:
        json.dump(manifest, fh, indent=2)
    size = sum(os.path.getsize(os.path.join(r, n))
               for r, _, ns in os.walk(out_dir) for n in ns)
    print(f"Bundle written to {out_dir}: {', '.join(domains)} "
          f"({size / 1e6:.0f} MB)")
    return manifest


def restore_bundle(bundle_dir: str,
                   config: Optional[RagConfig] = None) -> list[str]:
    """Load a bundle into Qdrant and the processed directory.

    Every file is checked against its SHA256 first; the snapshots are
    uploaded to the configured Qdrant server (replacing the domain's
    collection) and the BM25 indices copied to processed_dir.

    Returns:
        The restored domains.

    Raises:
        ValueError: If a file is missing or corrupted.
    """
    config = config or get_config()
    with open(os.path.join(bundle_dir, BUNDLE_FILE), encoding="utf-8") as fh:
        manifest = json.load(fh)
    for rel, digest in manifest["files"].items():
        path = os.path.join(bundle_dir, rel)
        if not os.path.isfile(path) or sha256(path) != digest:
            raise ValueError(f"Bundle file missing or corrupted: {rel}")
    url = config.qdrant.url.rstrip("/")
    with httpx.Client(base_url=url, timeout=1800) as http:
        for domain in manifest["domains"]:
            collection = f"{manifest['collection_prefix']}{domain}"
            snapshot = os.path.join(bundle_dir, "snapshots",
                                    f"{collection}.snapshot")
            print(f"Restoring {collection}...")
            with open(snapshot, "rb") as fh:
                response = http.post(
                    f"/collections/{collection}/snapshots/upload",
                    params={"priority": "snapshot", "wait": "true"},
                    files={"snapshot": (os.path.basename(snapshot), fh)},
                )
            response.raise_for_status()
            target = os.path.join(config.paths.processed_dir, domain)
            if os.path.isdir(target):
                shutil.rmtree(target)
            shutil.copytree(os.path.join(bundle_dir, "processed", domain),
                            target)
    print(f"Restored: {', '.join(manifest['domains'])} "
          f"(bundle {manifest['created']}, commit {manifest['commit']})")
    return list(manifest["domains"])

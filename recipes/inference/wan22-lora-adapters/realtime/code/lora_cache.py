"""On-demand S3 LoRA cache for the WAN 2.2 endpoint.

Adapters are addressed by S3 URI in the request payload. The first request for a
given URI downloads it to local disk; later requests reuse the cached copy. Only one
adapter is applied at a time -- the previous one is unloaded before the next is
loaded, so LoRAs never stack unintentionally.

Loading itself is plain `pipeline.load_lora_weights()`. Diffusers detects the
adapter's key format and converts it internally, so no remapping code lives here.
"""

import hashlib
import logging
import threading
from pathlib import Path
from urllib.parse import urlparse

import boto3

log = logging.getLogger(__name__)

ADAPTER_NAME = "active"


class LoraCache:
    def __init__(self, cache_dir: str = "/tmp/lora_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.s3 = boto3.client("s3")
        # Guards the whole fetch+apply sequence: the pipeline's adapter state is
        # global, so a concurrent load/unload would corrupt it.
        self.lock = threading.RLock()
        self.active_uri: str | None = None
        self.active_scale: float | None = None

    def _local_path(self, s3_uri: str) -> Path:
        return self.cache_dir / hashlib.sha1(s3_uri.encode()).hexdigest()[:16]

    def fetch(self, s3_uri: str) -> Path:
        """Download the adapter from S3 if not already cached. Returns its local dir.

        Accepts either a prefix holding the adapter files, or a direct URI to a
        single .safetensors file.
        """
        parsed = urlparse(s3_uri)
        if parsed.scheme != "s3":
            raise ValueError(f"Expected s3:// URI, got {s3_uri!r}")

        local_dir = self._local_path(s3_uri)
        marker = local_dir / ".complete"
        if marker.exists():
            return local_dir

        local_dir.mkdir(parents=True, exist_ok=True)
        bucket = parsed.netloc
        path = parsed.path.lstrip("/")

        log.info("Downloading LoRA %s -> %s", s3_uri, local_dir)
        downloaded = 0
        if path.endswith((".safetensors", ".bin")):
            dest = local_dir / Path(path).name
            self.s3.download_file(bucket, path, str(dest))
            downloaded = 1
        else:
            prefix = path.rstrip("/") + "/"
            paginator = self.s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    rel = obj["Key"][len(prefix):]
                    if not rel or rel.endswith("/"):
                        continue
                    dest = local_dir / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    self.s3.download_file(bucket, obj["Key"], str(dest))
                    downloaded += 1

        if downloaded == 0:
            raise FileNotFoundError(f"No objects at {s3_uri}")

        marker.touch()
        log.info("Cached %d file(s) for %s", downloaded, s3_uri)
        return local_dir

    def apply(self, pipeline, s3_uri: str, scale: float = 1.0) -> None:
        """Fetch the adapter if needed and make it the pipeline's active LoRA."""
        with self.lock:
            if s3_uri == self.active_uri:
                # Already loaded; a scale change alone needs no reload.
                if scale != self.active_scale:
                    pipeline.set_adapters(ADAPTER_NAME, adapter_weights=scale)
                    self.active_scale = scale
                return

            self.clear(pipeline)

            local_dir = self.fetch(s3_uri)
            weight_file = self._pick_weight_file(local_dir)
            log.info("Loading LoRA %s (scale=%.2f)", weight_file.name, scale)

            pipeline.load_lora_weights(
                str(local_dir),
                weight_name=weight_file.name,
                adapter_name=ADAPTER_NAME,
            )
            pipeline.set_adapters(ADAPTER_NAME, adapter_weights=scale)
            self.active_uri, self.active_scale = s3_uri, scale

    def clear(self, pipeline) -> None:
        """Remove any currently-applied adapter, returning the pipeline to base."""
        with self.lock:
            if self.active_uri is None:
                return
            try:
                pipeline.unload_lora_weights()
            except Exception:
                log.exception("unload_lora_weights failed; continuing")
            self.active_uri = self.active_scale = None

    @staticmethod
    def _pick_weight_file(local_dir: Path) -> Path:
        candidates = sorted(local_dir.glob("*.safetensors")) or sorted(local_dir.glob("*.bin"))
        if not candidates:
            raise FileNotFoundError(f"No LoRA weight file found in {local_dir}")
        preferred = [c for c in candidates if c.name.startswith("adapter_model")]
        return (preferred or candidates)[0]

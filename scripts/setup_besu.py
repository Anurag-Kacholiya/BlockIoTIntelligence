"""Install the pinned Hyperledger Besu release into tools/besu (final task 2: multi-node QBFT network).

  python scripts/setup_besu.py

Downloads besu-<version>.tar.gz from the official release page (github.com/besu-eth/besu), refuses it unless its
SHA-256 equals the one pinned in configs/blockchain.yaml (the release's published .sha256), extracts it and checks
that Java 21+ is available. tools/ is git-ignored, as for Foundry.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common.config import ROOT, load_config  # noqa: E402
from src.common.qbft import BESU  # noqa: E402

URL = "https://github.com/besu-eth/besu/releases/download/{v}/besu-{v}.tar.gz"


def java_major() -> int:
    out = subprocess.run(["java", "-version"], capture_output=True, text=True).stderr
    m = re.search(r'version "(\d+)', out)
    if not m:
        raise SystemExit(f"Java not found (Besu needs Java 21+): {out.strip()}")
    return int(m.group(1))


def main() -> None:
    cfg = load_config("blockchain")["qbft"]
    version, expected = cfg["besu_version"], cfg["besu_sha256"]
    if java_major() < 21:
        raise SystemExit("Besu needs Java 21 or newer")
    cache = ROOT / "tools" / "downloads" / f"besu-{version}.tar.gz"
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {URL.format(v=version)}")
        urllib.request.urlretrieve(URL.format(v=version), cache)
    digest = hashlib.sha256(cache.read_bytes()).hexdigest()
    if digest != expected:
        cache.unlink()
        raise SystemExit(f"checksum mismatch for {cache.name}: {digest} != {expected} (file removed)")
    target = BESU.parents[1]
    with tempfile.TemporaryDirectory(dir=ROOT / "tools") as tmp, tarfile.open(cache) as tar:
        tar.extractall(tmp, filter="data")
        (top,) = Path(tmp).iterdir()                   # besu-<version>/
        if target.exists():
            shutil.rmtree(target)
        top.rename(target)
    BESU.chmod(0o755)
    print(subprocess.run([str(BESU), "--version"], capture_output=True, text=True, check=True).stdout.strip())
    print(f"installed {target} (sha256 {digest[:16]}…, Java {java_major()})")


if __name__ == "__main__":
    main()

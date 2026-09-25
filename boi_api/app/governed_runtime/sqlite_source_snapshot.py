"""Read-only sealing for immutable SQLite connector snapshots, never live WAL."""
from pathlib import Path
import hashlib


def sealed_sqlite_digest(path: Path, *, error_prefix: str = "") -> str:
    """Hash main bytes without pretending that uncheckpointed WAL is included.

    Callers doing SQL also pin a read transaction and compare before/after. This
    function never checkpoints, repairs, copies, or changes the source database.
    """
    requested_path = path
    # SQLite follows the real filename for its WAL, not the caller's symlink.
    # Pin it once so hashing and WAL inspection refer to the same source.
    path = path.resolve(strict=True)
    wal = Path(str(path) + "-wal")

    def check_wal():
        try:
            size = wal.stat().st_size
        except FileNotFoundError:
            size = 0
        if size:
            raise ValueError(error_prefix + "WAL_SNAPSHOT_UNSEALED")

    def identity():
        value = path.stat()
        return (value.st_dev, value.st_ino, value.st_size,
                value.st_mtime_ns, value.st_ctime_ns)

    check_wal()
    before = identity()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    check_wal()
    if requested_path.resolve(strict=True) != path or identity() != before:
        raise ValueError(error_prefix + "SOURCE_SNAPSHOT_DRIFT")
    return "sha256:" + digest.hexdigest()

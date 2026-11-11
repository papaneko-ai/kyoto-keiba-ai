"""Fail-closed cleanup for explicitly initialized, disposable local cache ONLY.

Does not touch Turso, protected race evidence, snapshots, backups or ledgers.
No scheduler, website access, or credentials.
"""
from __future__ import annotations
import os
import stat
from dataclasses import dataclass
from pathlib import Path

MARKER = ".kyoto_disposable_cache_v1"
PREFIX = "tmp_"
SUFFIX = ".cache"
MAX_CACHE_FILE_BYTES = 100_000_000
MAX_CACHE_FILES = 100_000

class ReclaimRejected(ValueError):
    pass

@dataclass(frozen=True)
class Candidate:
    name: str
    bytes: int
    mtime_ns: int
    inode: int
    device: int

def _positive_int(value, label):
    if type(value) is not int or value < 0:
        raise ReclaimRejected(label + "_invalid")
    return value

def _open_cache_dir(path):
    root = Path(path)
    if not root.is_absolute() or ".." in root.parts or root == Path("/"):
        raise ReclaimRejected("unsafe_cache_path")
    walk = root
    while True:
        if walk.is_symlink():
            raise ReclaimRejected("symlink_cache_path")
        if walk == walk.parent:
            break
        walk = walk.parent
    try:
        return os.open(root, os.O_RDONLY |
                       getattr(os, "O_DIRECTORY", 0) |
                       getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        raise ReclaimRejected("cache_dir_unavailable") from exc

def initialize_cache(path):
    """Opt-in ONLY with a new empty directory; never existing storage."""
    root = Path(path)
    if not root.is_absolute() or ".." in root.parts or root == Path("/"):
        raise ReclaimRejected("unsafe_cache_path")
    if root.exists() or root.is_symlink():
        raise ReclaimRejected("cache_directory_already_exists")
    if not root.parent.is_dir() or root.parent.is_symlink():
        raise ReclaimRejected("invalid_cache_parent")
    try:
        root.mkdir(mode=0o700)
        fd = _open_cache_dir(root)
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            marker_fd = os.open(MARKER, flags, 0o600, dir_fd=fd)
            with os.fdopen(marker_fd, "w", encoding="ascii") as f:
                f.write("KYOTO_DISPOSABLE_CACHE_V1\n")
                f.flush()
                os.fsync(f.fileno())
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError as exc:
        raise ReclaimRejected("cache_init_failed") from exc

def _validated_cache_fd(path):
    fd = _open_cache_dir(path)
    try:
        if os.fstat(fd).st_mode & stat.S_IWOTH:
            raise ReclaimRejected("world_writable_cache")
        st = os.stat(MARKER, dir_fd=fd, follow_symlinks=False)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            raise ReclaimRejected("unsafe_cache_marker")
        marker_fd = os.open(MARKER, os.O_RDONLY |
                            getattr(os, "O_NOFOLLOW", 0), dir_fd=fd)
        with os.fdopen(marker_fd, "rb") as f:
            if f.read(100) != b"KYOTO_DISPOSABLE_CACHE_V1\n":
                raise ReclaimRejected("cache_marker_mismatch")
        return fd
    except (OSError, ValueError) as exc:
        os.close(fd)
        if isinstance(exc, ReclaimRejected):
            raise
        raise ReclaimRejected("cache_not_initialized") from exc

def _scan(fd, now_ns, ttl_seconds):
    candidates, skipped = [], []
    names = os.listdir(fd)
    if len(names) > MAX_CACHE_FILES:
        raise ReclaimRejected("cache_entry_limit")
    for name in sorted(names):
        if name == MARKER:
            continue
        if not name.startswith(PREFIX) or not name.endswith(SUFFIX):
            skipped.append(name)
            continue
        st = os.stat(name, dir_fd=fd, follow_symlinks=False)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size > MAX_CACHE_FILE_BYTES:
            skipped.append(name)
            continue
        if st.st_mtime_ns > now_ns or now_ns - st.st_mtime_ns < ttl_seconds * 1_000_000_000:
            skipped.append(name)
            continue
        candidates.append(Candidate(name, st.st_size, st.st_mtime_ns, st.st_ino, st.st_dev))
    return sorted(candidates, key=lambda x: (x.mtime_ns, x.name)), skipped

def reclaim_disposable_cache(*, cache_dir, now_ns, ttl_seconds=86_400,
                             requested_free_bytes=0, dry_run=True):
    """Dry run by default; only TTL-expired opted-in temp files are eligible."""
    _positive_int(now_ns, "now_ns")
    _positive_int(ttl_seconds, "ttl_seconds")
    _positive_int(requested_free_bytes, "requested_free_bytes")
    if ttl_seconds < 3_600:
        raise ReclaimRejected("ttl_too_short")
    if type(dry_run) is not bool:
        raise ReclaimRejected("dry_run_not_boolean")
    fd = _validated_cache_fd(cache_dir)
    try:
        candidates, skipped = _scan(fd, now_ns, ttl_seconds)
        selected, projected = [], 0
        for candidate in candidates:
            if requested_free_bytes and projected >= requested_free_bytes:
                break
            selected.append(candidate)
            projected += candidate.bytes
        deleted, freed = [], 0
        if not dry_run:
            for candidate in selected:
                current = os.stat(candidate.name, dir_fd=fd, follow_symlinks=False)
                if (current.st_ino, current.st_dev, current.st_size, current.st_mtime_ns) != (
                    candidate.inode, candidate.device, candidate.bytes, candidate.mtime_ns
                ) or not stat.S_ISREG(current.st_mode) or current.st_nlink != 1:
                    raise ReclaimRejected("candidate_changed_during_reclaim")
                os.unlink(candidate.name, dir_fd=fd)
                deleted.append(candidate.name)
                freed += candidate.bytes
            os.fsync(fd)
        return {
            "scope": "DISPOSABLE_LOCAL_CACHE_ONLY",
            "dry_run": dry_run,
            "selected": [x.name for x in selected],
            "skipped_count": len(skipped),
            "freed_bytes": freed,
            "projected_bytes": projected,
            "deleted": deleted,
            "protected_record_deletions": 0,
        }
    finally:
        os.close(fd)

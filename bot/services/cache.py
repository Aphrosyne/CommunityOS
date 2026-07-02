"""
Cache Service — 通用文件缓存

缓存目录由调用方指定。按总字节数限制，最旧文件优先淘汰。
缓存失败回退正常流程，不影响主业务。

日志由调用方负责——缓存服务自身不记录普通事件。
"""
import os
import time
from pathlib import Path
import logging

_log = logging.getLogger(__name__)


class FileCache:
    """文件缓存，按总字节数限制，最旧文件淘汰"""

    def __init__(self, max_mb: int, cache_dir: Path, name: str = "cache"):
        self._max_bytes = max_mb * 1024 * 1024
        self._dir = cache_dir
        self._name = name
        self._dir.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> bytes | None:
        """查缓存"""
        try:
            path = self._dir / key
            if path.exists():
                os.utime(path, (time.time(), time.time()))
                return path.read_bytes()
        except Exception as e:
            _log.debug(f"[{self._name}] 读取缓存异常: {e}")
        return None

    def set(self, key: str, value: bytes) -> None:
        """写缓存，超限时淘汰最旧文件"""
        try:
            path = self._dir / key
            if path.exists():
                return
            path.write_bytes(value)
            self._evict()
        except Exception as e:
            _log.debug(f"[{self._name}] 写入缓存异常: {e}")

    def _evict(self) -> None:
        """淘汰最旧文件直到总大小在限制内"""
        try:
            files = sorted(
                (f for f in self._dir.iterdir() if f.is_file()),
                key=lambda f: f.stat().st_mtime,
            )
            total = sum(f.stat().st_size for f in files)
            while files and total > self._max_bytes:
                doomed = files.pop(0)
                total -= doomed.stat().st_size
                doomed.unlink()
        except Exception as e:
            _log.debug(f"[{self._name}] 淘汰异常: {e}")

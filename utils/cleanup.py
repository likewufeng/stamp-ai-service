# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-20
#Description: 定时清理 uploads / outputs / temp 过期文件
#FilePath: /stamp-ai-service/utils/cleanup.py
#
from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from loguru import logger


class FileCleanupService:
    """
    后台定时清理指定目录中的过期文件/子目录。

    规则：
    - 以 mtime（最后修改时间）判断是否超期
    - 目录：整目录 mtime 超期，或目录内已空且自身超期，则删除整个目录
    - 文件：mtime 超期则删除
    - 不会删除被清理的根目录本身（uploads/outputs/temp）
    """

    def __init__(
        self,
        directories: Sequence[Path],
        max_age_seconds: int = 24 * 60 * 60,
        interval_seconds: int = 60 * 60,
        enabled: bool = True,
    ):
        self.directories = [Path(item) for item in directories]
        self.max_age_seconds = max(60, int(max_age_seconds))
        self.interval_seconds = max(30, int(interval_seconds))
        self.enabled = bool(enabled)

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return (
            self._thread is not None
            and self._thread.is_alive()
        )

    def start(self) -> None:
        if not self.enabled:
            logger.info("文件清理任务未启用（CLEANUP_ENABLED=false）")
            return

        with self._lock:
            if self.is_running:
                return

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="file-cleanup",
                daemon=True,
            )
            self._thread.start()

            logger.info(
                "文件清理任务已启动 interval={}s max_age={}s dirs={}",
                self.interval_seconds,
                self.max_age_seconds,
                [str(path) for path in self.directories],
            )

    def stop(self, timeout: float = 5.0) -> None:
        with self._lock:
            if not self.is_running:
                return

            self._stop_event.set()
            thread = self._thread

        if thread is not None:
            thread.join(timeout=timeout)
            logger.info("文件清理任务已停止")

    def run_once(self) -> dict:
        """立即执行一次清理，返回统计信息。"""
        started = time.time()
        deleted_files = 0
        deleted_dirs = 0
        freed_bytes = 0
        errors: List[str] = []

        expire_before = time.time() - self.max_age_seconds

        for root in self.directories:
            try:
                root.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                errors.append(f"{root}: mkdir failed: {exc}")
                continue

            try:
                file_count, dir_count, bytes_count, dir_errors = (
                    self._cleanup_directory(
                        root=root,
                        expire_before=expire_before,
                    )
                )
                deleted_files += file_count
                deleted_dirs += dir_count
                freed_bytes += bytes_count
                errors.extend(dir_errors)
            except Exception as exc:
                logger.exception("清理目录失败 path={}", root)
                errors.append(f"{root}: {exc}")

        elapsed = round(time.time() - started, 3)
        result = {
            "deleted_files": deleted_files,
            "deleted_dirs": deleted_dirs,
            "freed_bytes": freed_bytes,
            "elapsed_seconds": elapsed,
            "errors": errors,
        }

        if deleted_files or deleted_dirs:
            logger.info(
                "文件清理完成 files={} dirs={} freed={}B elapsed={}s",
                deleted_files,
                deleted_dirs,
                freed_bytes,
                elapsed,
            )
        else:
            logger.debug(
                "文件清理完成：无过期文件 elapsed={}s",
                elapsed,
            )

        if errors:
            logger.warning(
                "文件清理存在错误 count={} sample={}",
                len(errors),
                errors[:3],
            )

        return result

    def _run_loop(self) -> None:
        # 启动后稍等，避免拖慢服务启动
        if self._stop_event.wait(5):
            return

        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception:
                logger.exception("文件清理循环异常")

            # 可被 stop 打断的等待
            self._stop_event.wait(self.interval_seconds)

    def _cleanup_directory(
        self,
        root: Path,
        expire_before: float,
    ) -> Tuple[int, int, int, List[str]]:
        """
        清理策略（适配本项目）：

        uploads/
          xxx.jpg          -> 单文件按 mtime 删除
        outputs/
          {request_id}/    -> 整个请求目录按“目录内最新内容 mtime”删除
        temp/
          ...              -> 同上
        """
        deleted_files = 0
        deleted_dirs = 0
        freed_bytes = 0
        errors: List[str] = []

        try:
            entries = list(root.iterdir())
        except Exception as exc:
            errors.append(f"{root}: scan failed: {exc}")
            return 0, 0, 0, errors

        for entry in entries:
            try:
                if not entry.exists():
                    continue

                if entry.is_symlink():
                    if self._path_mtime(entry) < expire_before:
                        size = self._safe_size(entry)
                        entry.unlink(missing_ok=True)
                        deleted_files += 1
                        freed_bytes += size
                    continue

                if entry.is_file():
                    if self._path_mtime(entry) < expire_before:
                        size = self._safe_size(entry)
                        entry.unlink(missing_ok=True)
                        deleted_files += 1
                        freed_bytes += size
                    continue

                if entry.is_dir():
                    newest = self._newest_mtime(entry)
                    if newest < expire_before:
                        file_count, size = self._count_tree(entry)
                        shutil.rmtree(entry, ignore_errors=True)
                        if not entry.exists():
                            deleted_dirs += 1
                            # 目录内文件也计入 deleted_files，便于观察
                            deleted_files += file_count
                            freed_bytes += size

            except Exception as exc:
                errors.append(f"{entry}: {exc}")

        return deleted_files, deleted_dirs, freed_bytes, errors

    @staticmethod
    def _path_mtime(path: Path) -> float:
        try:
            return float(path.stat().st_mtime)
        except OSError:
            return time.time()

    def _newest_mtime(self, directory: Path) -> float:
        """目录内所有文件/子目录的最新 mtime；空目录用自身 mtime。"""
        newest = self._path_mtime(directory)
        try:
            for item in directory.rglob("*"):
                try:
                    mtime = float(item.stat().st_mtime)
                except OSError:
                    continue
                if mtime > newest:
                    newest = mtime
        except OSError:
            pass
        return newest

    @staticmethod
    def _safe_size(path: Path) -> int:
        try:
            return int(path.stat().st_size)
        except OSError:
            return 0

    def _count_tree(self, directory: Path) -> Tuple[int, int]:
        """返回 (文件数, 总字节数)。"""
        file_count = 0
        total = 0
        try:
            for item in directory.rglob("*"):
                if item.is_file():
                    file_count += 1
                    total += self._safe_size(item)
        except OSError:
            pass
        return file_count, total


def create_default_cleanup_service() -> FileCleanupService:
    from config import (
        CLEANUP_DIRS,
        CLEANUP_ENABLED,
        CLEANUP_INTERVAL_SECONDS,
        CLEANUP_MAX_AGE_SECONDS,
    )

    return FileCleanupService(
        directories=CLEANUP_DIRS,
        max_age_seconds=CLEANUP_MAX_AGE_SECONDS,
        interval_seconds=CLEANUP_INTERVAL_SECONDS,
        enabled=CLEANUP_ENABLED,
    )


# 进程内单例，供 app lifespan 使用
cleanup_service = create_default_cleanup_service()

# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 09:39:53
#LastEditTime: 2026-07-22 10:27:09
#LastEditors: WuFeng <763467339@qq.com>
#Description: 配置文件 - 全部支持环境变量覆盖
#FilePath: /stamp-ai-service/config.py
#Copyright 版权声明
#
import os
from pathlib import Path


def _parse_bool(val: str, default: bool = False) -> bool:
    """解析布尔值环境变量"""
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(val: str, default: int) -> int:
    """解析整数环境变量"""
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _parse_extensions(val: str) -> set:
    """解析逗号分隔的扩展名集合"""
    if not val:
        return {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
    return {ext.strip().lower() for ext in val.split(",") if ext.strip()}


# ──────────────────────────────────────────────
# 基础路径（可通过环境变量覆盖，默认项目根目录下 data/）
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent

# 支持自定义数据根目录（如 /data/stamp-ai），默认 BASE_DIR/data
DATA_ROOT = Path(os.getenv("DATA_ROOT", BASE_DIR / "data")).resolve()

UPLOAD_DIR = DATA_ROOT / "uploads"
OUTPUT_DIR = DATA_ROOT / "outputs"
TEMP_DIR = DATA_ROOT / "temp"
LOG_DIR = DATA_ROOT / "logs"
MODEL_DIR = DATA_ROOT / "models"

for directory in (
    UPLOAD_DIR,
    OUTPUT_DIR,
    TEMP_DIR,
    LOG_DIR,
    MODEL_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────
# 应用基本信息
# ──────────────────────────────────────────────
APP_NAME = os.getenv("APP_NAME", "Stamp AI Service")
APP_VERSION = os.getenv("APP_VERSION", "0.6.0")


# ──────────────────────────────────────────────
# 上传/图片限制
# ──────────────────────────────────────────────
MAX_UPLOAD_BYTES = _parse_int(os.getenv("MAX_UPLOAD_BYTES"), 30 * 1024 * 1024)
MAX_IMAGE_PIXELS = _parse_int(os.getenv("MAX_IMAGE_PIXELS"), 60_000_000)

# 允许的文件扩展名（逗号分隔，如 .jpg,.png,.pdf）
ALLOWED_EXTENSIONS = _parse_extensions(os.getenv("ALLOWED_EXTENSIONS"))


# ──────────────────────────────────────────────
# 输出访问 URL 前缀（生产环境必须配置为公网域名/IP）
# 例：https://api.example.com/outputs 或 http://192.168.1.100:18080/outputs
# ──────────────────────────────────────────────
OUTPUT_URL_PREFIX = os.getenv("OUTPUT_URL_PREFIX", "http://127.0.0.1:18080/outputs").rstrip("/")


# ──────────────────────────────────────────────
# 定时清理配置
# ──────────────────────────────────────────────
CLEANUP_ENABLED = _parse_bool(os.getenv("CLEANUP_ENABLED"), True)
CLEANUP_INTERVAL_SECONDS = _parse_int(os.getenv("CLEANUP_INTERVAL_SECONDS"), 60 * 60)
CLEANUP_MAX_AGE_SECONDS = _parse_int(os.getenv("CLEANUP_MAX_AGE_SECONDS"), 24 * 60 * 60)

CLEANUP_DIRS = (
    UPLOAD_DIR,
    OUTPUT_DIR,
    TEMP_DIR,
)


# ──────────────────────────────────────────────
# 日志配置
# ──────────────────────────────────────────────
LOG_RETENTION_DAYS = _parse_int(os.getenv("LOG_RETENTION_DAYS"), 3)
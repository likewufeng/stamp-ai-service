# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 09:39:53
#LastEditTime: 2026-07-20 14:06:52
#LastEditors: WuFeng <763467339@qq.com>
#Description: 配置文件
#FilePath: /stamp-ai-service/config.py
#Copyright 版权声明
#
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
TEMP_DIR = BASE_DIR / "temp"
LOG_DIR = BASE_DIR / "logs"
MODEL_DIR = BASE_DIR / "models"

for directory in (
    UPLOAD_DIR,
    OUTPUT_DIR,
    TEMP_DIR,
    LOG_DIR,
    MODEL_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)


APP_NAME = "Stamp AI Service"
APP_VERSION = "0.6.0"

MAX_UPLOAD_BYTES = int(
    os.getenv("MAX_UPLOAD_BYTES", 30 * 1024 * 1024)
)

MAX_IMAGE_PIXELS = int(
    os.getenv("MAX_IMAGE_PIXELS", 60_000_000)
)

ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".webp",
    ".tif",
    ".tiff",
}

OUTPUT_URL_PREFIX = "/outputs"

# 定时清理 uploads / outputs / temp 中的过期文件
# CLEANUP_ENABLED: true/false
# CLEANUP_INTERVAL_SECONDS: 扫描间隔（秒），默认 1 小时
# CLEANUP_MAX_AGE_SECONDS: 文件/目录超过该时长则删除，默认 24 小时
CLEANUP_ENABLED = (
    os.getenv("CLEANUP_ENABLED", "true").strip().lower()
    in {"1", "true", "yes", "on"}
)

CLEANUP_INTERVAL_SECONDS = int(
    os.getenv("CLEANUP_INTERVAL_SECONDS", 60 * 60)
)

CLEANUP_MAX_AGE_SECONDS = int(
    os.getenv("CLEANUP_MAX_AGE_SECONDS", 24 * 60 * 60)
)

# 需要清理的目录（相对项目根或绝对路径由 config 统一管理）
CLEANUP_DIRS = (
    UPLOAD_DIR,
    OUTPUT_DIR,
    TEMP_DIR,
)

# 日志保留天数（loguru retention）
LOG_RETENTION_DAYS = int(
    os.getenv("LOG_RETENTION_DAYS", 3)
)
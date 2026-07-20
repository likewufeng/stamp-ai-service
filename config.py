# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 09:39:53
#LastEditTime: 2026-07-19 14:47:46
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
APP_VERSION = "0.5.0"

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
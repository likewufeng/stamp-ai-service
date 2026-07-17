# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 09:45:42
#LastEditTime: 2026-07-17 10:11:18
#LastEditors: WuFeng <763467339@qq.com>
#Description: 日志配置
#FilePath: /stamp-ai-service/utils/logger.py
#Copyright 版权声明
#
from loguru import logger

logger.add(
    "logs/service.log",
    rotation="50 MB",
    retention="30 days",
    level="INFO",
    encoding="utf-8"
)
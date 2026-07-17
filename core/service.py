# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 10:45:35
#LastEditTime: 2026-07-17 11:08:21
#LastEditors: WuFeng <763467339@qq.com>
#Description: 业务管理
#FilePath: /stamp-ai-service/core/service.py
#Copyright 版权声明
#
from pathlib import Path

from core.model_manager import model_manager
from schemas.stamp import StampDetectionResponse


class StampService:

    @staticmethod
    def process_image(file_path: str, debug: bool = False) -> StampDetectionResponse:
        stamps = model_manager.detector.detect(file_path, debug=debug)

        return StampDetectionResponse(
            filename=Path(file_path).name,
            stamps=stamps
        )
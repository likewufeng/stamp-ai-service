# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 10:45:35
#LastEditTime: 2026-07-17 10:48:55
#LastEditors: WuFeng <763467339@qq.com>
#Description: 业务管理
#FilePath: /stamp-ai-service/core/service.py
#Copyright 版权声明
#
from .model_manager import model_manager
from schemas.stamp import StampDetectionResponse

class StampService:
    @staticmethod
    def process_image(file_path: str) -> StampDetectionResponse:
        # 1. 调用检测器
        stamps = model_manager.detector.detect(file_path)
        
        # 2. 封装返回
        return StampDetectionResponse(
            filename=file_path.split("/")[-1],
            stamps=stamps
        )
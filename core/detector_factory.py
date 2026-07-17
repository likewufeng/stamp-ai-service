# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 10:45:35
#LastEditTime: 2026-07-17 10:48:32
#LastEditors: WuFeng <763467339@qq.com>
#Description: 实例化逻辑
#FilePath: /stamp-ai-service/core/detector_factory.py
#Copyright 版权声明
#
from .detector_base import OpencvDetector

class DetectorFactory:
    @staticmethod
    def create_detector(detector_type: str = "opencv"):
        if detector_type == "opencv":
            return OpencvDetector()
        # 以后可以扩展: elif detector_type == "yolo": return YoloDetector()
        raise ValueError(f"Unknown detector type: {detector_type}")
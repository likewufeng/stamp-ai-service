# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 10:45:35
#LastEditTime: 2026-07-17 15:49:51
#LastEditors: WuFeng <763467339@qq.com>
#Description: 实例化逻辑
#FilePath: /stamp-ai-service/core/detectors/detector_factory.py
#Copyright 版权声明
#
from core.detectors.detector_base import BaseDetector
from core.detectors.opencv_detector import OpenCVDetector


class DetectorFactory:

    @staticmethod
    def create_detector(
        name: str = "opencv",
    ) -> BaseDetector:
        normalized_name = name.strip().lower()

        if normalized_name == "opencv":
            return OpenCVDetector()

        raise ValueError(
            f"不支持的检测器类型: {name}"
        )
# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 10:45:35
#LastEditTime: 2026-07-17 11:09:51
#LastEditors: WuFeng <763467339@qq.com>
#Description: 实例化逻辑
#FilePath: /stamp-ai-service/core/detector_factory.py
#Copyright 版权声明
#
from core.detectors.opencv_detector import OpenCVDetector


class DetectorFactory:

    @staticmethod
    def create_detector(name="opencv"):
        """创建检测器实例"""
        if name == "opencv":
            return OpenCVDetector()

        raise ValueError(name)
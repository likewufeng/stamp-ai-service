# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 10:45:35
#LastEditTime: 2026-07-17 10:51:17
#LastEditors: WuFeng <763467339@qq.com>
#Description: 接口定义
#FilePath: /stamp-ai-service/core/detector_base.py
#Copyright 版权声明
#
from abc import ABC, abstractmethod
from typing import List
from schemas.stamp import StampBox
import cv2

class BaseDetector(ABC):
    @abstractmethod
    def detect(self, image_path: str) -> List[StampBox]:
        pass

# 一个简单的 OpenCV 示例实现，后面我们会替换成完整的逻辑
class OpencvDetector(BaseDetector):
    def detect(self, image_path: str) -> List[StampBox]:
        # TODO: 这里放我们上一版写的那套 OpenCV 检测逻辑
        # 暂时返回一个模拟框，用于测试整个流程是否打通
        return [StampBox(x=100, y=100, w=200, h=200)]
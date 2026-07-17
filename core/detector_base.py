# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 10:45:35
#LastEditTime: 2026-07-17 11:00:14
#LastEditors: WuFeng <763467339@qq.com>
#Description: 接口定义
#FilePath: /stamp-ai-service/core/detector_base.py
#Copyright 版权声明
#
from abc import ABC, abstractmethod
from typing import List

from schemas.stamp import StampBox


class BaseDetector(ABC):

    @abstractmethod
    def detect(self, image_path: str, debug: bool = False) -> List[StampBox]:
        raise NotImplementedError
# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 10:45:35
#LastEditTime: 2026-07-17 15:21:56
#LastEditors: WuFeng <763467339@qq.com>
#Description: 接口定义
#FilePath: /stamp-ai-service/core/detector_base.py
#Copyright 版权声明
#
from abc import ABC, abstractmethod
from typing import List

import numpy as np

from schemas.stamp import StampBox


class BaseDetector(ABC):

    @abstractmethod
    def detect_image(
        self,
        image: np.ndarray,
        debug: bool = False
    ) -> List[StampBox]:
        """
        输入opencv图片(BGR)
        输出印章框
        """
        pass
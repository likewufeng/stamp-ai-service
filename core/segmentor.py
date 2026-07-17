# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 11:21:37
#LastEditTime: 2026-07-17 11:22:55
#LastEditors: WuFeng <763467339@qq.com>
#Description: 图像分割器
#这个文件的作用只有一个：给一张裁剪后的印章图片，返回一张二值 Mask
#FilePath: /stamp-ai-service/core/segmentor.py
#Copyright 版权声明
#
# core/segmentor.py

from abc import ABC, abstractmethod
from typing import Tuple

import cv2
import numpy as np


class BaseSegmentor(ABC):
    @abstractmethod
    def segment(self, image: np.ndarray) -> np.ndarray:
        """
        返回 uint8 mask
        0~255
        """
        raise NotImplementedError


class OpenCVSegmentor(BaseSegmentor):
    """
    默认OpenCV分割器

    后面直接替换成BiRefNet即可
    API不用改
    """

    def segment(self, image: np.ndarray) -> np.ndarray:

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        lower_red1 = np.array([0, 30, 30])
        upper_red1 = np.array([15, 255, 255])

        lower_red2 = np.array([160, 30, 30])
        upper_red2 = np.array([180, 255, 255])

        red1 = cv2.inRange(
            hsv,
            lower_red1,
            upper_red1
        )

        red2 = cv2.inRange(
            hsv,
            lower_red2,
            upper_red2
        )

        mask = cv2.bitwise_or(red1, red2)

        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY
        )

        adaptive = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            31,
            10
        )

        mask = cv2.bitwise_or(
            mask,
            adaptive
        )

        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (3, 3)
        )

        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            kernel,
            iterations=2
        )

        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_OPEN,
            kernel,
            iterations=1
        )

        return mask
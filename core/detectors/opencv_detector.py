# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 10:58:36
#LastEditTime: 2026-07-19 10:57:58
#LastEditors: WuFeng <763467339@qq.com>
#Description: OpenCV 印章检测器
#FilePath: /stamp-ai-service/core/detectors/opencv_detector.py
#Copyright 版权声明
#
from typing import List

import cv2
import numpy as np

from core.detectors.detector_base import BaseDetector
from schemas.stamp import StampBox


class OpenCVDetector(BaseDetector):

    def detect_image(
        self,
        image: np.ndarray,
        debug: bool = False
    ) -> List[StampBox]:

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        lower1 = np.array([0, 40, 40])
        upper1 = np.array([15, 255, 255])

        lower2 = np.array([160, 40, 40])
        upper2 = np.array([180, 255, 255])

        mask1 = cv2.inRange(hsv, lower1, upper1)
        mask2 = cv2.inRange(hsv, lower2, upper2)

        mask = cv2.bitwise_or(mask1, mask2)

        kernel = np.ones((3, 3), np.uint8)

        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            kernel,
            iterations=2
        )

        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        result = []

        for c in contours:

            area = cv2.contourArea(c)

            if area < 500:
                continue

            x, y, w, h = cv2.boundingRect(c)

            result.append(
                StampBox(
                    x=int(x),
                    y=int(y),
                    w=int(w),
                    h=int(h),
                    confidence=1.0,
                    label="stamp",
                    color="red"
                )
            )

        return result
# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 10:58:36
#LastEditTime: 2026-07-17 10:58:36
#LastEditors: WuFeng <763467339@qq.com>
#Description: OpenCV 印章检测器
#FilePath: /stamp-ai-service/core/detectors/opencv_detector.py
#Copyright 版权声明
#
from typing import List

import cv2
import numpy as np

from schemas.stamp import StampBox
from core.detector_base import BaseDetector


class OpenCVDetector(BaseDetector):

    def detect(self, image_path: str) -> List[StampBox]:

        image = cv2.imread(image_path)

        if image is None:
            return []

        image = self.preprocess(image)

        mask = self.create_mask(image)

        mask = self.remove_table(mask)

        return self.find_stamps(mask)

    ########################################

    def preprocess(self, image):

        image = cv2.bilateralFilter(
            image,
            9,
            75,
            75
        )

        lab = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2LAB
        )

        l, a, b = cv2.split(lab)

        clahe = cv2.createCLAHE(
            clipLimit=2,
            tileGridSize=(8, 8)
        )

        l = clahe.apply(l)

        lab = cv2.merge((l, a, b))

        return cv2.cvtColor(
            lab,
            cv2.COLOR_LAB2BGR
        )

    ########################################

    def create_mask(self, image):

        hsv = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2HSV
        )

        lower_red1 = np.array([0, 40, 40])
        upper_red1 = np.array([15, 255, 255])

        lower_red2 = np.array([160, 40, 40])
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

        red = cv2.bitwise_or(red1, red2)

        lower_blue = np.array([90, 40, 40])
        upper_blue = np.array([140, 255, 255])

        blue = cv2.inRange(
            hsv,
            lower_blue,
            upper_blue
        )

        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY
        )

        _, black = cv2.threshold(
            gray,
            70,
            255,
            cv2.THRESH_BINARY_INV
        )

        mask = cv2.bitwise_or(red, blue)

        mask = cv2.bitwise_or(mask, black)

        kernel = np.ones((3, 3), np.uint8)

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

    ########################################

    def remove_table(self, mask):

        horizontal = mask.copy()

        cols = horizontal.shape[1]

        size = cols // 25

        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (size, 1)
        )

        horizontal = cv2.erode(
            horizontal,
            kernel
        )

        horizontal = cv2.dilate(
            horizontal,
            kernel
        )

        vertical = mask.copy()

        rows = vertical.shape[0]

        size = rows // 25

        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (1, size)
        )

        vertical = cv2.erode(
            vertical,
            kernel
        )

        vertical = cv2.dilate(
            vertical,
            kernel
        )

        table = cv2.bitwise_or(
            horizontal,
            vertical
        )

        return cv2.subtract(
            mask,
            table
        )

    ########################################

    def find_stamps(self, mask):

        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        stamps = []

        for c in contours:

            area = cv2.contourArea(c)

            if area < 500:
                continue

            x, y, w, h = cv2.boundingRect(c)

            ratio = w / h

            if ratio < 0.5 or ratio > 2:
                continue

            stamps.append(
                StampBox(
                    x=int(x),
                    y=int(y),
                    w=int(w),
                    h=int(h),
                    confidence=1.0
                )
            )

        return stamps
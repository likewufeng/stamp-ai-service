# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 11:23:19
#LastEditTime: 2026-07-19 10:36:32
#LastEditors: WuFeng <763467339@qq.com>
#Description: 图像透明度处理
#FilePath: /stamp-ai-service/core/utils/alpha.py
#Copyright 版权声明
#
# core/utils/alpha.py

from typing import Tuple

import cv2
import numpy as np


class AlphaComposer:

    def __init__(
        self,
        padding: int = 10,
        trim_threshold: int = 4,
    ):
        self.padding = max(0, padding)
        self.trim_threshold = max(
            0,
            min(255, trim_threshold),
        )

    def compose(
        self,
        image: np.ndarray,
        alpha: np.ndarray,
    ) -> np.ndarray:
        if image is None or image.size == 0:
            raise ValueError("图片为空")

        if alpha is None or alpha.size == 0:
            raise ValueError("Alpha Mask为空")

        alpha = self._normalize_alpha(
            image=image,
            alpha=alpha,
        )

        image, alpha = self._trim(
            image=image,
            alpha=alpha,
        )

        bgra = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2BGRA,
        )

        bgra[:, :, 3] = alpha

        transparent_pixels = alpha == 0
        bgra[transparent_pixels, 0:3] = 0

        return bgra

    @staticmethod
    def _normalize_alpha(
        image: np.ndarray,
        alpha: np.ndarray,
    ) -> np.ndarray:
        if alpha.ndim == 3:
            alpha = cv2.cvtColor(
                alpha,
                cv2.COLOR_BGR2GRAY,
            )

        image_height, image_width = image.shape[:2]

        if alpha.shape[:2] != (
            image_height,
            image_width,
        ):
            alpha = cv2.resize(
                alpha,
                (image_width, image_height),
                interpolation=cv2.INTER_LINEAR,
            )

        return np.clip(
            alpha,
            0,
            255,
        ).astype(np.uint8)

    def _trim(
        self,
        image: np.ndarray,
        alpha: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        binary = np.where(
            alpha > self.trim_threshold,
            255,
            0,
        ).astype(np.uint8)

        points = cv2.findNonZero(binary)

        if points is None:
            return image, alpha

        x, y, width, height = cv2.boundingRect(
            points
        )

        image_height, image_width = image.shape[:2]

        x1 = max(0, x - self.padding)
        y1 = max(0, y - self.padding)

        x2 = min(
            image_width,
            x + width + self.padding,
        )

        y2 = min(
            image_height,
            y + height + self.padding,
        )

        return (
            image[y1:y2, x1:x2],
            alpha[y1:y2, x1:x2],
        )
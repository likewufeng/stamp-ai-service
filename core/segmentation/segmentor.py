# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 11:21:37
#LastEditTime: 2026-07-19 10:36:04
#LastEditors: WuFeng <763467339@qq.com>
#Description: 图像分割器
#这个文件的作用只有一个：给一张裁剪后的印章图片，返回一张二值 Mask
#FilePath: /stamp-ai-service/core/segmentation/segmentor.py
#Copyright 版权声明
#
# core/segmentation/segmentor.py

from abc import ABC, abstractmethod

import cv2
import numpy as np

from core.utils.color_utils import (
    create_color_mask,
    remove_small_components,
)


class BaseSegmentor(ABC):

    @abstractmethod
    def segment(
        self,
        image: np.ndarray,
        color: str,
    ) -> np.ndarray:
        raise NotImplementedError


class OpenCVSegmentor(BaseSegmentor):

    def segment(
        self,
        image: np.ndarray,
        color: str,
    ) -> np.ndarray:
        if image is None or image.size == 0:
            raise ValueError("待分割图片为空")

        mask = create_color_mask(
            image,
            color=color,
            relaxed=True,
        )

        image_area = (
            image.shape[0] * image.shape[1]
        )

        min_component_area = max(
            2,
            int(image_area * 0.000008),
        )

        mask = remove_small_components(
            mask,
            min_area=min_component_area,
        )

        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (3, 3),
        )

        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            kernel,
            iterations=1,
        )

        return self._create_soft_alpha(mask)

    @staticmethod
    def _create_soft_alpha(
        mask: np.ndarray,
    ) -> np.ndarray:
        blurred = cv2.GaussianBlur(
            mask,
            (3, 3),
            0.7,
        )

        eroded = cv2.erode(
            mask,
            cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (3, 3),
            ),
            iterations=1,
        )

        alpha = blurred.copy()

        alpha[eroded > 0] = 255
        alpha[alpha < 4] = 0

        return alpha.astype(np.uint8)
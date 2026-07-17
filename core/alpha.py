# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 11:23:19
#LastEditTime: 2026-07-17 11:23:29
#LastEditors: WuFeng <763467339@qq.com>
#Description: 图像透明度处理
#FilePath: /stamp-ai-service/core/alpha.py
#Copyright 版权声明
#
# core/alpha.py

from typing import Optional, Tuple

import cv2
import numpy as np


class AlphaComposer:

    def __init__(
        self,
        feather_radius: int = 2,
        pad: int = 10,
        crop_whitespace: bool = True
    ):
        self.feather_radius = feather_radius
        self.pad = pad
        self.crop_whitespace = crop_whitespace

    def compose(
        self,
        image: np.ndarray,
        mask: np.ndarray
    ) -> np.ndarray:
        """
        输入: BGR图片 + 二值Mask
        输出: BGRA图片(透明背景)
        """

        # 确保尺寸一致
        mask = self._resize_mask(mask, image)

        # 边缘羽化
        alpha = self._feather_mask(mask)

        # 找外接矩形，裁剪空白区域
        if self.crop_whitespace:
            image, alpha = self._crop_by_mask(image, alpha)

        # 组合成BGRA
        bgra = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
        bgra[:, :, 3] = alpha

        return bgra

    # -------------------------------------------------
    # 内部方法
    # -------------------------------------------------

    def _resize_mask(
        self,
        mask: np.ndarray,
        image: np.ndarray
    ) -> np.ndarray:

        h_img, w_img = image.shape[:2]
        h_mask, w_mask = mask.shape[:2]

        if h_mask == h_img and w_mask == w_img:
            return mask

        return cv2.resize(
            mask,
            (w_img, h_img),
            interpolation=cv2.INTER_NEAREST
        )

    def _feather_mask(
        self,
        mask: np.ndarray
    ) -> np.ndarray:

        if self.feather_radius <= 0:
            return mask.copy()

        k = self.feather_radius * 2 + 1
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (k, k)
        )

        # 先膨胀再腐蚀，平滑边缘
        dilated = cv2.dilate(mask, kernel, iterations=1)
        eroded = cv2.erode(mask, kernel, iterations=1)

        # 在膨胀和腐蚀之间取中值
        blend = cv2.addWeighted(
            dilated.astype(np.float32),
            0.5,
            eroded.astype(np.float32),
            0.5,
            0
        )

        # 用高斯模糊柔化边缘
        blurred = cv2.GaussianBlur(
            blend,
            (k, k),
            0
        )

        alpha = np.clip(blurred, 0, 255).astype(np.uint8)

        # 保留原始mask内部区域为255
        alpha[mask > 0] = np.maximum(
            alpha[mask > 0],
            200
        )

        return alpha

    def _crop_by_mask(
        self,
        image: np.ndarray,
        alpha: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:

        coords = cv2.findNonZero(alpha)

        if coords is None:
            return image, alpha

        x, y, w, h = cv2.boundingRect(coords)

        # 加padding
        h_img, w_img = image.shape[:2]

        x1 = max(0, x - self.pad)
        y1 = max(0, y - self.pad)
        x2 = min(w_img, x + w + self.pad)
        y2 = min(h_img, y + h + self.pad)

        crop_image = image[y1:y2, x1:x2]
        crop_alpha = alpha[y1:y2, x1:x2]

        return crop_image, crop_alpha


# -------------------------------------------------
# 便捷函数，方便外部直接调用
# -------------------------------------------------

def make_transparent_png(
    image: np.ndarray,
    mask: np.ndarray,
    feather: int = 2,
    pad: int = 10
) -> np.ndarray:

    composer = AlphaComposer(
        feather_radius=feather,
        pad=pad
    )

    return composer.compose(image, mask)


def save_transparent_png(
    image: np.ndarray,
    mask: np.ndarray,
    output_path: str,
    feather: int = 2,
    pad: int = 10
) -> str:

    bgra = make_transparent_png(
        image,
        mask,
        feather=feather,
        pad=pad
    )

    cv2.imwrite(output_path, bgra)

    return output_path
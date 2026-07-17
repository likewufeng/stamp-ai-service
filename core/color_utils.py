# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 15:48:30
#LastEditTime: 2026-07-17 15:48:30
#LastEditors: WuFeng <763467339@qq.com>
#Description: 
#FilePath: /stamp-ai-service/core/color_utils.py
#Copyright 版权声明
#
import cv2
import numpy as np


def create_color_mask(
    image: np.ndarray,
    color: str,
    relaxed: bool = False,
) -> np.ndarray:
    if image is None or image.size == 0:
        raise ValueError("输入图片为空")

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)

    b, g, r = cv2.split(image.astype(np.int16))

    if color == "red":
        mask = _create_red_mask(
            hsv=hsv,
            lab=lab,
            b=b,
            g=g,
            r=r,
            relaxed=relaxed,
        )
    elif color == "blue":
        mask = _create_blue_mask(
            hsv=hsv,
            lab=lab,
            b=b,
            g=g,
            r=r,
            relaxed=relaxed,
        )
    else:
        raise ValueError(f"不支持的印章颜色: {color}")

    mask = cv2.medianBlur(mask, 3)

    return mask


def _create_red_mask(
    hsv: np.ndarray,
    lab: np.ndarray,
    b: np.ndarray,
    g: np.ndarray,
    r: np.ndarray,
    relaxed: bool,
) -> np.ndarray:
    saturation_min = 22 if relaxed else 30
    value_min = 25 if relaxed else 35

    hsv_red_1 = cv2.inRange(
        hsv,
        np.array([0, saturation_min, value_min], dtype=np.uint8),
        np.array([20, 255, 255], dtype=np.uint8),
    )

    hsv_red_2 = cv2.inRange(
        hsv,
        np.array([155, saturation_min, value_min], dtype=np.uint8),
        np.array([180, 255, 255], dtype=np.uint8),
    )

    hsv_mask = cv2.bitwise_or(hsv_red_1, hsv_red_2)

    red_dominance = r - np.maximum(g, b)
    dominance_threshold = 6 if relaxed else 10

    dominance_mask = np.where(
        (red_dominance >= dominance_threshold)
        & (r >= 55)
        & (r > g)
        & (r > b),
        255,
        0,
    ).astype(np.uint8)

    a_channel = lab[:, :, 1].astype(np.int16)
    b_channel = lab[:, :, 2].astype(np.int16)

    lab_threshold = 136 if relaxed else 141

    lab_mask = np.where(
        (a_channel >= lab_threshold)
        & ((a_channel - b_channel) >= 2)
        & (r >= 50),
        255,
        0,
    ).astype(np.uint8)

    result = cv2.bitwise_or(hsv_mask, dominance_mask)
    result = cv2.bitwise_or(result, lab_mask)

    return result


def _create_blue_mask(
    hsv: np.ndarray,
    lab: np.ndarray,
    b: np.ndarray,
    g: np.ndarray,
    r: np.ndarray,
    relaxed: bool,
) -> np.ndarray:
    saturation_min = 22 if relaxed else 30
    value_min = 25 if relaxed else 35

    hsv_mask = cv2.inRange(
        hsv,
        np.array([85, saturation_min, value_min], dtype=np.uint8),
        np.array([145, 255, 255], dtype=np.uint8),
    )

    blue_dominance = b - np.maximum(g, r)
    dominance_threshold = 5 if relaxed else 9

    dominance_mask = np.where(
        (blue_dominance >= dominance_threshold)
        & (b >= 50)
        & (b > r),
        255,
        0,
    ).astype(np.uint8)

    lab_b = lab[:, :, 2].astype(np.int16)

    lab_threshold = 123 if relaxed else 119

    lab_mask = np.where(
        (lab_b <= lab_threshold)
        & ((b - r) >= dominance_threshold)
        & (b >= 50),
        255,
        0,
    ).astype(np.uint8)

    result = cv2.bitwise_or(hsv_mask, dominance_mask)
    result = cv2.bitwise_or(result, lab_mask)

    return result


def remove_small_components(
    mask: np.ndarray,
    min_area: int,
) -> np.ndarray:
    if min_area <= 1:
        return mask.copy()

    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask,
        connectivity=8,
    )

    output = np.zeros_like(mask)

    for index in range(1, count):
        area = int(stats[index, cv2.CC_STAT_AREA])

        if area >= min_area:
            output[labels == index] = 255

    return output
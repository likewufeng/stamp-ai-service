# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 10:58:36
#LastEditTime: 2026-07-17 11:07:43
#LastEditors: WuFeng <763467339@qq.com>
#Description: OpenCV 印章检测器
#FilePath: /stamp-ai-service/core/detectors/opencv_detector.py
#Copyright 版权声明
#
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np

from config import OUTPUT_DIR
from core.detector_base import BaseDetector
from schemas.stamp import StampBox


class OpenCVDetector(BaseDetector):

    def __init__(self):
        self.max_side = 2200
        self.min_area_ratio = 0.00025
        self.min_wh = 28

    def detect(self, image_path: str, debug: bool = False) -> List[StampBox]:
        image = cv2.imread(image_path)
        if image is None:
            return []

        original = image.copy()

        image, scale = self._resize_keep_aspect(image)
        image = self._white_balance(image)
        image = self._enhance_contrast(image)
        image = cv2.bilateralFilter(image, 7, 60, 60)

        mask = self._build_candidate_mask(image)
        mask = self._remove_table_lines(image, mask)
        mask = self._refine_mask(mask)

        boxes = self._components_to_boxes(mask, image)
        boxes = self._merge_boxes(boxes)

        if scale != 1.0:
            inv = 1.0 / scale
            boxes = [self._rescale_box(box, inv) for box in boxes]

        if debug:
            self._save_debug_files(image_path, original, mask, boxes)

        return boxes

    # -------------------------------------------------
    # 预处理
    # -------------------------------------------------

    def _resize_keep_aspect(self, image):
        h, w = image.shape[:2]
        longest = max(h, w)
        if longest <= self.max_side:
            return image, 1.0

        scale = self.max_side / float(longest)
        new_w = int(w * scale)
        new_h = int(h * scale)

        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return resized, scale

    def _white_balance(self, image):
        img = image.astype(np.float32)
        b, g, r = cv2.split(img)

        b_avg = np.mean(b)
        g_avg = np.mean(g)
        r_avg = np.mean(r)

        k = (b_avg + g_avg + r_avg) / 3.0 + 1e-6

        b *= k / (b_avg + 1e-6)
        g *= k / (g_avg + 1e-6)
        r *= k / (r_avg + 1e-6)

        balanced = cv2.merge([b, g, r])
        balanced = np.clip(balanced, 0, 255).astype(np.uint8)
        return balanced

    def _enhance_contrast(self, image):
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)

        lab = cv2.merge((l, a, b))
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    # -------------------------------------------------
    # mask构建
    # -------------------------------------------------

    def _build_candidate_mask(self, image):
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 红章
        lower_red1 = np.array([0, 35, 35])
        upper_red1 = np.array([18, 255, 255])
        lower_red2 = np.array([160, 35, 35])
        upper_red2 = np.array([180, 255, 255])

        red1 = cv2.inRange(hsv, lower_red1, upper_red1)
        red2 = cv2.inRange(hsv, lower_red2, upper_red2)
        red = cv2.bitwise_or(red1, red2)

        # 额外利用 LAB 的 a 通道强化红色区域
        a_channel = lab[:, :, 1]
        red_lab = cv2.inRange(a_channel, 145, 255)
        red = cv2.bitwise_or(red, red_lab)

        # 蓝章
        lower_blue = np.array([90, 35, 35])
        upper_blue = np.array([140, 255, 255])
        blue = cv2.inRange(hsv, lower_blue, upper_blue)

        # 黑章 / 深色印章
        gray_blur = cv2.GaussianBlur(gray, (3, 3), 0)
        black = cv2.adaptiveThreshold(
            gray_blur,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            35,
            13
        )

        # 去小噪点、连起来
        kernel3 = np.ones((3, 3), np.uint8)
        black = cv2.morphologyEx(black, cv2.MORPH_OPEN, kernel3, iterations=1)
        black = cv2.morphologyEx(black, cv2.MORPH_CLOSE, kernel3, iterations=2)

        mask = cv2.bitwise_or(red, blue)
        mask = cv2.bitwise_or(mask, black)

        return mask

    def _remove_table_lines(self, image, mask):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        bin_img = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            35,
            15
        )

        h, w = bin_img.shape[:2]

        h_len = max(20, w // 25)
        v_len = max(20, h // 25)

        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_len, 1))
        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_len))

        horizontal = cv2.erode(bin_img, h_kernel, iterations=1)
        horizontal = cv2.dilate(horizontal, h_kernel, iterations=1)

        vertical = cv2.erode(bin_img, v_kernel, iterations=1)
        vertical = cv2.dilate(vertical, v_kernel, iterations=1)

        table_lines = cv2.bitwise_or(horizontal, vertical)
        table_lines = cv2.dilate(table_lines, np.ones((3, 3), np.uint8), iterations=1)

        cleaned = cv2.bitwise_and(mask, cv2.bitwise_not(table_lines))
        return cleaned

    def _refine_mask(self, mask):
        h, w = mask.shape[:2]
        k = max(3, int(min(h, w) * 0.004))
        if k % 2 == 0:
            k += 1

        close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        open_kernel = np.ones((3, 3), np.uint8)

        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel, iterations=1)
        mask = self._fill_holes(mask)

        return mask

    def _fill_holes(self, mask):
        h, w = mask.shape[:2]
        flood = mask.copy()
        ff_mask = np.zeros((h + 2, w + 2), np.uint8)
        cv2.floodFill(flood, ff_mask, (0, 0), 255)
        flood_inv = cv2.bitwise_not(flood)
        return cv2.bitwise_or(mask, flood_inv)

    # -------------------------------------------------
    # 候选框提取
    # -------------------------------------------------

    def _components_to_boxes(self, mask, image) -> List[StampBox]:
        h, w = mask.shape[:2]
        image_area = h * w
        min_area = max(800, int(image_area * self.min_area_ratio))

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)

        results: List[StampBox] = []

        for idx in range(1, num_labels):
            x, y, bw, bh, area = stats[idx]

            if area < min_area:
                continue
            if bw < self.min_wh or bh < self.min_wh:
                continue

            ratio = bw / float(bh + 1e-6)
            if ratio < 0.30 or ratio > 3.50:
                continue

            bbox_area = bw * bh
            extent = area / float(bbox_area + 1e-6)
            if extent < 0.035:
                continue

            comp_mask = (labels == idx).astype(np.uint8) * 255
            contours, _ = cv2.findContours(comp_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue

            cnt = max(contours, key=cv2.contourArea)
            contour_area = cv2.contourArea(cnt)
            perimeter = cv2.arcLength(cnt, True)

            circularity = 0.0
            if perimeter > 0:
                circularity = 4.0 * np.pi * contour_area / (perimeter * perimeter + 1e-6)

            # 过滤掉特别碎、特别像文字段落的区域
            if extent < 0.05 and circularity < 0.03:
                continue

            color = self._guess_color(image, x, y, bw, bh)

            results.append(
                StampBox(
                    x=int(x),
                    y=int(y),
                    w=int(bw),
                    h=int(bh),
                    confidence=1.0,
                    label="stamp",
                    color=color
                )
            )

        return results

    def _guess_color(self, image, x, y, w, h):
        h_img, w_img = image.shape[:2]
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(w_img, x + w)
        y2 = min(h_img, y + h)

        roi = image[y1:y2, x1:x2]
        if roi.size == 0:
            return "unknown"

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        red1 = cv2.inRange(hsv, np.array([0, 35, 35]), np.array([18, 255, 255]))
        red2 = cv2.inRange(hsv, np.array([160, 35, 35]), np.array([180, 255, 255]))
        red = cv2.countNonZero(cv2.bitwise_or(red1, red2))

        blue = cv2.countNonZero(cv2.inRange(hsv, np.array([90, 35, 35]), np.array([140, 255, 255])))

        black = cv2.countNonZero(cv2.inRange(gray, 0, 90))

        if red >= blue and red >= black and red > roi.shape[0] * roi.shape[1] * 0.01:
            return "red"
        if blue >= red and blue >= black and blue > roi.shape[0] * roi.shape[1] * 0.01:
            return "blue"
        if black > roi.shape[0] * roi.shape[1] * 0.02:
            return "black"

        return "unknown"

    # -------------------------------------------------
    # 框合并
    # -------------------------------------------------

    def _merge_boxes(self, boxes: List[StampBox]) -> List[StampBox]:
        if not boxes:
            return []

        merged: List[StampBox] = []
        boxes = sorted(boxes, key=lambda b: b.w * b.h, reverse=True)

        for box in boxes:
            placed = False
            for i, exist in enumerate(merged):
                if self._boxes_close(exist, box, margin=12):
                    merged[i] = self._union_box(exist, box)
                    placed = True
                    break
            if not placed:
                merged.append(box)

        # 再做一轮，防止链式合并
        changed = True
        while changed:
            changed = False
            new_list: List[StampBox] = []
            used = [False] * len(merged)

            for i in range(len(merged)):
                if used[i]:
                    continue
                cur = merged[i]
                for j in range(i + 1, len(merged)):
                    if used[j]:
                        continue
                    if self._boxes_close(cur, merged[j], margin=12):
                        cur = self._union_box(cur, merged[j])
                        used[j] = True
                        changed = True
                new_list.append(cur)
                used[i] = True

            merged = new_list

        return sorted(merged, key=lambda b: (b.y, b.x))

    def _boxes_close(self, a: StampBox, b: StampBox, margin: int = 12) -> bool:
        ax1, ay1, ax2, ay2 = a.x, a.y, a.x + a.w, a.y + a.h
        bx1, by1, bx2, by2 = b.x, b.y, b.x + b.w, b.y + b.h

        ax1 -= margin
        ay1 -= margin
        ax2 += margin
        ay2 += margin

        bx1 -= margin
        by1 -= margin
        bx2 += margin
        by2 += margin

        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)

        return inter_x1 <= inter_x2 and inter_y1 <= inter_y2

    def _union_box(self, a: StampBox, b: StampBox) -> StampBox:
        x1 = min(a.x, b.x)
        y1 = min(a.y, b.y)
        x2 = max(a.x + a.w, b.x + b.w)
        y2 = max(a.y + a.h, b.y + b.h)

        color = a.color if a.color != "unknown" else b.color

        return StampBox(
            x=int(x1),
            y=int(y1),
            w=int(x2 - x1),
            h=int(y2 - y1),
            confidence=max(a.confidence, b.confidence),
            label="stamp",
            color=color
        )

    def _rescale_box(self, box: StampBox, factor: float) -> StampBox:
        return StampBox(
            x=int(box.x * factor),
            y=int(box.y * factor),
            w=int(box.w * factor),
            h=int(box.h * factor),
            confidence=box.confidence,
            label=box.label,
            color=box.color
        )

    # -------------------------------------------------
    # debug
    # -------------------------------------------------

    def _save_debug_files(self, image_path, original, mask, boxes):
        debug_dir = OUTPUT_DIR / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)

        stem = Path(image_path).stem

        mask_path = debug_dir / f"{stem}_mask.png"
        annotated_path = debug_dir / f"{stem}_annotated.png"

        cv2.imwrite(str(mask_path), mask)

        annotated = original.copy()
        for idx, box in enumerate(boxes, start=1):
            x1, y1 = box.x, box.y
            x2, y2 = box.x + box.w, box.y + box.h

            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                annotated,
                f"{idx}:{box.color}",
                (x1, max(0, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )

        cv2.imwrite(str(annotated_path), annotated)
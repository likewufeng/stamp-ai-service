# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 14:21:52
#LastEditTime: 2026-07-20 09:10:35
#LastEditors: WuFeng <763467339@qq.com>
#Description: 文档预处理器
#FilePath: /stamp-ai-service/core/processors/document_processor.py
#Copyright 版权声明
#
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np


@dataclass(frozen=True)
class DocumentProcessResult:
    image: np.ndarray
    analysis_image: np.ndarray
    perspective_applied: bool


class DocumentProcessor:

    def __init__(
        self,
        max_side: int = 2400,
    ):
        self.max_side = max_side

    def process(
        self,
        image: np.ndarray,
        correct_perspective: bool = True,
        correct_orientation: bool = False,
    ) -> DocumentProcessResult:
        if image is None or image.size == 0:
            raise ValueError("输入文档图片为空")

        working_image = image.copy()
        perspective_applied = False

        # 自动矫正透视
        if correct_perspective:
            corrected = self._try_perspective_correction(
                working_image
            )

            if corrected is not None:
                working_image = corrected
                perspective_applied = True

        # 自动旋转方向
        if correct_orientation:
          working_image = (
              self._try_orientation_correction(
                  working_image
              )
          )

        working_image = self._resize_max_side(
            working_image
        )

        analysis_image = self._create_analysis_image(
            working_image
        )

        return DocumentProcessResult(
            image=working_image,
            analysis_image=analysis_image,
            perspective_applied=perspective_applied,
        )
    
    def _try_orientation_correction(
        self,
        image: np.ndarray,
    ) -> np.ndarray:
        """
        自动尝试 0°/90°/180°/270°。

        只有当最佳方向明显优于其它方向时，
        才进行旋转。
        """

        candidates = [
            image,
            cv2.rotate(
                image,
                cv2.ROTATE_90_CLOCKWISE,
            ),
            cv2.rotate(
                image,
                cv2.ROTATE_180,
            ),
            cv2.rotate(
                image,
                cv2.ROTATE_90_COUNTERCLOCKWISE,
            ),
        ]

        scores = [
            self._orientation_score(img)
            for img in candidates
        ]

        best_index = int(
            np.argmax(scores)
        )

        sorted_scores = sorted(
            scores,
            reverse=True,
        )

        best_score = sorted_scores[0]
        second_score = sorted_scores[1]

        # 只有当领先明显时才旋转
        margin = (
            abs(best_score) * 0.12
        )

        margin = max(
            margin,
            120,
        )

        if (
            best_score - second_score
        ) < margin:
            return image

        return candidates[best_index]
    

    @staticmethod
    def _orientation_score(
        image: np.ndarray,
    ) -> float:
        """
        文档方向评分。

        分数越高，
        越可能是正常方向。

        注意：
        对于没有方向信息（如只有印章）的图片，
        四个方向分数会非常接近，
        上层不会自动旋转。
        """

        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY,
        )

        _, binary = cv2.threshold(
            gray,
            0,
            255,
            cv2.THRESH_BINARY_INV
            + cv2.THRESH_OTSU,
        )

        height, width = binary.shape

        top = binary[
            : height // 4,
            :
        ]

        bottom = binary[
            height * 3 // 4 :,
            :
        ]

        top_pixels = cv2.countNonZero(
            top
        )

        bottom_pixels = cv2.countNonZero(
            bottom
        )

        horizontal_kernel = (
            cv2.getStructuringElement(
                cv2.MORPH_RECT,
                (
                    max(
                        20,
                        width // 20,
                    ),
                    1,
                ),
            )
        )

        vertical_kernel = (
            cv2.getStructuringElement(
                cv2.MORPH_RECT,
                (
                    1,
                    max(
                        20,
                        height // 20,
                    ),
                ),
            )
        )

        horizontal = cv2.morphologyEx(
            binary,
            cv2.MORPH_OPEN,
            horizontal_kernel,
        )

        vertical = cv2.morphologyEx(
            binary,
            cv2.MORPH_OPEN,
            vertical_kernel,
        )

        horizontal_score = (
            cv2.countNonZero(
                horizontal
            )
        )

        vertical_score = (
            cv2.countNonZero(
                vertical
            )
        )

        score = 0.0

        # 文档通常顶部信息更多
        score += (
            top_pixels
            - bottom_pixels
        ) * 0.3

        # 正常方向一般横线更多
        score += (
            horizontal_score
            - vertical_score
        ) * 0.8

        # 文档通常竖版
        if height >= width:
            score += 200

        return float(score)
    

    def _resize_max_side(
        self,
        image: np.ndarray,
    ) -> np.ndarray:
        height, width = image.shape[:2]
        longest = max(height, width)

        if longest <= self.max_side:
            return image

        scale = self.max_side / float(longest)

        new_width = max(
            1,
            int(round(width * scale)),
        )

        new_height = max(
            1,
            int(round(height * scale)),
        )

        return cv2.resize(
            image,
            (new_width, new_height),
            interpolation=cv2.INTER_AREA,
        )

    def _create_analysis_image(
        self,
        image: np.ndarray,
    ) -> np.ndarray:
        balanced = self._white_balance(image)

        lab = cv2.cvtColor(
            balanced,
            cv2.COLOR_BGR2LAB,
        )

        lightness, channel_a, channel_b = cv2.split(
            lab
        )

        clahe = cv2.createCLAHE(
            clipLimit=1.8,
            tileGridSize=(8, 8),
        )

        lightness = clahe.apply(lightness)

        enhanced_lab = cv2.merge(
            (lightness, channel_a, channel_b)
        )

        enhanced = cv2.cvtColor(
            enhanced_lab,
            cv2.COLOR_LAB2BGR,
        )

        return cv2.bilateralFilter(
            enhanced,
            5,
            35,
            35,
        )

    @staticmethod
    def _white_balance(
        image: np.ndarray,
    ) -> np.ndarray:
        float_image = image.astype(np.float32)

        blue, green, red = cv2.split(float_image)

        blue_average = float(np.mean(blue))
        green_average = float(np.mean(green))
        red_average = float(np.mean(red))

        global_average = (
            blue_average
            + green_average
            + red_average
        ) / 3.0

        blue *= global_average / (
            blue_average + 1e-6
        )

        green *= global_average / (
            green_average + 1e-6
        )

        red *= global_average / (
            red_average + 1e-6
        )

        balanced = cv2.merge(
            (blue, green, red)
        )

        return np.clip(
            balanced,
            0,
            255,
        ).astype(np.uint8)

    def _try_perspective_correction(
        self,
        image: np.ndarray,
    ) -> Optional[np.ndarray]:
        original_height, original_width = (
            image.shape[:2]
        )

        preview_max_side = 1400
        longest = max(
            original_height,
            original_width,
        )

        preview_scale = min(
            1.0,
            preview_max_side / float(longest),
        )

        if preview_scale < 1.0:
            preview = cv2.resize(
                image,
                (
                    int(original_width * preview_scale),
                    int(original_height * preview_scale),
                ),
                interpolation=cv2.INTER_AREA,
            )
        else:
            preview = image.copy()

        quad = self._detect_document_quad(preview)

        if quad is None:
            return None

        quad = quad / preview_scale

        return self._warp_by_quad(
            image,
            quad.astype(np.float32),
        )

    def _detect_document_quad(
        self,
        image: np.ndarray,
    ) -> Optional[np.ndarray]:
        height, width = image.shape[:2]
        image_area = height * width

        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY,
        )

        gray = cv2.GaussianBlur(
            gray,
            (5, 5),
            0,
        )

        median_value = float(np.median(gray))

        lower = int(
            max(0, 0.66 * median_value)
        )

        upper = int(
            min(255, 1.33 * median_value)
        )

        edges = cv2.Canny(
            gray,
            lower,
            upper,
        )

        edges = cv2.morphologyEx(
            edges,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(
                cv2.MORPH_RECT,
                (7, 7),
            ),
            iterations=2,
        )

        contours, _ = cv2.findContours(
            edges,
            cv2.RETR_LIST,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        contours = sorted(
            contours,
            key=cv2.contourArea,
            reverse=True,
        )[:30]

        best_quad = None
        best_score = 0.0

        for contour in contours:
            area = cv2.contourArea(contour)
            area_ratio = area / float(image_area)

            if area_ratio < 0.45:
                continue

            perimeter = cv2.arcLength(
                contour,
                True,
            )

            approximation = cv2.approxPolyDP(
                contour,
                0.02 * perimeter,
                True,
            )

            if len(approximation) != 4:
                continue

            quad = approximation.reshape(
                4,
                2,
            ).astype(np.float32)

            if not cv2.isContourConvex(
                approximation
            ):
                continue

            ordered = self._order_points(quad)

            target_width, target_height = (
                self._quad_dimensions(ordered)
            )

            if target_width < 100 or target_height < 100:
                continue

            short_side = min(
                target_width,
                target_height,
            )

            long_side = max(
                target_width,
                target_height,
            )

            paper_ratio = short_side / float(
                long_side
            )

            # A4、Letter以及常见文档的保守范围
            if paper_ratio < 0.54 or paper_ratio > 0.86:
                continue

            x, y, box_width, box_height = (
                cv2.boundingRect(
                    approximation
                )
            )

            coverage_width = (
                box_width / float(width)
            )

            coverage_height = (
                box_height / float(height)
            )

            if coverage_width < 0.55:
                continue

            if coverage_height < 0.55:
                continue

            border_contrast = (
                self._calculate_border_contrast(
                    image,
                    ordered,
                )
            )

            # 避免把文档内部的大表格误认为纸张边界
            if (
                border_contrast < 7.0
                and area_ratio < 0.88
            ):
                continue

            ratio_score = max(
                0.0,
                1.0 - abs(paper_ratio - 0.707),
            )

            score = (
                area_ratio * 0.65
                + ratio_score * 0.20
                + min(border_contrast / 30.0, 1.0)
                * 0.15
            )

            if score > best_score:
                best_score = score
                best_quad = ordered

        return best_quad

    @staticmethod
    def _calculate_border_contrast(
        image: np.ndarray,
        quad: np.ndarray,
    ) -> float:
        mask = np.zeros(
            image.shape[:2],
            dtype=np.uint8,
        )

        cv2.fillConvexPoly(
            mask,
            quad.astype(np.int32),
            255,
        )

        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (15, 15),
        )

        eroded = cv2.erode(
            mask,
            kernel,
            iterations=1,
        )

        dilated = cv2.dilate(
            mask,
            kernel,
            iterations=1,
        )

        inner_ring = cv2.subtract(
            mask,
            eroded,
        )

        outer_ring = cv2.subtract(
            dilated,
            mask,
        )

        if cv2.countNonZero(inner_ring) < 20:
            return 0.0

        if cv2.countNonZero(outer_ring) < 20:
            return 0.0

        inner_mean = np.array(
            cv2.mean(image, mask=inner_ring)[:3]
        )

        outer_mean = np.array(
            cv2.mean(image, mask=outer_ring)[:3]
        )

        return float(
            np.linalg.norm(
                inner_mean - outer_mean
            )
        )

    @staticmethod
    def _order_points(
        points: np.ndarray,
    ) -> np.ndarray:
        ordered = np.zeros(
            (4, 2),
            dtype=np.float32,
        )

        sums = points.sum(axis=1)
        differences = np.diff(
            points,
            axis=1,
        ).reshape(-1)

        ordered[0] = points[np.argmin(sums)]
        ordered[2] = points[np.argmax(sums)]

        ordered[1] = points[
            np.argmin(differences)
        ]

        ordered[3] = points[
            np.argmax(differences)
        ]

        return ordered

    @staticmethod
    def _quad_dimensions(
        quad: np.ndarray,
    ):
        top_left, top_right, bottom_right, bottom_left = quad

        width_top = np.linalg.norm(
            top_right - top_left
        )

        width_bottom = np.linalg.norm(
            bottom_right - bottom_left
        )

        height_left = np.linalg.norm(
            bottom_left - top_left
        )

        height_right = np.linalg.norm(
            bottom_right - top_right
        )

        return (
            int(max(width_top, width_bottom)),
            int(max(height_left, height_right)),
        )

    def _warp_by_quad(
        self,
        image: np.ndarray,
        quad: np.ndarray,
    ) -> Optional[np.ndarray]:
        ordered = self._order_points(quad)

        width, height = self._quad_dimensions(
            ordered
        )

        if width < 100 or height < 100:
            return None

        destination = np.array(
            [
                [0, 0],
                [width - 1, 0],
                [width - 1, height - 1],
                [0, height - 1],
            ],
            dtype=np.float32,
        )

        matrix = cv2.getPerspectiveTransform(
            ordered,
            destination,
        )

        return cv2.warpPerspective(
            image,
            matrix,
            (width, height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
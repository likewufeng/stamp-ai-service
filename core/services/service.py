# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 10:45:35
#LastEditTime: 2026-07-19 10:34:48
#LastEditors: WuFeng <763467339@qq.com>
#Description: 业务管理
#FilePath: /stamp-ai-service/core/services/service.py
#Copyright 版权声明
#
import uuid
import zipfile
from pathlib import Path
from typing import List

import cv2
import numpy as np
from PIL import Image, ImageOps

from config import (
    MAX_IMAGE_PIXELS,
    OUTPUT_DIR,
    OUTPUT_URL_PREFIX,
)
from core.utils.alpha import AlphaComposer
from core.services.model_manager import model_manager
from core.processors.document_processor import (
    DocumentProcessor,
)
from schemas.stamp import (
    StampBox,
    StampExtractionResponse,
    StampOutput,
)


class StampService:

    def __init__(self):
        self.processor = DocumentProcessor()
        self.alpha_composer = AlphaComposer(
            padding=10,
            trim_threshold=4,
        )

    def process_image(
        self,
        file_path: str,
        source_filename: str,
        debug: bool = False,
        correct_perspective: bool = True,
    ) -> StampExtractionResponse:
        request_id = uuid.uuid4().hex

        request_output_dir = (
            OUTPUT_DIR / request_id
        )

        request_output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        original_image = self._load_image(
            file_path
        )

        original_height, original_width = (
            original_image.shape[:2]
        )

        document = self.processor.process(
            original_image,
            correct_perspective=correct_perspective,
        )

        processed_image = document.image
        analysis_image = document.analysis_image

        processed_height, processed_width = (
            processed_image.shape[:2]
        )

        boxes = (
            model_manager.detector.detect_image(
                analysis_image,
                debug=debug,
            )
        )

        stamp_outputs: List[StampOutput] = []
        stamp_paths: List[Path] = []
        debug_urls: List[str] = []

        for box in boxes:
            cropped = self._crop_with_padding(
                processed_image,
                box,
            )

            if cropped.size == 0:
                continue

            alpha = model_manager.segmentor.segment(
                cropped,
                color=box.color,
            )

            if cv2.countNonZero(
                np.where(
                    alpha > 4,
                    255,
                    0,
                ).astype(np.uint8)
            ) < 20:
                continue

            transparent_stamp = (
                self.alpha_composer.compose(
                    cropped,
                    alpha,
                )
            )

            index = len(stamp_outputs) + 1

            file_name = (
                f"stamp_{index:03d}.png"
            )

            output_path = (
                request_output_dir / file_name
            )

            self._save_image(
                output_path,
                transparent_stamp,
            )

            stamp_paths.append(output_path)

            output_height, output_width = (
                transparent_stamp.shape[:2]
            )

            stamp_outputs.append(
                StampOutput(
                    index=index,
                    box=box,
                    width=output_width,
                    height=output_height,
                    file_name=file_name,
                    url=self._build_output_url(
                        request_id,
                        file_name,
                    ),
                )
            )

            if debug:
                mask_name = (
                    f"stamp_{index:03d}_alpha.png"
                )

                mask_path = (
                    request_output_dir / mask_name
                )

                self._save_image(
                    mask_path,
                    alpha,
                )

                debug_urls.append(
                    self._build_output_url(
                        request_id,
                        mask_name,
                    )
                )

        if debug:
            debug_urls.extend(
                self._save_debug_files(
                    request_id=request_id,
                    output_dir=request_output_dir,
                    document_image=processed_image,
                    analysis_image=analysis_image,
                    boxes=boxes,
                )
            )

        zip_url = None

        if stamp_paths:
            zip_name = "stamps.zip"
            zip_path = request_output_dir / zip_name

            self._create_zip(
                zip_path=zip_path,
                image_paths=stamp_paths,
            )

            zip_url = self._build_output_url(
                request_id,
                zip_name,
            )

        return StampExtractionResponse(
            request_id=request_id,
            filename=source_filename,
            original_width=original_width,
            original_height=original_height,
            processed_width=processed_width,
            processed_height=processed_height,
            perspective_applied=(
                document.perspective_applied
            ),
            count=len(stamp_outputs),
            stamps=stamp_outputs,
            zip_url=zip_url,
            debug_files=debug_urls,
        )

    @staticmethod
    def _load_image(
        file_path: str,
    ) -> np.ndarray:
        with Image.open(file_path) as pil_image:
            pil_image = ImageOps.exif_transpose(
                pil_image
            )

            width, height = pil_image.size

            if width * height > MAX_IMAGE_PIXELS:
                raise ValueError(
                    "图片像素数量过大，"
                    f"最大允许 {MAX_IMAGE_PIXELS} 像素"
                )

            if pil_image.mode in (
                "RGBA",
                "LA",
            ) or (
                pil_image.mode == "P"
                and "transparency"
                in pil_image.info
            ):
                rgba = pil_image.convert("RGBA")

                background = Image.new(
                    "RGBA",
                    rgba.size,
                    (255, 255, 255, 255),
                )

                pil_image = Image.alpha_composite(
                    background,
                    rgba,
                ).convert("RGB")
            else:
                pil_image = pil_image.convert("RGB")

            rgb = np.asarray(
                pil_image,
                dtype=np.uint8,
            )

        return cv2.cvtColor(
            rgb,
            cv2.COLOR_RGB2BGR,
        )

    @staticmethod
    def _crop_with_padding(
        image: np.ndarray,
        box: StampBox,
    ) -> np.ndarray:
        image_height, image_width = image.shape[:2]

        padding = max(
            8,
            int(round(max(box.w, box.h) * 0.08)),
        )

        x1 = max(0, box.x - padding)
        y1 = max(0, box.y - padding)

        x2 = min(
            image_width,
            box.x + box.w + padding,
        )

        y2 = min(
            image_height,
            box.y + box.h + padding,
        )

        return image[y1:y2, x1:x2].copy()

    def _save_debug_files(
        self,
        request_id: str,
        output_dir: Path,
        document_image: np.ndarray,
        analysis_image: np.ndarray,
        boxes: List[StampBox],
    ) -> List[str]:
        debug_urls: List[str] = []

        document_name = "debug_document.jpg"
        analysis_name = "debug_analysis.jpg"
        annotated_name = "debug_annotated.jpg"

        self._save_image(
            output_dir / document_name,
            document_image,
        )

        self._save_image(
            output_dir / analysis_name,
            analysis_image,
        )

        annotated = document_image.copy()

        for index, box in enumerate(
            boxes,
            start=1,
        ):
            x1 = box.x
            y1 = box.y
            x2 = box.x + box.w
            y2 = box.y + box.h

            cv2.rectangle(
                annotated,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                3,
            )

            cv2.putText(
                annotated,
                (
                    f"{index} "
                    f"{box.color} "
                    f"{box.confidence:.2f}"
                ),
                (x1, max(25, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 180, 0),
                2,
                cv2.LINE_AA,
            )

        self._save_image(
            output_dir / annotated_name,
            annotated,
        )

        for file_name in (
            document_name,
            analysis_name,
            annotated_name,
        ):
            debug_urls.append(
                self._build_output_url(
                    request_id,
                    file_name,
                )
            )

        debug_masks = (
            model_manager.detector
            .create_debug_masks(
                analysis_image
            )
        )

        for name, mask in debug_masks.items():
            file_name = f"debug_{name}.png"

            self._save_image(
                output_dir / file_name,
                mask,
            )

            debug_urls.append(
                self._build_output_url(
                    request_id,
                    file_name,
                )
            )

        return debug_urls

    @staticmethod
    def _save_image(
        path: Path,
        image: np.ndarray,
    ) -> None:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        suffix = path.suffix.lower()

        if suffix in (".jpg", ".jpeg"):
            extension = ".jpg"
            parameters = [
                cv2.IMWRITE_JPEG_QUALITY,
                92,
            ]
        else:
            extension = ".png"
            parameters = [
                cv2.IMWRITE_PNG_COMPRESSION,
                6,
            ]

        success, encoded = cv2.imencode(
            extension,
            image,
            parameters,
        )

        if not success:
            raise IOError(
                f"图片编码失败: {path}"
            )

        encoded.tofile(str(path))

    @staticmethod
    def _create_zip(
        zip_path: Path,
        image_paths: List[Path],
    ) -> None:
        with zipfile.ZipFile(
            zip_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            for image_path in image_paths:
                archive.write(
                    image_path,
                    arcname=image_path.name,
                )

    @staticmethod
    def _build_output_url(
        request_id: str,
        file_name: str,
    ) -> str:
        return (
            f"{OUTPUT_URL_PREFIX}/"
            f"{request_id}/"
            f"{file_name}"
        )


stamp_service = StampService()
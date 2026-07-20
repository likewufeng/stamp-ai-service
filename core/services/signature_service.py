# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-19
#Description: 手写签名抠图（保留原笔迹外观）
#FilePath: /stamp-ai-service/core/services/signature_service.py
#
import base64
import io
import uuid
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from loguru import logger
from rembg import new_session, remove

from config import (
    MAX_IMAGE_PIXELS,
    OUTPUT_DIR,
    OUTPUT_URL_PREFIX,
)
from schemas.signature import (
    SignatureBox,
    SignatureExtractionResponse,
    SignatureOutput,
)


class SignatureService:
    """
    签名抠图流程：

    1. 用 rembg / 传统阈值只做“定位 mask”（不直接当最终像素）
    2. 最终输出 = 原图像素 + mask 透明通道
       （100% 保留原笔迹颜色/粗细，不转纯黑、不加粗）
    3. 裁剪可用区域 + padding
    4. 可选等比缩放到目标画布
    5. 返回 url / base64
    """

    def __init__(self):
        self._session = None
        self._session_name = "u2net"

    @property
    def session(self):
        if self._session is None:
            logger.info("加载 rembg 模型 session={}", self._session_name)
            self._session = new_session(self._session_name)
        return self._session

    def process_image(
        self,
        file_path: str,
        source_filename: str,
        debug: bool = False,
        correct_perspective: bool = False,
        target_width: Optional[int] = None,
        target_height: Optional[int] = None,
        resize_mode: str = "fit",
        return_type: str = "base64",
        padding: int = 30,
        ink_threshold: int = 30,
    ) -> SignatureExtractionResponse:
        request_id = uuid.uuid4().hex
        request_output_dir = OUTPUT_DIR / request_id
        request_output_dir.mkdir(parents=True, exist_ok=True)

        return_type = (return_type or "base64").strip().lower()
        if return_type not in {"url", "base64", "both"}:
            raise ValueError("return_type 仅支持 url / base64 / both")

        resize_mode = (resize_mode or "fit").strip().lower()
        if resize_mode not in {"fit", "fill", "stretch"}:
            raise ValueError("resize_mode 仅支持 fit / fill / stretch")

        if target_width is not None and target_width <= 0:
            raise ValueError("width 必须为正整数")
        if target_height is not None and target_height <= 0:
            raise ValueError("height 必须为正整数")

        # 原图：最终取色只用它，保证笔迹外观不变
        original = self._load_pil_image(file_path)
        original_width, original_height = original.size
        original_rgb = np.array(original.convert("RGB"), dtype=np.uint8)

        # 检测用增强图（仅用于生成 mask，不进入最终输出）
        enhanced = self._enhance_for_detection(original)

        rembg_rgba = self._remove_background(enhanced)
        fallback_mask = self._fallback_ink_mask(enhanced)

        rembg_dirty = self._is_over_segmented(rembg_rgba, ink_threshold)

        rembg_mask = self._rgba_to_mask(rembg_rgba, ink_threshold)
        if rembg_dirty:
            rembg_mask = np.zeros(original_rgb.shape[:2], dtype=np.uint8)
            logger.info(
                "rembg 前景过脏（疑似水印纸），禁用 rembg filename={}",
                source_filename,
            )

        # 候选 mask
        masks = {
            "rembg": rembg_mask,
            "threshold_fallback": fallback_mask,
            "merged": self._merge_masks(rembg_mask, fallback_mask),
        }

        # 用 mask 从原图合成“原笔迹透明图”，再评分选最优
        candidates = []
        for name, mask in masks.items():
            if mask is None or cv2.countNonZero(mask) < 40:
                continue

            composed = self._compose_original_stroke(
                original_rgb=original_rgb,
                mask=mask,
            )
            cropped = self._crop_content(composed, padding=padding)
            if cropped is None:
                continue

            score = self._score_signature_candidate(cropped)
            if score < 0:
                continue

            candidates.append((name, score, composed, cropped, mask))

        if not candidates:
            raise ValueError("未检测到签名内容，请检查图片是否包含清晰手写签名")

        # 分高优先；同分时 fallback 更适合水印纸
        priority = {
            "threshold_fallback": 3,
            "rembg": 2,
            "merged": 1,
        }
        candidates.sort(
            key=lambda item: (item[1], priority.get(item[0], 0)),
            reverse=True,
        )

        method, best_score, signature, cropped, best_mask = candidates[0]

        # 若最优结果 ink 占比仍过大，尽量切到更干净的 fallback
        best_ratio = self._ink_ratio(cropped)
        fallback_items = [c for c in candidates if c[0] == "threshold_fallback"]
        if (
            best_ratio > 0.18
            and fallback_items
            and self._ink_ratio(fallback_items[0][3]) < best_ratio * 0.5
        ):
            method, best_score, signature, cropped, best_mask = fallback_items[0]

        logger.info(
            "签名选用 method={} score={:.3f} ink_ratio={:.4f}",
            method,
            best_score,
            self._ink_ratio(cropped),
        )

        content_box = SignatureBox(
            x=0,
            y=0,
            w=max(1, cropped.width),
            h=max(1, cropped.height),
            confidence=1.0,
            label="signature",
            ink_color="original",
        )

        output_image, content_w, content_h = self._fit_to_canvas(
            image=cropped,
            target_width=target_width,
            target_height=target_height,
            mode=resize_mode,
        )

        file_name = "signature_001.png"
        output_path = request_output_dir / file_name
        output_image.save(output_path, format="PNG", optimize=True)

        out_w, out_h = output_image.size

        url_value = None
        base64_value = None
        if return_type in {"url", "both"}:
            url_value = self._build_output_url(request_id, file_name)
        if return_type in {"base64", "both"}:
            base64_value = self._encode_base64_png(output_image)

        signature_outputs: List[SignatureOutput] = [
            SignatureOutput(
                index=1,
                box=content_box,
                width=out_w,
                height=out_h,
                content_width=content_w,
                content_height=content_h,
                file_name=file_name,
                url=url_value,
                base64=base64_value,
            )
        ]

        debug_urls: List[str] = []
        if debug:
            debug_urls.extend(
                self._save_debug_files(
                    request_id=request_id,
                    output_dir=request_output_dir,
                    original=original,
                    enhanced=enhanced,
                    rembg_rgba=rembg_rgba,
                    signature=signature,
                    cropped=cropped,
                    method=method,
                    mask=best_mask,
                )
            )

        zip_url = None
        if return_type in {"url", "both"}:
            zip_name = "signatures.zip"
            zip_path = request_output_dir / zip_name
            self._create_zip(zip_path, [output_path])
            zip_url = self._build_output_url(request_id, zip_name)

        logger.info(
            "签名处理完成 request_id={} method={} preserve_original_stroke=true",
            request_id,
            method,
        )

        return SignatureExtractionResponse(
            request_id=request_id,
            filename=source_filename,
            original_width=original_width,
            original_height=original_height,
            processed_width=original_width,
            processed_height=original_height,
            perspective_applied=False,
            target_width=target_width,
            target_height=target_height,
            resize_mode=resize_mode,
            return_type=return_type,
            count=1,
            signatures=signature_outputs,
            zip_url=zip_url,
            debug_files=debug_urls,
        )

    # ------------------------------------------------------------------
    # Detection helpers (mask only)
    # ------------------------------------------------------------------

    @staticmethod
    def _enhance_for_detection(image: Image.Image) -> Image.Image:
        """仅用于提升 mask 检测，不进入最终输出。"""
        rgb = image.convert("RGB")
        rgb = ImageEnhance.Contrast(rgb).enhance(1.6)
        rgb = ImageEnhance.Sharpness(rgb).enhance(1.2)
        return rgb

    def _remove_background(self, image: Image.Image) -> Image.Image:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        output_data = remove(
            buffer.getvalue(),
            session=self.session,
        )
        return Image.open(io.BytesIO(output_data)).convert("RGBA")

    @staticmethod
    def _rgba_to_mask(rgba: Image.Image, alpha_threshold: int = 30) -> np.ndarray:
        alpha = np.array(rgba.convert("RGBA"))[:, :, 3]
        thr = int(np.clip(alpha_threshold, 0, 255))
        mask = np.where(alpha > thr, 255, 0).astype(np.uint8)
        return SignatureService._cleanup_mask(mask)

    @staticmethod
    def _fallback_ink_mask(image: Image.Image) -> np.ndarray:
        """传统暗度 mask，适合水印纸 / rembg 过脏场景。"""
        bgr = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        background = cv2.GaussianBlur(blurred, (71, 71), 0)
        diff = cv2.subtract(background, blurred)

        nonzero = diff[diff > 1]
        if nonzero.size > 200:
            thr = max(8, int(np.percentile(nonzero, 93)))
            thr = min(thr, 28)
        else:
            thr = 10

        _, mask = cv2.threshold(diff, thr, 255, cv2.THRESH_BINARY)

        paper_ref = float(np.percentile(blurred, 90))
        dark_cut = max(40.0, paper_ref - 55.0)
        dark_mask = np.where(blurred < dark_cut, 255, 0).astype(np.uint8)
        mask = cv2.bitwise_and(mask, dark_mask)

        adaptive = cv2.adaptiveThreshold(
            blurred,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            31,
            12,
        )
        mask = cv2.bitwise_or(mask, cv2.bitwise_and(adaptive, dark_mask))

        mask = cv2.medianBlur(mask.astype(np.uint8), 3)
        return SignatureService._cleanup_mask(mask)

    @staticmethod
    def _cleanup_mask(mask: np.ndarray) -> np.ndarray:
        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
            iterations=1,
        )
        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
            iterations=1,
        )
        mask = SignatureService._keep_main_signature_cluster(mask)
        mask = SignatureService._remove_small_specks(
            mask,
            min_area_ratio=0.00005,
            min_area_abs=30,
        )
        return mask

    @staticmethod
    def _merge_masks(rembg_mask: np.ndarray, fallback_mask: np.ndarray) -> np.ndarray:
        if rembg_mask is None or cv2.countNonZero(rembg_mask) < 20:
            return fallback_mask.copy() if fallback_mask is not None else np.zeros_like(fallback_mask)

        if fallback_mask is None:
            return rembg_mask.copy()

        if rembg_mask.shape != fallback_mask.shape:
            fallback_mask = cv2.resize(
                fallback_mask,
                (rembg_mask.shape[1], rembg_mask.shape[0]),
                interpolation=cv2.INTER_NEAREST,
            )

        # 只在 rembg 邻域内吸收 fallback，避免水印扩散
        h, w = rembg_mask.shape[:2]
        radius = max(12, int(round(min(h, w) * 0.04)))
        if radius % 2 == 0:
            radius += 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius, radius))
        neighborhood = cv2.dilate(rembg_mask, kernel, iterations=2)

        pts = cv2.findNonZero(rembg_mask)
        if pts is not None:
            x, y, bw, bh = cv2.boundingRect(pts)
            pad_x = max(20, int(bw * 0.35))
            pad_y = max(20, int(bh * 0.35))
            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(w, x + bw + pad_x)
            y2 = min(h, y + bh + pad_y)
            box_roi = np.zeros_like(rembg_mask)
            box_roi[y1:y2, x1:x2] = 255
            neighborhood = cv2.bitwise_or(neighborhood, box_roi)

        fallback_near = cv2.bitwise_and(fallback_mask, neighborhood)
        merged = cv2.bitwise_or(rembg_mask, fallback_near)
        return SignatureService._cleanup_mask(merged)

    @staticmethod
    def _keep_main_signature_cluster(mask: np.ndarray) -> np.ndarray:
        h, w = mask.shape[:2]
        image_area = h * w
        min_area = max(18, int(image_area * 0.000015))

        count, labels, stats, _ = cv2.connectedComponentsWithStats(
            mask,
            connectivity=8,
        )
        if count <= 1:
            return mask

        components = []
        for i in range(1, count):
            area = int(stats[i, cv2.CC_STAT_AREA])
            if area < min_area:
                continue
            components.append(
                {
                    "idx": i,
                    "area": area,
                    "x": int(stats[i, cv2.CC_STAT_LEFT]),
                    "y": int(stats[i, cv2.CC_STAT_TOP]),
                    "w": int(stats[i, cv2.CC_STAT_WIDTH]),
                    "h": int(stats[i, cv2.CC_STAT_HEIGHT]),
                }
            )

        if not components:
            return np.zeros_like(mask)

        components.sort(key=lambda c: c["area"], reverse=True)
        main = components[0]
        main_scale = max(main["w"], main["h"], 30)

        kept = [main]
        for comp in components[1:]:
            min_dist = 1e18
            for k in kept:
                gap_x = max(
                    0.0,
                    max(comp["x"] - (k["x"] + k["w"]), k["x"] - (comp["x"] + comp["w"])),
                )
                gap_y = max(
                    0.0,
                    max(comp["y"] - (k["y"] + k["h"]), k["y"] - (comp["y"] + comp["h"])),
                )
                dist = (gap_x ** 2 + gap_y ** 2) ** 0.5
                min_dist = min(min_dist, dist)

            max_dist = max(main_scale * 1.8, 80.0)
            if min_dist <= max_dist:
                kept.append(comp)
            elif comp["area"] >= main["area"] * 0.25 and min_dist <= max_dist * 1.4:
                kept.append(comp)

        out = np.zeros_like(mask)
        for comp in kept:
            out[labels == comp["idx"]] = 255

        out = cv2.morphologyEx(
            out,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
            iterations=1,
        )
        return out

    @staticmethod
    def _remove_small_specks(
        mask: np.ndarray,
        min_area_ratio: float = 0.00005,
        min_area_abs: int = 30,
    ) -> np.ndarray:
        h, w = mask.shape[:2]
        min_area = max(min_area_abs, int(h * w * min_area_ratio))

        count, labels, stats, centroids = cv2.connectedComponentsWithStats(
            mask,
            connectivity=8,
        )
        if count <= 1:
            return mask

        areas = stats[1:, cv2.CC_STAT_AREA]
        main_idx = int(np.argmax(areas)) + 1
        main_area = int(stats[main_idx, cv2.CC_STAT_AREA])
        main_cx, main_cy = centroids[main_idx]
        main_w = int(stats[main_idx, cv2.CC_STAT_WIDTH])
        main_h = int(stats[main_idx, cv2.CC_STAT_HEIGHT])
        radius = max(main_w, main_h) * 1.15

        out = np.zeros_like(mask)
        for i in range(1, count):
            area = int(stats[i, cv2.CC_STAT_AREA])
            cx, cy = centroids[i]
            dist = float(np.hypot(cx - main_cx, cy - main_cy))

            if i == main_idx:
                out[labels == i] = 255
            elif area >= max(min_area, int(main_area * 0.02)) and dist <= radius * 1.6:
                out[labels == i] = 255
            elif area >= max(min_area * 3, int(main_area * 0.05)) and dist <= radius * 2.2:
                out[labels == i] = 255

        return out

    @staticmethod
    def _is_over_segmented(
        rgba: Image.Image,
        alpha_threshold: int = 30,
    ) -> bool:
        arr = np.array(rgba.convert("RGBA"))
        alpha = arr[:, :, 3]
        thr = int(np.clip(alpha_threshold, 0, 255))
        ink_ratio = float(np.count_nonzero(alpha > thr)) / float(max(alpha.size, 1))
        soft_ratio = float(np.count_nonzero((alpha > 0) & (alpha <= 128))) / float(
            max(alpha.size, 1)
        )
        if ink_ratio >= 0.12:
            return True
        if soft_ratio >= 0.35 and ink_ratio >= 0.06:
            return True
        return False

    # ------------------------------------------------------------------
    # Preserve original stroke
    # ------------------------------------------------------------------

    @staticmethod
    def _compose_original_stroke(
        original_rgb: np.ndarray,
        mask: np.ndarray,
    ) -> Image.Image:
        """
        最终输出：原图像素 + mask 透明通道。
        不改 RGB，不转纯黑，不加粗。
        """
        if mask.shape[:2] != original_rgb.shape[:2]:
            mask = cv2.resize(
                mask,
                (original_rgb.shape[1], original_rgb.shape[0]),
                interpolation=cv2.INTER_NEAREST,
            )

        # 轻微羽化边缘，仅作用于 alpha，不改颜色
        soft = cv2.GaussianBlur(mask, (3, 3), 0.6)
        alpha = soft.copy()
        alpha[mask > 0] = np.maximum(alpha[mask > 0], 220)
        alpha[mask == 0] = 0

        rgba = np.zeros(
            (original_rgb.shape[0], original_rgb.shape[1], 4),
            dtype=np.uint8,
        )
        rgba[:, :, :3] = original_rgb
        rgba[:, :, 3] = alpha

        # 背景 RGB 清零，避免预乘/预览异常
        rgba[alpha == 0, :3] = 0
        return Image.fromarray(rgba, mode="RGBA")

    # ------------------------------------------------------------------
    # Score / crop / canvas
    # ------------------------------------------------------------------

    @staticmethod
    def _ink_ratio(image: Optional[Image.Image]) -> float:
        if image is None:
            return 0.0
        alpha = np.array(image.convert("RGBA"))[:, :, 3]
        return float(np.count_nonzero(alpha > 30)) / float(max(alpha.size, 1))

    @staticmethod
    def _score_signature_candidate(image: Optional[Image.Image]) -> float:
        if image is None:
            return -1.0

        arr = np.array(image.convert("RGBA"))
        alpha = arr[:, :, 3]
        ink = int(np.count_nonzero(alpha > 30))
        if ink < 80:
            return 0.0

        h, w = alpha.shape[:2]
        area = float(max(w * h, 1))
        fill = ink / area
        aspect = w / float(max(h, 1))

        aspect_score = 1.0 - min(abs(aspect - 2.2) / 4.0, 1.0)
        fill_score = 1.0 - min(abs(fill - 0.10) / 0.20, 1.0)
        ink_score = min(1.0, np.log1p(ink) / np.log1p(25000))

        size_score = min(1.0, area / 80000.0)
        if area > 500000:
            size_score *= 0.35

        penalty = 0.0
        if fill < 0.01 and area > 200000:
            penalty += 0.5
        if aspect < 0.3 or aspect > 12:
            penalty += 0.3
        if fill > 0.35:
            penalty += min(0.8, (fill - 0.35) * 2.0)
        if ink > 200000:
            penalty += 0.6

        score = (
            0.35 * ink_score
            + 0.25 * size_score
            + 0.20 * aspect_score
            + 0.20 * fill_score
            - penalty
        )
        return float(np.clip(score, -1.0, 0.99))

    @staticmethod
    def _crop_content(
        image: Image.Image,
        padding: int = 30,
    ) -> Optional[Image.Image]:
        bbox = image.getbbox()
        if not bbox:
            return None

        pad = max(0, int(padding))
        left = max(0, bbox[0] - pad)
        top = max(0, bbox[1] - pad)
        right = min(image.width, bbox[2] + pad)
        bottom = min(image.height, bbox[3] + pad)

        if right <= left or bottom <= top:
            return None

        return image.crop((left, top, right, bottom))

    @staticmethod
    def _fit_to_canvas(
        image: Image.Image,
        target_width: Optional[int],
        target_height: Optional[int],
        mode: str = "fit",
    ) -> Tuple[Image.Image, int, int]:
        src_w, src_h = image.size

        if target_width is None and target_height is None:
            return image, src_w, src_h

        if target_width is None:
            scale = target_height / float(src_h)
            target_width = max(1, int(round(src_w * scale)))
        elif target_height is None:
            scale = target_width / float(src_w)
            target_height = max(1, int(round(src_h * scale)))

        target_width = int(target_width)
        target_height = int(target_height)

        if mode == "stretch":
            resized = image.resize(
                (target_width, target_height),
                Image.Resampling.LANCZOS,
            )
            return resized, target_width, target_height

        src_ratio = src_w / float(src_h)
        target_ratio = target_width / float(target_height)

        if mode == "fill":
            if src_ratio > target_ratio:
                draw_h = target_height
                draw_w = max(1, int(round(target_height * src_ratio)))
            else:
                draw_w = target_width
                draw_h = max(1, int(round(target_width / src_ratio)))

            resized = image.resize((draw_w, draw_h), Image.Resampling.LANCZOS)
            left = max(0, (draw_w - target_width) // 2)
            top = max(0, (draw_h - target_height) // 2)
            cropped = resized.crop(
                (left, top, left + target_width, top + target_height)
            )
            return cropped, target_width, target_height

        if src_ratio > target_ratio:
            draw_w = target_width
            draw_h = max(1, int(round(target_width / src_ratio)))
        else:
            draw_h = target_height
            draw_w = max(1, int(round(target_height * src_ratio)))

        resized = image.resize((draw_w, draw_h), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
        x = (target_width - draw_w) // 2
        y = (target_height - draw_h) // 2
        canvas.paste(resized, (x, y), resized)
        return canvas, draw_w, draw_h

    @staticmethod
    def _load_pil_image(file_path: str) -> Image.Image:
        with Image.open(file_path) as pil_image:
            pil_image = ImageOps.exif_transpose(pil_image)
            width, height = pil_image.size

            if width * height > MAX_IMAGE_PIXELS:
                raise ValueError(
                    "图片像素数量过大，"
                    f"最大允许 {MAX_IMAGE_PIXELS} 像素"
                )

            if pil_image.mode in ("RGBA", "LA") or (
                pil_image.mode == "P"
                and "transparency" in pil_image.info
            ):
                rgba = pil_image.convert("RGBA")
                background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                pil_image = Image.alpha_composite(background, rgba).convert("RGB")
            else:
                pil_image = pil_image.convert("RGB")

            return pil_image.copy()

    def _save_debug_files(
        self,
        request_id: str,
        output_dir: Path,
        original: Image.Image,
        enhanced: Image.Image,
        rembg_rgba: Image.Image,
        signature: Image.Image,
        cropped: Image.Image,
        method: str,
        mask: np.ndarray,
    ) -> List[str]:
        files = {
            "debug_original.jpg": original.convert("RGB"),
            "debug_enhanced.jpg": enhanced.convert("RGB"),
            "debug_rembg.png": rembg_rgba,
            "debug_mask.png": Image.fromarray(mask, mode="L"),
            "debug_signature.png": signature,
            "debug_cropped.png": cropped,
        }

        (output_dir / "debug_method.txt").write_text(
            f"{method}|preserve_original_stroke",
            encoding="utf-8",
        )

        urls: List[str] = [
            self._build_output_url(request_id, "debug_method.txt")
        ]
        for name, image in files.items():
            path = output_dir / name
            if name.endswith(".jpg"):
                image.save(path, format="JPEG", quality=92)
            else:
                image.save(path, format="PNG")
            urls.append(self._build_output_url(request_id, name))
        return urls

    @staticmethod
    def _encode_base64_png(image: Image.Image) -> str:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        payload = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/png;base64,{payload}"

    @staticmethod
    def _create_zip(zip_path: Path, image_paths: List[Path]) -> None:
        with zipfile.ZipFile(
            zip_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            for image_path in image_paths:
                archive.write(image_path, arcname=image_path.name)

    @staticmethod
    def _build_output_url(request_id: str, file_name: str) -> str:
        return f"{OUTPUT_URL_PREFIX}/{request_id}/{file_name}"


signature_service = SignatureService()

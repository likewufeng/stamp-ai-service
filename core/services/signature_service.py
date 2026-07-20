# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-19
#Description: 手写签名抠图业务服务（rembg 去背景 + 淡笔回退）
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

    1. 对比度增强（提升淡铅笔可见度）
    2. rembg AI 去背景
    3. 若前景过少，回退到传统暗度阈值
    4. 笔画转纯黑 + 透明底
    5. 裁空白 + padding
    6. 等比缩放居中到目标画布（不变形）
    7. 返回 url / base64
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
        return_type: str = "url",
        padding: int = 30,
        ink_threshold: int = 30,
    ) -> SignatureExtractionResponse:
        request_id = uuid.uuid4().hex
        request_output_dir = OUTPUT_DIR / request_id
        request_output_dir.mkdir(parents=True, exist_ok=True)

        return_type = (return_type or "url").strip().lower()
        if return_type not in {"url", "base64", "both"}:
            raise ValueError("return_type 仅支持 url / base64 / both")

        resize_mode = (resize_mode or "fit").strip().lower()
        if resize_mode not in {"fit", "fill", "stretch"}:
            raise ValueError("resize_mode 仅支持 fit / fill / stretch")

        if target_width is not None and target_width <= 0:
            raise ValueError("width 必须为正整数")
        if target_height is not None and target_height <= 0:
            raise ValueError("height 必须为正整数")

        original = self._load_pil_image(file_path)
        original_width, original_height = original.size

        enhanced = self._enhance_for_signature(original)

        # 双路提取：rembg + 传统暗度，择优
        rembg_rgba = self._remove_background(enhanced)
        fallback_rgba = self._fallback_threshold_rgba(enhanced)

        rembg_sig = self._to_pure_black_signature(
            rembg_rgba,
            alpha_threshold=ink_threshold,
        )
        fallback_sig = self._to_pure_black_signature(
            fallback_rgba,
            alpha_threshold=ink_threshold,
        )

        rembg_crop = self._crop_content(rembg_sig, padding=padding)
        fallback_crop = self._crop_content(fallback_sig, padding=padding)

        rembg_score = self._score_signature_candidate(rembg_crop)
        fallback_score = self._score_signature_candidate(fallback_crop)

        logger.info(
            "签名候选评分 filename={} rembg={:.3f} fallback={:.3f}",
            source_filename,
            rembg_score,
            fallback_score,
        )

        if rembg_crop is None and fallback_crop is None:
            raise ValueError("未检测到签名内容，请检查图片是否包含清晰手写签名")

        # 选择策略：
        # 1) rembg 足够好时优先 rembg（边缘更干净）
        # 2) 仅当 fallback 明显更完整时才切换（淡铅笔场景）
        use_fallback = False
        if rembg_crop is None and fallback_crop is not None:
            use_fallback = True
        elif fallback_crop is not None and rembg_crop is not None:
            if rembg_score < 0.45 and fallback_score > rembg_score:
                use_fallback = True
            elif fallback_score > rembg_score * 1.25 and fallback_score >= 0.55:
                use_fallback = True

        if use_fallback:
            signature = fallback_sig
            cropped = fallback_crop
            removed = fallback_rgba
            method = "threshold_fallback"
        else:
            signature = rembg_sig
            cropped = rembg_crop if rembg_crop is not None else fallback_crop
            removed = rembg_rgba
            method = "rembg"

        if cropped is None:
            raise ValueError("未检测到签名内容，请检查图片是否包含清晰手写签名")

        content_box = SignatureBox(
            x=0,
            y=0,
            w=max(1, cropped.width),
            h=max(1, cropped.height),
            confidence=1.0,
            label="signature",
            ink_color="black",
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
                    removed=removed,
                    signature=signature,
                    cropped=cropped,
                    method=method,
                )
            )

        zip_url = None
        if return_type in {"url", "both"}:
            zip_name = "signatures.zip"
            zip_path = request_output_dir / zip_name
            self._create_zip(zip_path, [output_path])
            zip_url = self._build_output_url(request_id, zip_name)

        logger.info(
            "签名处理完成 request_id={} method={}",
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

    @staticmethod
    def _enhance_for_signature(image: Image.Image) -> Image.Image:
        """轻微增强对比度，帮助淡铅笔被 rembg 识别。"""
        rgb = image.convert("RGB")
        # 对比度 + 锐化一点点，不过度以免放大噪点
        rgb = ImageEnhance.Contrast(rgb).enhance(1.8)
        rgb = ImageEnhance.Sharpness(rgb).enhance(1.4)
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
    def _fallback_threshold_rgba(image: Image.Image) -> Image.Image:
        """
        传统回退：相对纸面暗度提取笔迹。
        适合 rembg 对淡铅笔几乎无输出的情况。
        """
        bgr = cv2.cvtColor(
            np.array(image.convert("RGB")),
            cv2.COLOR_RGB2BGR,
        )
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # 局部背景
        background = cv2.GaussianBlur(blurred, (71, 71), 0)
        diff = cv2.subtract(background, blurred)

        nonzero = diff[diff > 1]
        if nonzero.size > 200:
            thr = max(4, int(np.percentile(nonzero, 88)))
            thr = min(thr, 16)
        else:
            thr = 6

        _, mask = cv2.threshold(diff, thr, 255, cv2.THRESH_BINARY)

        adaptive = cv2.adaptiveThreshold(
            blurred,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            31,
            8,
        )
        diff_gate = np.where(diff > max(1, thr - 2), 255, 0).astype(np.uint8)
        mask = cv2.bitwise_or(
            mask,
            cv2.bitwise_and(adaptive, diff_gate),
        )

        mask = cv2.medianBlur(mask.astype(np.uint8), 3)
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

        # 去小噪点，并只保留主签名团簇（抑制折痕/纸噪）
        cleaned = SignatureService._keep_main_signature_cluster(mask)

        rgba = np.zeros((mask.shape[0], mask.shape[1], 4), dtype=np.uint8)
        rgba[cleaned > 0] = (0, 0, 0, 255)
        return Image.fromarray(rgba, mode="RGBA")

    @staticmethod
    def _keep_main_signature_cluster(mask: np.ndarray) -> np.ndarray:
        """保留主签名连通域簇，去掉远离主簇的折痕/噪点。"""
        h, w = mask.shape[:2]
        image_area = h * w
        min_area = max(18, int(image_area * 0.000015))

        count, labels, stats, centroids = cv2.connectedComponentsWithStats(
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
                    "cx": float(centroids[i][0]),
                    "cy": float(centroids[i][1]),
                }
            )

        if not components:
            return np.zeros_like(mask)

        # 以面积最大的部件为主锚点
        components.sort(key=lambda c: c["area"], reverse=True)
        main = components[0]
        main_scale = max(main["w"], main["h"], 30)

        kept = [main]
        for comp in components[1:]:
            # 与已保留簇的最近距离
            min_dist = 1e18
            for k in kept:
                dx = comp["cx"] - k["cx"]
                dy = comp["cy"] - k["cy"]
                # 框间距（比中心距更稳）
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

            # 允许一个字宽左右的间隔
            max_dist = max(main_scale * 1.8, 80.0)
            # 太小的远距离点丢掉
            if min_dist <= max_dist:
                kept.append(comp)
            elif comp["area"] >= main["area"] * 0.25 and min_dist <= max_dist * 1.4:
                kept.append(comp)

        out = np.zeros_like(mask)
        for comp in kept:
            out[labels == comp["idx"]] = 255

        # 轻微闭运算，连回断裂笔画
        out = cv2.morphologyEx(
            out,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
            iterations=1,
        )
        return out

    @staticmethod
    def _to_pure_black_signature(
        image: Image.Image,
        alpha_threshold: int = 30,
    ) -> Image.Image:
        arr = np.array(image.convert("RGBA"))
        alpha = arr[:, :, 3]
        threshold = int(np.clip(alpha_threshold, 0, 255))

        out = np.zeros_like(arr)
        solid = alpha > threshold
        soft = (alpha > 0) & (~solid)

        out[solid] = (0, 0, 0, 255)
        if np.any(soft):
            a = alpha[soft].astype(np.float32) / 255.0
            out[soft, 0] = 0
            out[soft, 1] = 0
            out[soft, 2] = 0
            out[soft, 3] = np.clip(np.round(a * 255.0), 0, 255).astype(np.uint8)

        return Image.fromarray(out, mode="RGBA")

    @staticmethod
    def _score_signature_candidate(
        image: Optional[Image.Image],
    ) -> float:
        """
        给候选签名图打分，分数越高越好。

        综合考虑：
        - 有效墨迹量
        - 外接框面积（完整签名通常更大）
        - 宽高比是否像签名
        - 避免整页噪声（过大且填充极低）
        """
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

        # 签名常见宽高比
        aspect_score = 1.0 - min(abs(aspect - 2.2) / 4.0, 1.0)

        # 填充率常见 0.03~0.25
        fill_score = 1.0 - min(abs(fill - 0.10) / 0.20, 1.0)

        # 墨迹量（对数）
        ink_score = min(1.0, np.log1p(ink) / np.log1p(25000))

        # 尺寸分：太小扣分
        size_score = min(1.0, area / 80000.0)

        # 过大且几乎空白：噪声
        penalty = 0.0
        if fill < 0.01 and area > 200000:
            penalty += 0.5
        if aspect < 0.3 or aspect > 12:
            penalty += 0.3

        score = (
            0.35 * ink_score
            + 0.25 * size_score
            + 0.20 * aspect_score
            + 0.20 * fill_score
            - penalty
        )
        return float(score)

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

        # fit
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
        removed: Image.Image,
        signature: Image.Image,
        cropped: Image.Image,
        method: str,
    ) -> List[str]:
        files = {
            "debug_original.jpg": original.convert("RGB"),
            "debug_enhanced.jpg": enhanced.convert("RGB"),
            "debug_removed.png": removed,
            "debug_black.png": signature,
            "debug_cropped.png": cropped,
        }

        # 记录使用的方法
        (output_dir / "debug_method.txt").write_text(method, encoding="utf-8")

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

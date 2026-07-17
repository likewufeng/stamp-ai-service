# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 14:21:52
#LastEditTime: 2026-07-17 15:24:33
#LastEditors: WuFeng <763467339@qq.com>
#Description: 文档预处理器
#FilePath: /stamp-ai-service/core/processors/document_processor.py
#Copyright 版权声明
#
import cv2
import numpy as np


class DocumentProcessor:

    def process(self, image):

        image = self.resize(image)

        image = self.white_balance(image)

        image = self.enhance(image)

        return image

    def resize(self, image, max_side=2200):

        h, w = image.shape[:2]

        m = max(h, w)

        if m <= max_side:
            return image

        scale = max_side / m

        return cv2.resize(
            image,
            (
                int(w * scale),
                int(h * scale)
            )
        )

    def white_balance(self, image):

        img = image.astype(np.float32)

        b, g, r = cv2.split(img)

        b_avg = np.mean(b)
        g_avg = np.mean(g)
        r_avg = np.mean(r)

        k = (b_avg + g_avg + r_avg) / 3

        b *= k / (b_avg + 1e-6)
        g *= k / (g_avg + 1e-6)
        r *= k / (r_avg + 1e-6)

        img = cv2.merge((b, g, r))

        return np.clip(img, 0, 255).astype(np.uint8)

    def enhance(self, image):

        lab = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2LAB
        )

        l, a, b = cv2.split(lab)

        clahe = cv2.createCLAHE(
            clipLimit=2.0,
            tileGridSize=(8, 8)
        )

        l = clahe.apply(l)

        lab = cv2.merge((l, a, b))

        return cv2.cvtColor(
            lab,
            cv2.COLOR_LAB2BGR
        )
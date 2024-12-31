#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import cv2
import numpy as np
from threading import Lock


def adjust_gamma(image, gamma=1.0):
    # https://pyimagesearch.com/2015/10/05/opencv-gamma-correction/
    # build a lookup table mapping the pixel values [0, 255] to
    # their adjusted gamma values
    # inv_gamma = 1.0 / gamma
    # table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
    table = ((np.arange(0, 256) / 255) ** (1 / gamma) * 255).astype(np.uint8)
    # apply gamma correction using the lookup table
    return cv2.LUT(image, table)


def identity(img: np.ndarray):
    return img


def linear_u12_to_u8(img: np.ndarray):
    if img.dtype != np.uint16:
        return img
    return cv2.convertScaleAbs(img, None, 255 / 4095, 0)


def linear_u16_to_u8(img: np.ndarray):
    if img.dtype != np.uint16:
        return img
    return cv2.convertScaleAbs(img, None, 255 / 65535, 0)


def linear_min_max(min_v, max_v, img: np.ndarray):
    if img.dtype != np.uint16:
        return img
    img = np.copy(img)

    # xs, ys = np.where(np.logical_or(img < min_v, max_v < img))
    # img[xs, ys] = cv2.medianBlur(img, 5)[xs, ys]

    alpha = 255 / (max_v - min_v)
    beta = -min_v * alpha
    ret = cv2.convertScaleAbs(img, None, alpha, beta)
    return ret


def alpha_beta_gamma(alpha: float, beta: float, gamma: float, img: np.ndarray):
    if img.dtype != np.uint16:
        return img

    img = cv2.convertScaleAbs(img, None, alpha, beta)
    if gamma != 1.0:
        img = adjust_gamma(img, gamma)
    return img


class NormalizeDropPepperSalt:
    def __init__(self):
        self.mn = 0
        self.mx = 0

    @staticmethod
    def calc_min_max_with_dropout(img: np.ndarray, dropout=0.0001):
        hists = np.bincount(img.ravel())

        drop_cnt = max(img.size * dropout, 50)
        c, min_v = 0, 0
        while c <= drop_cnt:
            c += hists[min_v]
            min_v += 1

        c, max_v = 0, len(hists) - 1
        while c <= drop_cnt:
            c += hists[max_v]
            max_v -= 1
        return min_v, max_v

    def __call__(self, img: np.ndarray, dropout=0.0001):
        self.mn, self.mx = NormalizeDropPepperSalt.calc_min_max_with_dropout(img, dropout)
        return linear_min_max(self.mn, self.mx, img)


def normalize_with_drop(img: np.ndarray, dropout=0.0001):
    if img.dtype != np.uint16:
        return img
    min_v, max_v = NormalizeDropPepperSalt.calc_min_max_with_dropout(img, dropout)
    return linear_min_max(min_v, max_v, img)


class ProcessorContext:
    def __init__(self, mgr: "ZemImageProcessorManager", processor):
        self.mgr = mgr
        self.processor = processor
        self.last = None

    def __enter__(self):
        with self.mgr.lock:
            self.last = self.mgr._curr
            self.mgr._curr = self.processor
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.mgr._curr = self.last


class ZemImageProcessorManager:
    def __init__(self):
        self._op_identity = lambda _: _
        self._curr = None
        self.lock = Lock()

    def __call__(self, img):
        if self._curr:
            return self._curr(img)
        else:
            return self._op_identity(img)

    def update(self, p):
        self._curr = p

    def with_processor(self, processor):
        return ProcessorContext(self, processor)

import json

import cv2
import numpy as np

from zemrpc.zem.models import NavImage, NavParam


def test_export_nav_image_and_coefficients_with_matching_names(tmp_path):
    rgb_image = np.array([[[10, 20, 30], [40, 50, 60]]], dtype=np.uint8)
    nav_param = NavParam(p0x=320.0, p0y=240.0, cx=1.25, cy=-2.5)
    nav_image = NavImage(ctime=1_700_000_000.123, shape=rgb_image.shape[:2], nav_param=nav_param, img=rgb_image)

    image_path, coefficient_path = nav_image.export(tmp_path)

    assert image_path.stem == coefficient_path.stem
    assert image_path.suffix == ".png"
    assert coefficient_path.suffix == ".json"
    assert json.loads(coefficient_path.read_text(encoding="utf-8")) == nav_param.model_dump()
    assert np.array_equal(cv2.imread(str(image_path)), cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR))

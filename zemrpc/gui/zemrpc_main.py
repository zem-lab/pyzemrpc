#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import os
import cv2
import sys
from PIL import Image
import pyqtgraph as pg
from loguru import logger
from qtpy.QtWidgets import QApplication, QMainWindow

from jgb.util import loguru_util

from zemrpc import app_cfg
from zemrpc.gui import qt_exception_hook
from zemrpc.gui.zemrpc_win import ZemRpcWidget


class MainWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle("ZEMrpc 示例")
        self.w = ZemRpcWidget(self)
        self.setCentralWidget(self.w)


if __name__ == "__main__":
    os.environ["QT_API"] = "pyside6"
    os.environ["PYQTGRAPH_QT_LIB"] = "PySide6"
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    Image.MAX_IMAGE_PIXELS = None
    cv2.ocl.setUseOpenCL(False)
    pg.setConfigOptions(imageAxisOrder="row-major", background="w", foreground="k")

    loguru_util.init_log(app_cfg.log_dir)
    logger.debug(app_cfg.about)

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

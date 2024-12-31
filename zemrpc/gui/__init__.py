#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com
import sys
from loguru import logger
from qtpy import QtCore, QtWidgets
import traceback


def show_exception_box(log_msg):
    """Checks if a QApplication instance is available and shows a messagebox with the exception message.
    If unavailable (non-console application), log an additional notice.
    """
    if QtWidgets.QApplication.instance() is not None:
        errorbox = QtWidgets.QMessageBox()
        errorbox.setText("Oops. An unexpected error occured:\n{0}".format(log_msg))
        errorbox.exec_()
    else:
        logger.debug("No QApplication instance available.")


class UncaughtHook(QtCore.QObject):
    _exception_caught = QtCore.Signal(object)

    def __init__(self, *args, **kwargs):
        super(UncaughtHook, self).__init__(*args, **kwargs)
        sys.excepthook = self.exception_hook
        # connect signal to execute the message box function always on main thread
        self._exception_caught.connect(show_exception_box)

    def exception_hook(self, exc_type, exc_value, exc_traceback):
        """Function handling uncaught exceptions.
        It is triggered each time an uncaught exception occurs.
        """
        if issubclass(exc_type, KeyboardInterrupt):
            # ignore keyboard interrupt to support console applications
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
        else:
            log_msg = "\n".join(["".join(traceback.format_tb(exc_traceback)), "{0}: {1}".format(exc_type.__name__, exc_value)])

            exc_info = (exc_type, exc_value, exc_traceback)
            # log.critical("Uncaught exception:\n {0}".format(log_msg), exc_info=exc_info)
            # logger.warning("Uncaught exception:\n {0}".format(log_msg), exc_info=exc_info)
            logger.exception("Uncaught exception:\n {0}".format(log_msg))

            # trigger message box show
            self._exception_caught.emit(log_msg)


# create a global instance of our class to register the hook
qt_exception_hook = UncaughtHook()

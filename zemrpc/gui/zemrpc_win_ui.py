# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'zemrpc_win.ui'
##
## Created by: Qt User Interface Compiler version 6.10.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QRadioButton, QSizePolicy, QSpacerItem,
    QTabWidget, QToolButton, QVBoxLayout, QWidget)

from jgb.gui.qt.widgets.qt_edit_slider import QEditSlider
from jgb.gui.qt.widgets.qt_wheel_lineedit import QWheelLineEdit

class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(528, 705)
        Form.setMinimumSize(QSize(500, 700))
        self.verticalLayout = QVBoxLayout(Form)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.tabWidget_3 = QTabWidget(Form)
        self.tabWidget_3.setObjectName(u"tabWidget_3")
        self.tabWidget_3.setMinimumSize(QSize(0, 512))
        self.tab_sem_img = QWidget()
        self.tab_sem_img.setObjectName(u"tab_sem_img")
        self.tabWidget_3.addTab(self.tab_sem_img, "")
        self.tab_nav_img = QWidget()
        self.tab_nav_img.setObjectName(u"tab_nav_img")
        self.tabWidget_3.addTab(self.tab_nav_img, "")

        self.verticalLayout.addWidget(self.tabWidget_3)

        self.tab_modules = QTabWidget(Form)
        self.tab_modules.setObjectName(u"tab_modules")
        self.tab_modules.setMaximumSize(QSize(16777215, 130))
        self.tab_conn = QWidget()
        self.tab_conn.setObjectName(u"tab_conn")
        self.verticalLayout_2 = QVBoxLayout(self.tab_conn)
        self.verticalLayout_2.setSpacing(0)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 4, 0, 0)
        self.frame_5 = QFrame(self.tab_conn)
        self.frame_5.setObjectName(u"frame_5")
        self.frame_5.setFrameShape(QFrame.Shape.Box)
        self.frame_5.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.frame_5)
        self.horizontalLayout_2.setSpacing(6)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.btn_handshake = QPushButton(self.frame_5)
        self.btn_handshake.setObjectName(u"btn_handshake")

        self.horizontalLayout_2.addWidget(self.btn_handshake)

        self.cbox_sem_servers = QComboBox(self.frame_5)
        self.cbox_sem_servers.setObjectName(u"cbox_sem_servers")
        self.cbox_sem_servers.setMinimumSize(QSize(180, 0))

        self.horizontalLayout_2.addWidget(self.cbox_sem_servers)

        self.btn_zem_sync = QPushButton(self.frame_5)
        self.btn_zem_sync.setObjectName(u"btn_zem_sync")

        self.horizontalLayout_2.addWidget(self.btn_zem_sync)

        self.horizontalSpacer_5 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer_5)


        self.verticalLayout_2.addWidget(self.frame_5)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.cbox_cmds = QComboBox(self.tab_conn)
        self.cbox_cmds.setObjectName(u"cbox_cmds")
        self.cbox_cmds.setMinimumSize(QSize(175, 0))

        self.horizontalLayout.addWidget(self.cbox_cmds)

        self.input_cmd_args = QLineEdit(self.tab_conn)
        self.input_cmd_args.setObjectName(u"input_cmd_args")
        self.input_cmd_args.setMinimumSize(QSize(180, 0))

        self.horizontalLayout.addWidget(self.input_cmd_args)

        self.btn_send = QPushButton(self.tab_conn)
        self.btn_send.setObjectName(u"btn_send")

        self.horizontalLayout.addWidget(self.btn_send)

        self.horizontalSpacer_7 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer_7)


        self.verticalLayout_2.addLayout(self.horizontalLayout)

        self.line_4 = QFrame(self.tab_conn)
        self.line_4.setObjectName(u"line_4")
        self.line_4.setLineWidth(2)
        self.line_4.setFrameShape(QFrame.Shape.HLine)
        self.line_4.setFrameShadow(QFrame.Shadow.Sunken)

        self.verticalLayout_2.addWidget(self.line_4)

        self.horizontalLayout_4 = QHBoxLayout()
        self.horizontalLayout_4.setSpacing(2)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(-1, 0, -1, -1)
        self.label_8 = QLabel(self.tab_conn)
        self.label_8.setObjectName(u"label_8")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_8.sizePolicy().hasHeightForWidth())
        self.label_8.setSizePolicy(sizePolicy)

        self.horizontalLayout_4.addWidget(self.label_8)

        self.lbl_cmd_send = QLabel(self.tab_conn)
        self.lbl_cmd_send.setObjectName(u"lbl_cmd_send")

        self.horizontalLayout_4.addWidget(self.lbl_cmd_send)


        self.verticalLayout_2.addLayout(self.horizontalLayout_4)

        self.horizontalLayout_5 = QHBoxLayout()
        self.horizontalLayout_5.setSpacing(2)
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.label_5 = QLabel(self.tab_conn)
        self.label_5.setObjectName(u"label_5")
        sizePolicy.setHeightForWidth(self.label_5.sizePolicy().hasHeightForWidth())
        self.label_5.setSizePolicy(sizePolicy)

        self.horizontalLayout_5.addWidget(self.label_5)

        self.lbl_cmd_rcv = QLabel(self.tab_conn)
        self.lbl_cmd_rcv.setObjectName(u"lbl_cmd_rcv")

        self.horizontalLayout_5.addWidget(self.lbl_cmd_rcv)


        self.verticalLayout_2.addLayout(self.horizontalLayout_5)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_2.addItem(self.verticalSpacer_2)

        self.tab_modules.addTab(self.tab_conn, "")
        self.tab_hv = QWidget()
        self.tab_hv.setObjectName(u"tab_hv")
        self.verticalLayout_6 = QVBoxLayout(self.tab_hv)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.horizontalLayout_10 = QHBoxLayout()
        self.horizontalLayout_10.setObjectName(u"horizontalLayout_10")
        self.btn_hv_get = QPushButton(self.tab_hv)
        self.btn_hv_get.setObjectName(u"btn_hv_get")
        self.btn_hv_get.setMaximumSize(QSize(80, 16777215))

        self.horizontalLayout_10.addWidget(self.btn_hv_get)

        self.ipt_hv = QWheelLineEdit(self.tab_hv)
        self.ipt_hv.setObjectName(u"ipt_hv")
        self.ipt_hv.setMaximumSize(QSize(40, 16777215))
        self.ipt_hv.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.horizontalLayout_10.addWidget(self.ipt_hv)

        self.label_10 = QLabel(self.tab_hv)
        self.label_10.setObjectName(u"label_10")

        self.horizontalLayout_10.addWidget(self.label_10)

        self.btn_hv_set = QPushButton(self.tab_hv)
        self.btn_hv_set.setObjectName(u"btn_hv_set")
        self.btn_hv_set.setMinimumSize(QSize(45, 0))
        self.btn_hv_set.setMaximumSize(QSize(16777215, 16777215))

        self.horizontalLayout_10.addWidget(self.btn_hv_set)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_10.addItem(self.horizontalSpacer)

        self.btn_gun_on = QPushButton(self.tab_hv)
        self.btn_gun_on.setObjectName(u"btn_gun_on")
        self.btn_gun_on.setMinimumSize(QSize(45, 0))
        self.btn_gun_on.setMaximumSize(QSize(16777215, 16777215))

        self.horizontalLayout_10.addWidget(self.btn_gun_on)

        self.btn_gun_off = QPushButton(self.tab_hv)
        self.btn_gun_off.setObjectName(u"btn_gun_off")
        self.btn_gun_off.setMinimumSize(QSize(45, 0))
        self.btn_gun_off.setMaximumSize(QSize(16777215, 16777215))

        self.horizontalLayout_10.addWidget(self.btn_gun_off)

        self.line_6 = QFrame(self.tab_hv)
        self.line_6.setObjectName(u"line_6")
        self.line_6.setFrameShape(QFrame.Shape.VLine)
        self.line_6.setFrameShadow(QFrame.Shadow.Sunken)

        self.horizontalLayout_10.addWidget(self.line_6)

        self.btn_allow_open_gun = QPushButton(self.tab_hv)
        self.btn_allow_open_gun.setObjectName(u"btn_allow_open_gun")
        self.btn_allow_open_gun.setMinimumSize(QSize(80, 0))
        self.btn_allow_open_gun.setMaximumSize(QSize(16777215, 16777215))

        self.horizontalLayout_10.addWidget(self.btn_allow_open_gun)

        self.ipt_allow_open_gun_resp = QLineEdit(self.tab_hv)
        self.ipt_allow_open_gun_resp.setObjectName(u"ipt_allow_open_gun_resp")
        self.ipt_allow_open_gun_resp.setMinimumSize(QSize(200, 0))
        self.ipt_allow_open_gun_resp.setReadOnly(True)

        self.horizontalLayout_10.addWidget(self.ipt_allow_open_gun_resp)


        self.verticalLayout_6.addLayout(self.horizontalLayout_10)

        # 协议测试区域 - 使用下拉菜单选择
        self.horizontalLayout_protocol = QHBoxLayout()
        self.horizontalLayout_protocol.setObjectName(u"horizontalLayout_protocol")
        
        # 协议命令选择下拉菜单
        self.cbox_protocol_cmd = QComboBox(self.tab_hv)
        self.cbox_protocol_cmd.setObjectName(u"cbox_protocol_cmd")
        self.cbox_protocol_cmd.setMinimumSize(QSize(150, 0))
        self.horizontalLayout_protocol.addWidget(self.cbox_protocol_cmd)

        # 参数输入框（可选）
        self.ipt_protocol_param = QLineEdit(self.tab_hv)
        self.ipt_protocol_param.setObjectName(u"ipt_protocol_param")
        self.ipt_protocol_param.setMaximumSize(QSize(80, 16777215))
        self.ipt_protocol_param.setPlaceholderText("参数")
        self.horizontalLayout_protocol.addWidget(self.ipt_protocol_param)

        # 执行按钮
        self.btn_protocol_execute = QPushButton(self.tab_hv)
        self.btn_protocol_execute.setObjectName(u"btn_protocol_execute")
        self.btn_protocol_execute.setMinimumSize(QSize(60, 0))
        self.btn_protocol_execute.setMaximumSize(QSize(80, 16777215))
        self.horizontalLayout_protocol.addWidget(self.btn_protocol_execute)

        self.horizontalSpacer_protocol = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.horizontalLayout_protocol.addItem(self.horizontalSpacer_protocol)

        self.verticalLayout_6.addLayout(self.horizontalLayout_protocol)

        # 协议测试响应显示区域
        self.ipt_protocol_response = QLineEdit(self.tab_hv)
        self.ipt_protocol_response.setObjectName(u"ipt_protocol_response")
        self.ipt_protocol_response.setMinimumSize(QSize(0, 60))
        self.ipt_protocol_response.setMaximumSize(QSize(16777215, 80))
        self.ipt_protocol_response.setReadOnly(True)
        self.ipt_protocol_response.setStyleSheet("QLineEdit { padding: 5px; }")

        self.verticalLayout_6.addWidget(self.ipt_protocol_response)

        self.verticalSpacer_5 = QSpacerItem(20, 50, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_6.addItem(self.verticalSpacer_5)

        self.tab_modules.addTab(self.tab_hv, "")
        self.tab_focus = QWidget()
        self.tab_focus.setObjectName(u"tab_focus")
        self.verticalLayout_3 = QVBoxLayout(self.tab_focus)
        self.verticalLayout_3.setSpacing(0)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.frame_2 = QFrame(self.tab_focus)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setFrameShape(QFrame.Shape.Box)
        self.frame_2.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_6 = QHBoxLayout(self.frame_2)
        self.horizontalLayout_6.setSpacing(2)
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.horizontalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.btn_ob = QPushButton(self.frame_2)
        self.btn_ob.setObjectName(u"btn_ob")
        self.btn_ob.setMaximumSize(QSize(45, 16777215))

        self.horizontalLayout_6.addWidget(self.btn_ob)

        self.slider_ob = QEditSlider(self.frame_2)
        self.slider_ob.setObjectName(u"slider_ob")

        self.horizontalLayout_6.addWidget(self.slider_ob)

        self.line = QFrame(self.frame_2)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.Shape.VLine)
        self.line.setFrameShadow(QFrame.Shadow.Sunken)

        self.horizontalLayout_6.addWidget(self.line)

        self.horizontalSpacer_6 = QSpacerItem(20, 20, QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_6.addItem(self.horizontalSpacer_6)

        self.btn_af = QPushButton(self.frame_2)
        self.btn_af.setObjectName(u"btn_af")
        self.btn_af.setMaximumSize(QSize(16777215, 16777215))

        self.horizontalLayout_6.addWidget(self.btn_af)

        self.horizontalLayout_6.setStretch(1, 1)

        self.verticalLayout_3.addWidget(self.frame_2)

        self.verticalSpacer = QSpacerItem(20, 62, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_3.addItem(self.verticalSpacer)

        self.verticalLayout_3.setStretch(0, 1)
        self.tab_modules.addTab(self.tab_focus, "")
        self.tab_stage = QWidget()
        self.tab_stage.setObjectName(u"tab_stage")
        self.verticalLayout_4 = QVBoxLayout(self.tab_stage)
        self.verticalLayout_4.setSpacing(0)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.verticalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.frame_8 = QFrame(self.tab_stage)
        self.frame_8.setObjectName(u"frame_8")
        self.frame_8.setFrameShape(QFrame.Shape.Box)
        self.frame_8.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_7 = QHBoxLayout(self.frame_8)
        self.horizontalLayout_7.setSpacing(6)
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.horizontalLayout_7.setContentsMargins(0, 0, 0, 0)
        self.btn_stage_xy_pos = QPushButton(self.frame_8)
        self.btn_stage_xy_pos.setObjectName(u"btn_stage_xy_pos")
        self.btn_stage_xy_pos.setMaximumSize(QSize(80, 16777215))

        self.horizontalLayout_7.addWidget(self.btn_stage_xy_pos)

        self.input_stage_xy_pos = QLineEdit(self.frame_8)
        self.input_stage_xy_pos.setObjectName(u"input_stage_xy_pos")
        self.input_stage_xy_pos.setMaximumSize(QSize(180, 16777215))

        self.horizontalLayout_7.addWidget(self.input_stage_xy_pos)

        self.btn_stage_xy_goto = QPushButton(self.frame_8)
        self.btn_stage_xy_goto.setObjectName(u"btn_stage_xy_goto")
        self.btn_stage_xy_goto.setMinimumSize(QSize(45, 0))
        self.btn_stage_xy_goto.setMaximumSize(QSize(16777215, 16777215))

        self.horizontalLayout_7.addWidget(self.btn_stage_xy_goto)

        self.frame_7 = QFrame(self.frame_8)
        self.frame_7.setObjectName(u"frame_7")
        self.frame_7.setFrameShape(QFrame.Shape.StyledPanel)
        self.frame_7.setFrameShadow(QFrame.Shadow.Raised)
        self.gridLayout = QGridLayout(self.frame_7)
        self.gridLayout.setSpacing(1)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_10 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_10, 0, 0, 1, 1)


        self.horizontalLayout_7.addWidget(self.frame_7)


        self.verticalLayout_4.addWidget(self.frame_8)

        self.frame_6 = QFrame(self.tab_stage)
        self.frame_6.setObjectName(u"frame_6")
        self.frame_6.setFrameShape(QFrame.Shape.StyledPanel)
        self.frame_6.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_8 = QHBoxLayout(self.frame_6)
        self.horizontalLayout_8.setSpacing(6)
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.horizontalLayout_8.setContentsMargins(0, 0, 0, 0)
        self.label_3 = QLabel(self.frame_6)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setMinimumSize(QSize(70, 0))
        self.label_3.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.horizontalLayout_8.addWidget(self.label_3)

        self.input_stage_xy_rval = QLineEdit(self.frame_6)
        self.input_stage_xy_rval.setObjectName(u"input_stage_xy_rval")
        self.input_stage_xy_rval.setMaximumSize(QSize(60, 16777215))

        self.horizontalLayout_8.addWidget(self.input_stage_xy_rval)

        self.frame = QFrame(self.frame_6)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.Shape.Box)
        self.frame.setFrameShadow(QFrame.Shadow.Raised)
        self.gridLayout_2 = QGridLayout(self.frame)
        self.gridLayout_2.setSpacing(0)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setContentsMargins(0, 0, 0, 0)
        self.btn_stage_xy_move_up = QToolButton(self.frame)
        self.btn_stage_xy_move_up.setObjectName(u"btn_stage_xy_move_up")
        self.btn_stage_xy_move_up.setMaximumSize(QSize(30, 15))
        self.btn_stage_xy_move_up.setArrowType(Qt.ArrowType.UpArrow)

        self.gridLayout_2.addWidget(self.btn_stage_xy_move_up, 0, 1, 1, 1)

        self.btn_stage_xy_move_down = QToolButton(self.frame)
        self.btn_stage_xy_move_down.setObjectName(u"btn_stage_xy_move_down")
        self.btn_stage_xy_move_down.setMaximumSize(QSize(30, 15))
        self.btn_stage_xy_move_down.setArrowType(Qt.ArrowType.DownArrow)

        self.gridLayout_2.addWidget(self.btn_stage_xy_move_down, 1, 1, 1, 1)

        self.btn_stage_xy_move_right = QToolButton(self.frame)
        self.btn_stage_xy_move_right.setObjectName(u"btn_stage_xy_move_right")
        self.btn_stage_xy_move_right.setMaximumSize(QSize(30, 15))
        self.btn_stage_xy_move_right.setArrowType(Qt.ArrowType.RightArrow)

        self.gridLayout_2.addWidget(self.btn_stage_xy_move_right, 1, 2, 1, 1)

        self.btn_stage_xy_move_left = QToolButton(self.frame)
        self.btn_stage_xy_move_left.setObjectName(u"btn_stage_xy_move_left")
        self.btn_stage_xy_move_left.setMaximumSize(QSize(30, 15))
        self.btn_stage_xy_move_left.setArrowType(Qt.ArrowType.LeftArrow)

        self.gridLayout_2.addWidget(self.btn_stage_xy_move_left, 1, 0, 1, 1)


        self.horizontalLayout_8.addWidget(self.frame)

        self.horizontalSpacer_4 = QSpacerItem(277, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_8.addItem(self.horizontalSpacer_4)


        self.verticalLayout_4.addWidget(self.frame_6)

        self.verticalSpacer_3 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_4.addItem(self.verticalSpacer_3)

        self.tab_modules.addTab(self.tab_stage, "")
        self.tab_snap = QWidget()
        self.tab_snap.setObjectName(u"tab_snap")
        self.verticalLayout_5 = QVBoxLayout(self.tab_snap)
        self.verticalLayout_5.setSpacing(0)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.verticalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.frame_4 = QFrame(self.tab_snap)
        self.frame_4.setObjectName(u"frame_4")
        self.frame_4.setFrameShape(QFrame.Shape.Box)
        self.frame_4.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_3 = QHBoxLayout(self.frame_4)
        self.horizontalLayout_3.setSpacing(3)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.label_9 = QLabel(self.frame_4)
        self.label_9.setObjectName(u"label_9")

        self.horizontalLayout_3.addWidget(self.label_9)

        self.cbox_mag = QComboBox(self.frame_4)
        self.cbox_mag.setObjectName(u"cbox_mag")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.cbox_mag.sizePolicy().hasHeightForWidth())
        self.cbox_mag.setSizePolicy(sizePolicy1)
        self.cbox_mag.setMinimumSize(QSize(80, 0))
        self.cbox_mag.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow)

        self.horizontalLayout_3.addWidget(self.cbox_mag)

        self.input_mag = QLineEdit(self.frame_4)
        self.input_mag.setObjectName(u"input_mag")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.input_mag.sizePolicy().hasHeightForWidth())
        self.input_mag.setSizePolicy(sizePolicy2)
        self.input_mag.setMinimumSize(QSize(80, 0))
        self.input_mag.setMaximumSize(QSize(50, 16777215))

        self.horizontalLayout_3.addWidget(self.input_mag)

        self.line_5 = QFrame(self.frame_4)
        self.line_5.setObjectName(u"line_5")
        self.line_5.setFrameShape(QFrame.Shape.VLine)
        self.line_5.setFrameShadow(QFrame.Shadow.Sunken)

        self.horizontalLayout_3.addWidget(self.line_5)

        self.label = QLabel(self.frame_4)
        self.label.setObjectName(u"label")

        self.horizontalLayout_3.addWidget(self.label)

        self.input_field_size = QLineEdit(self.frame_4)
        self.input_field_size.setObjectName(u"input_field_size")
        sizePolicy2.setHeightForWidth(self.input_field_size.sizePolicy().hasHeightForWidth())
        self.input_field_size.setSizePolicy(sizePolicy2)
        self.input_field_size.setMinimumSize(QSize(80, 0))
        self.input_field_size.setMaximumSize(QSize(16777215, 16777215))

        self.horizontalLayout_3.addWidget(self.input_field_size)

        self.label_2 = QLabel(self.frame_4)
        self.label_2.setObjectName(u"label_2")

        self.horizontalLayout_3.addWidget(self.label_2)

        self.input_field_rotation = QLineEdit(self.frame_4)
        self.input_field_rotation.setObjectName(u"input_field_rotation")
        sizePolicy2.setHeightForWidth(self.input_field_rotation.sizePolicy().hasHeightForWidth())
        self.input_field_rotation.setSizePolicy(sizePolicy2)
        self.input_field_rotation.setMinimumSize(QSize(60, 0))
        self.input_field_rotation.setMaximumSize(QSize(50, 16777215))

        self.horizontalLayout_3.addWidget(self.input_field_rotation)

        self.label_4 = QLabel(self.frame_4)
        self.label_4.setObjectName(u"label_4")

        self.horizontalLayout_3.addWidget(self.label_4)

        self.horizontalSpacer_2 = QSpacerItem(110, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer_2)


        self.verticalLayout_5.addWidget(self.frame_4)

        self.frame_15 = QFrame(self.tab_snap)
        self.frame_15.setObjectName(u"frame_15")
        self.frame_15.setFrameShape(QFrame.Shape.Box)
        self.frame_15.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_14 = QHBoxLayout(self.frame_15)
        self.horizontalLayout_14.setSpacing(3)
        self.horizontalLayout_14.setObjectName(u"horizontalLayout_14")
        self.horizontalLayout_14.setContentsMargins(0, 0, 0, 0)
        self.label_6 = QLabel(self.frame_15)
        self.label_6.setObjectName(u"label_6")

        self.horizontalLayout_14.addWidget(self.label_6)

        self.cbox_cap_avg = QComboBox(self.frame_15)
        self.cbox_cap_avg.setObjectName(u"cbox_cap_avg")
        self.cbox_cap_avg.setMaximumSize(QSize(35, 16777215))

        self.horizontalLayout_14.addWidget(self.cbox_cap_avg)

        self.label_7 = QLabel(self.frame_15)
        self.label_7.setObjectName(u"label_7")

        self.horizontalLayout_14.addWidget(self.label_7)

        self.cbox_cap_size = QComboBox(self.frame_15)
        self.cbox_cap_size.setObjectName(u"cbox_cap_size")
        self.cbox_cap_size.setMinimumSize(QSize(100, 0))

        self.horizontalLayout_14.addWidget(self.cbox_cap_size)

        self.line_2 = QFrame(self.frame_15)
        self.line_2.setObjectName(u"line_2")
        self.line_2.setFrameShape(QFrame.Shape.VLine)
        self.line_2.setFrameShadow(QFrame.Shadow.Sunken)

        self.horizontalLayout_14.addWidget(self.line_2)

        self.line_3 = QFrame(self.frame_15)
        self.line_3.setObjectName(u"line_3")
        self.line_3.setFrameShape(QFrame.Shape.VLine)
        self.line_3.setFrameShadow(QFrame.Shadow.Sunken)

        self.horizontalLayout_14.addWidget(self.line_3)

        self.ckb_snap_save = QCheckBox(self.frame_15)
        self.ckb_snap_save.setObjectName(u"ckb_snap_save")

        self.horizontalLayout_14.addWidget(self.ckb_snap_save)

        self.btn_snap = QPushButton(self.frame_15)
        self.btn_snap.setObjectName(u"btn_snap")
        self.btn_snap.setMaximumSize(QSize(60, 16777215))

        self.horizontalLayout_14.addWidget(self.btn_snap)

        self.btn_play = QPushButton(self.frame_15)
        self.btn_play.setObjectName(u"btn_play")
        self.btn_play.setMaximumSize(QSize(60, 16777215))

        self.horizontalLayout_14.addWidget(self.btn_play)

        self.horizontalSpacer_3 = QSpacerItem(61, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_14.addItem(self.horizontalSpacer_3)

        self.btn_remap = QPushButton(self.frame_15)
        self.btn_remap.setObjectName(u"btn_remap")
        self.btn_remap.setMaximumSize(QSize(35, 16777215))

        self.horizontalLayout_14.addWidget(self.btn_remap)


        self.verticalLayout_5.addWidget(self.frame_15)

        self.verticalSpacer_6 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_5.addItem(self.verticalSpacer_6)

        self.tab_modules.addTab(self.tab_snap, "")
        self.tab_nav = QWidget()
        self.tab_nav.setObjectName(u"tab_nav")
        self.verticalLayout_7 = QVBoxLayout(self.tab_nav)
        self.verticalLayout_7.setSpacing(2)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.verticalLayout_7.setContentsMargins(0, 0, 0, 0)
        self.frame_9 = QFrame(self.tab_nav)
        self.frame_9.setObjectName(u"frame_9")
        self.frame_9.setFrameShape(QFrame.Shape.StyledPanel)
        self.frame_9.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_9 = QHBoxLayout(self.frame_9)
        self.horizontalLayout_9.setSpacing(2)
        self.horizontalLayout_9.setObjectName(u"horizontalLayout_9")
        self.horizontalLayout_9.setContentsMargins(0, 0, 0, 0)
        self.btn_get_nav_info = QPushButton(self.frame_9)
        self.btn_get_nav_info.setObjectName(u"btn_get_nav_info")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.btn_get_nav_info.sizePolicy().hasHeightForWidth())
        self.btn_get_nav_info.setSizePolicy(sizePolicy3)
        self.btn_get_nav_info.setMaximumSize(QSize(60, 16777215))

        self.horizontalLayout_9.addWidget(self.btn_get_nav_info)

        self.horizontalSpacer_8 = QSpacerItem(247, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_9.addItem(self.horizontalSpacer_8)

        self.btn_nav_circle_marker = QPushButton(self.frame_9)
        self.btn_nav_circle_marker.setObjectName(u"btn_nav_circle_marker")

        self.horizontalLayout_9.addWidget(self.btn_nav_circle_marker)

        self.btn_nav_marker_align = QPushButton(self.frame_9)
        self.btn_nav_marker_align.setObjectName(u"btn_nav_marker_align")

        self.horizontalLayout_9.addWidget(self.btn_nav_marker_align)

        self.rbtn_nav_enable_calib = QRadioButton(self.frame_9)
        self.rbtn_nav_enable_calib.setObjectName(u"rbtn_nav_enable_calib")

        self.horizontalLayout_9.addWidget(self.rbtn_nav_enable_calib)


        self.verticalLayout_7.addWidget(self.frame_9)

        self.verticalSpacer_4 = QSpacerItem(20, 36, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_7.addItem(self.verticalSpacer_4)

        self.tab_modules.addTab(self.tab_nav, "")
        self.tab = QWidget()
        self.tab.setObjectName(u"tab")
        self.verticalLayout_8 = QVBoxLayout(self.tab)
        self.verticalLayout_8.setObjectName(u"verticalLayout_8")
        self.horizontalLayout_11 = QHBoxLayout()
        self.horizontalLayout_11.setObjectName(u"horizontalLayout_11")
        self.cbox_vzem_type = QComboBox(self.tab)
        self.cbox_vzem_type.setObjectName(u"cbox_vzem_type")
        self.cbox_vzem_type.setMinimumSize(QSize(120, 0))

        self.horizontalLayout_11.addWidget(self.cbox_vzem_type)

        self.horizontalSpacer_9 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_11.addItem(self.horizontalSpacer_9)

        self.btn_vzem_start = QPushButton(self.tab)
        self.btn_vzem_start.setObjectName(u"btn_vzem_start")

        self.horizontalLayout_11.addWidget(self.btn_vzem_start)


        self.verticalLayout_8.addLayout(self.horizontalLayout_11)

        self.horizontalLayout_12 = QHBoxLayout()
        self.horizontalLayout_12.setObjectName(u"horizontalLayout_12")

        self.verticalLayout_8.addLayout(self.horizontalLayout_12)

        self.horizontalLayout_13 = QHBoxLayout()
        self.horizontalLayout_13.setObjectName(u"horizontalLayout_13")
        self.le_vzem_json = QLineEdit(self.tab)
        self.le_vzem_json.setObjectName(u"le_vzem_json")

        self.horizontalLayout_13.addWidget(self.le_vzem_json)

        self.btn_vzem_open_json = QPushButton(self.tab)
        self.btn_vzem_open_json.setObjectName(u"btn_vzem_open_json")

        self.horizontalLayout_13.addWidget(self.btn_vzem_open_json)


        self.verticalLayout_8.addLayout(self.horizontalLayout_13)

        self.verticalSpacer_7 = QSpacerItem(20, 50, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_8.addItem(self.verticalSpacer_7)

        self.tab_modules.addTab(self.tab, "")

        self.verticalLayout.addWidget(self.tab_modules)


        self.retranslateUi(Form)

        self.tabWidget_3.setCurrentIndex(0)
        self.tab_modules.setCurrentIndex(6)


        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate("Form", u"Form", None))
        self.tabWidget_3.setTabText(self.tabWidget_3.indexOf(self.tab_sem_img), QCoreApplication.translate("Form", u"\u7535\u955c\u56fe", None))
        self.tabWidget_3.setTabText(self.tabWidget_3.indexOf(self.tab_nav_img), QCoreApplication.translate("Form", u"\u5bfc\u822a\u56fe", None))
        self.btn_handshake.setText(QCoreApplication.translate("Form", u"\u626b\u63cf\u5728\u7ebf\u8bbe\u5907", None))
        self.btn_zem_sync.setText(QCoreApplication.translate("Form", u"\u540c\u6b65\u72b6\u6001", None))
        self.btn_send.setText(QCoreApplication.translate("Form", u"\u53d1\u9001\u547d\u4ee4", None))
        self.label_8.setText(QCoreApplication.translate("Form", u"\u53d1\u9001:", None))
        self.lbl_cmd_send.setText("")
        self.label_5.setText(QCoreApplication.translate("Form", u"\u63a5\u6536:", None))
        self.lbl_cmd_rcv.setText("")
        self.tab_modules.setTabText(self.tab_modules.indexOf(self.tab_conn), QCoreApplication.translate("Form", u"\u8fde\u63a5", None))
        self.btn_hv_get.setText(QCoreApplication.translate("Form", u"\u5f53\u524d\u7535\u538b:", None))
        self.ipt_hv.setText("")
        self.label_10.setText(QCoreApplication.translate("Form", u"KV", None))
        self.btn_hv_set.setText(QCoreApplication.translate("Form", u"\u8bbe\u7f6e", None))
        self.btn_gun_on.setText(QCoreApplication.translate("Form", u"\u5f00\u67aa", None))
        self.btn_gun_off.setText(QCoreApplication.translate("Form", u"\u5173\u67aa", None))
        self.btn_allow_open_gun.setText(QCoreApplication.translate("Form", u"\u5141\u8bb8\u5f00\u67aa", None))
        self.btn_protocol_execute.setText(QCoreApplication.translate("Form", u"\u6267\u884c", None))
        self.tab_modules.setTabText(self.tab_modules.indexOf(self.tab_hv), QCoreApplication.translate("Form", u"\u9ad8\u538b", None))
        self.btn_ob.setText(QCoreApplication.translate("Form", u"\u5f53\u524d\u503c:", None))
        self.btn_af.setText(QCoreApplication.translate("Form", u"AF", None))
        self.tab_modules.setTabText(self.tab_modules.indexOf(self.tab_focus), QCoreApplication.translate("Form", u"\u5bf9\u7126", None))
        self.btn_stage_xy_pos.setText(QCoreApplication.translate("Form", u"\u5f53\u524d\u5750\u6807:", None))
        self.input_stage_xy_pos.setText(QCoreApplication.translate("Form", u"0,0", None))
        self.btn_stage_xy_goto.setText(QCoreApplication.translate("Form", u"GOTO", None))
        self.label_3.setText(QCoreApplication.translate("Form", u"\u76f8\u5bf9\u8fd0\u52a8:", None))
        self.input_stage_xy_rval.setText(QCoreApplication.translate("Form", u"10", None))
        self.btn_stage_xy_move_up.setText(QCoreApplication.translate("Form", u"...", None))
        self.btn_stage_xy_move_down.setText(QCoreApplication.translate("Form", u"...", None))
        self.btn_stage_xy_move_right.setText(QCoreApplication.translate("Form", u"...", None))
        self.btn_stage_xy_move_left.setText(QCoreApplication.translate("Form", u"...", None))
        self.tab_modules.setTabText(self.tab_modules.indexOf(self.tab_stage), QCoreApplication.translate("Form", u"\u6837\u54c1\u53f0", None))
        self.label_9.setText(QCoreApplication.translate("Form", u"\u653e\u5927\u500d\u6570:", None))
        self.input_mag.setText(QCoreApplication.translate("Form", u"500", None))
        self.label.setText(QCoreApplication.translate("Form", u"\u626b\u63cf\u573a:", None))
        self.input_field_size.setText(QCoreApplication.translate("Form", u"520", None))
        self.label_2.setText(QCoreApplication.translate("Form", u"\u03bcm   ", None))
        self.input_field_rotation.setText(QCoreApplication.translate("Form", u"0", None))
        self.label_4.setText(QCoreApplication.translate("Form", u"\u00b0", None))
        self.label_6.setText(QCoreApplication.translate("Form", u"\u62cd\u7167\u6863\u4f4d:", None))
        self.label_7.setText(QCoreApplication.translate("Form", u"\u56fe\u50cf\u5c3a\u5bf8:", None))
        self.ckb_snap_save.setText(QCoreApplication.translate("Form", u"\u4fdd\u5b58", None))
        self.btn_snap.setText(QCoreApplication.translate("Form", u"\u62cd\u7167", None))
        self.btn_play.setText(QCoreApplication.translate("Form", u"\u64ad\u653e", None))
        self.btn_remap.setText(QCoreApplication.translate("Form", u"\u6620\u5c04", None))
        self.tab_modules.setTabText(self.tab_modules.indexOf(self.tab_snap), QCoreApplication.translate("Form", u"\u62cd\u7167", None))
        self.btn_get_nav_info.setText(QCoreApplication.translate("Form", u"\u5bfc\u822a\u56fe", None))
        self.btn_nav_circle_marker.setText(QCoreApplication.translate("Form", u"\u5706\u5f62\u6807\u8bb0", None))
        self.btn_nav_marker_align.setText(QCoreApplication.translate("Form", u"\u6807\u8bb0\u70b9\u5bf9\u9f50", None))
        self.rbtn_nav_enable_calib.setText(QCoreApplication.translate("Form", u"\u4f7f\u80fd", None))
        self.tab_modules.setTabText(self.tab_modules.indexOf(self.tab_nav), QCoreApplication.translate("Form", u"\u5bfc\u822a", None))
        self.btn_vzem_start.setText(QCoreApplication.translate("Form", u"\u5f00\u542f", None))
        self.btn_vzem_open_json.setText(QCoreApplication.translate("Form", u"\u6253\u5f00\u62cd\u56fe\u4efb\u52a1", None))
        self.tab_modules.setTabText(self.tab_modules.indexOf(self.tab), QCoreApplication.translate("Form", u"\u6a21\u62df", None))
    # retranslateUi

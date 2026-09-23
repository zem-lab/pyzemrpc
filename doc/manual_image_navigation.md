# 手动实时图导航（2026-09-23）

SDK 1.2.6.dev2026092302：`device.set_roi_nav(width, height, bbox)`。
UDP：`SetRoiNav:width,height,x0,y0,x1,y1`。所有数字有限，点/矩形在图像范围内；点的两角相同，保持倍率。矩形按长边比例变倍。

电镜端使用当前光学状态自动决定移台或束移；无需视频 token、当前倍率或束移开关。旧九参数帧绑定接口已替换，需同步部署 Instrument。SetRoiNav 超时不自动重试；返回 accepted 只表示接受命令。手动倍率仍使用 SetMag。

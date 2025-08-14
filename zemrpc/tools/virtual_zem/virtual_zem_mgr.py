#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import sys
import time
import socket
import subprocess
from loguru import logger
from pathlib import Path

from jgb.util import py_util, file_util

from zemrpc import app_cfg


class VZemMgr:
    def __init__(self):
        self._vzem_proc = None
        self._vzem_log_fp = None
        self._vzem_log_path = None

    def start_vzem(self):
        """
        启动 virtual ZEM (uvicorn main.py)
        vzem_type:
          builtin (默认) 使用模块 zemrpc.tools.virtual_zem.main
          其它: 传入.py脚本路径
        """
        host = "127.0.0.1"
        port = 61600

        def port_open():
            try:
                with socket.create_connection((host, port), timeout=0.4):
                    return True
            except OSError:
                return False

        # 已有实例在监听
        if port_open():
            logger.info(f"virtual ZEM 已在运行 {host}:{port}")
            return True

        # 进程对象还活着
        if self._vzem_proc and self._vzem_proc.poll() is None:
            logger.info("virtual ZEM 进程已启动")
            return True

        from zemrpc.tools.virtual_zem import main as m

        py = file_util.resolve_filepath(py_util.get_script_path(m))

        if py.exists():
            cmd = [sys.executable, str(py)]
        else:
            cmd = [sys.executable, "-m", "zemrpc.tools.virtual_zem.main"]

        try:
            logger.info(f"启动 virtual ZEM: {' '.join(cmd)}")
            # 准备日志文件
            file_util.ensure_dir(app_cfg.log_dir)
            self._vzem_log_path = app_cfg.log_dir / "virtual_zem.stdout.log"
            self._vzem_log_fp = self._vzem_log_path.open("a", encoding="utf-8")
            self._vzem_log_fp.write(f"\n==== virtual ZEM start {time.strftime('%Y-%m-%d %H:%M:%S')} cmd={' '.join(cmd)} ====\n")
            self._vzem_log_fp.flush()
            creationflags = 0x00000200 if sys.platform.startswith("win") else 0  # CREATE_NEW_PROCESS_GROUP
            self._vzem_proc = subprocess.Popen(
                cmd,
                stdout=self._vzem_log_fp,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=creationflags,
            )
        except Exception as e:
            logger.exception(f"启动失败: {e}")
            if self._vzem_log_fp:
                try:
                    self._vzem_log_fp.write(f"==== start failed {time.strftime('%Y-%m-%d %H:%M:%S')} ====\n")
                    self._vzem_log_fp.close()
                except Exception:
                    pass
                finally:
                    self._vzem_log_fp = None
            return False

        # 等待端口就绪
        deadline = time.time() + 8
        while time.time() < deadline:
            if self._vzem_proc.poll() is not None:
                logger.error("virtual ZEM 进程提前退出")
                return False
            if port_open():
                logger.info("virtual ZEM 启动成功")
                # 更新远端地址
                return True
            time.sleep(0.3)

        logger.error("virtual ZEM 启动超时")
        return False

    def stop_vzem(self, timeout: float = 5.0):
        """
        停止通过 start_vzem 启动的 virtual ZEM
        """
        proc = self._vzem_proc
        if not proc:
            logger.info("无 virtual ZEM 进程可停止")
            return True

        if proc.poll() is not None:
            logger.info("virtual ZEM 进程已结束")
            self._vzem_proc = None
            return True

        logger.info("尝试停止 virtual ZEM")
        try:
            # 优先 terminate
            proc.terminate()
        except Exception as e:
            logger.warning(f"terminate 失败: {e}")

        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.warning("优雅停止超时，执行 kill")
            try:
                proc.kill()
                proc.wait(timeout=2)
            except Exception as e:
                logger.error(f"kill 失败: {e}")
                return False

        rc = proc.returncode
        logger.info(f"virtual ZEM 已退出 returncode={rc}")
        # 关闭日志
        if self._vzem_log_fp:
            try:
                self._vzem_log_fp.write(f"==== virtual ZEM exit rc={rc} {time.strftime('%Y-%m-%d %H:%M:%S')} ====\n")
                self._vzem_log_fp.close()
            except Exception:
                pass
            finally:
                self._vzem_log_fp = None
        self._vzem_proc = None
        return True

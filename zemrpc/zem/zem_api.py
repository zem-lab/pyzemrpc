#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import time
import copy
from loguru import logger
from pydantic import Field
from typing import List, Tuple
from transitions import Machine, EventData
from tenacity import retry, stop_after_attempt, wait_fixed, wait_random

from jgb.util import json_util
from jgb.util.dds_util import AppTreeNode, AppTreeNodeRequiredMixin

from zemrpc import app_cfg
from zemrpc.zem.context import ctx
from zemrpc.zem.models import EnumBeamSize, FieldWithLoc, NavImage, NavParam, ScanInfo, SnapArgs, StageMoveDirection, StagePos, ZemException, ZemImage, ZemState
from zemrpc.zem.conn.protocol import EnumCmd
from zemrpc.zem.zem_image_processor import ZemImageProcessorManager, normalize_with_drop
from zemrpc.zem.zem_rpc_device import ZemRpcDevice


class ZemApiMachine(Machine):
    transitions = [
        dict(trigger="enable", source=ZemState.Disable, dest=ZemState.Idel),
        dict(trigger="disable", source="*", dest=ZemState.Disable),
    ]

    def __init__(self):
        super().__init__(states=ZemState, transitions=self.transitions, initial=ZemState.Disable, send_event=True)
        self.subscribe(self.state_changed_log)

    def state_changed_log(self, event_data: EventData):
        logger.info(f"api state changed: {event_data.transition.source} -> {event_data.state.name}")

    def subscribe(self, func, trigger="", source="*", dest="*"):
        for transition in self.get_transitions(trigger, source, dest):
            transition.after.append(func)

    def unsubscribe(self, func, trigger="", source="*", dest="*"):
        for transition in self.get_transitions(trigger, source, dest):
            if func in transition.after:
                transition.after.remove(func)

    def api_state(self) -> ZemState:
        return self.state


def ensure_sync_done(func):
    def wrapper(*args, **kwargs):
        if not zem_api._init_sync:
            zem_api._init_sync = True
            zem_api.sync()
        return func(*args, **kwargs)

    return wrapper


class ZemApiModel(AppTreeNode):
    api_state: ZemState = Field(default=None, on_setattr=True)

    servers: List[Tuple[str, int]] = Field(default=None)
    nav_param: NavParam = Field(default=None)
    nav_param_calibed: NavParam = Field(default=None)
    nav_img: NavImage = Field(default=None, on_setattr=True)
    use_calib_nav_param: bool = Field(default=False)

    zem_img: ZemImage = Field(default=None, on_setattr=True)
    snap_args: SnapArgs = Field(default=SnapArgs())

    def field_with_loc(self, si: ScanInfo, pos: StagePos):
        if si is None:
            return
        ctx.pub_computed_attr(self, "field_with_loc", FieldWithLoc(scan_info=si, pos=pos))


class ZemApi(AppTreeNodeRequiredMixin):
    def __init__(self):
        self.m = ZemApiModel(ctx=ctx)
        self.n = ctx.add_node(self)

        self.device = ZemRpcDevice(name="instrument", parent=self.n)

        self.machine = ZemApiMachine()
        self.img_processor_mgr = ZemImageProcessorManager()
        self.m.api_state = self.machine.api_state()
        self.machine.subscribe(self.api_state_changed)

        self._init_sync = False
        if (nav_param := app_cfg.cfg_db.kv_db.get_obj("nav_param_calibed", NavParam)) is not None:
            logger.debug(f"load last nav_param_calibed: {nav_param}")
            self.m.nav_param_calibed = nav_param

        self.get_stage_pos = self.device.get_stage_pos
        self.video_play_on = self.device.video_play_on
        self.check_video_play = self.device.check_video_play
        self.get_ob = self.device.get_ob
        self.set_field_rotation = self.device.set_field_rotation

        self.update_img_processor(normalize_with_drop)

    def api_state_changed(self, event_data: EventData):
        self.m.api_state = event_data.state.value

    def update_remote_addr(self, addr: Tuple[str, int]):
        self.device.update_remote_addr(addr)
        self.machine.disable()
        self.machine.enable()
        # TODO 如果支持RPC接口，一次性同步状态信息

    def send_cmd(self, cmd: EnumCmd, args: str = None):
        self.device.ensure_connected()
        self.device.send_cmd(cmd, args)

    def handshake(self):
        servers = self.device.handshake()
        self.m.servers = servers
        return servers

    def set_beam_size(self, bs: EnumBeamSize):
        if zem_api.is_api_state_idel():
            return self.device.set_beam_size(bs)

    def set_ob(self, ob: int, wait_stable_ms=0):
        if zem_api.is_api_state_idel():
            ret = self.device.set_ob(ob)
            if ret and wait_stable_ms:
                time.sleep(wait_stable_ms / 1000)
            return ret

    def stage_xy_goto(self, xy):
        self.ensure_api_state_idel()
        self.device.set_stage_pos(StagePos(x=xy[0], y=xy[1]))
        self.m.field_with_loc(self.device.m.scan_info, self.device.m.stage_pos)

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_fixed(1) + wait_random(0, 1))
    def stage_xy_goto_closed(self, xy, stable_after_idle_ms=0):
        self.stage_xy_goto(xy)
        self.device.ensure_stage_idle()
        if stable_after_idle_ms:
            logger.debug(f"force sleep stable_after_idle_ms: {stable_after_idle_ms}ms")
            time.sleep(stable_after_idle_ms / 1000)

    def move_then_cap(self, xy, stable_after_idle_ms=0, png=None, **kwargs) -> ZemImage:
        self.stage_xy_goto_closed(xy, stable_after_idle_ms)
        img = self.snap(save=False, **kwargs)
        if png:
            img.dump(png)
        return img

    def mov_then_focus(self, xy, stable_after_idle_ms=0):
        self.stage_xy_goto_closed(xy, stable_after_idle_ms)
        self.run_autofocus()

    def run_autofocus(self):
        ob0 = self.device.get_ob()
        self.device.set_autofocus()
        self.device.ensure_af_done()
        ob = self.device.get_ob()
        logger.debug(f"autofocus done {ob0} -> {ob}")
        return ob

    def stage_xy_rmove(self, direction: StageMoveDirection, value: float):
        x = self.device.m.stage_pos.x
        y = self.device.m.stage_pos.y

        match direction:
            case StageMoveDirection.Up:
                y += value
            case StageMoveDirection.Down:
                y -= value
            case StageMoveDirection.Left:
                x -= value
            case StageMoveDirection.Right:
                x += value
        self.stage_xy_goto((x, y))

    def set_mag(self, mag: int):
        self.device.set_mag(mag)
        self.device.get_scan_info()
        self.m.field_with_loc(self.device.m.scan_info, self.device.m.stage_pos)

    def sync_scan_field(self):
        self.device.get_mag()
        self.device.get_scan_info()
        self.m.field_with_loc(self.device.m.scan_info, self.device.m.stage_pos)

    def sync_stage_and_scan_field(self):
        self.device.get_stage_pos()
        self.sync_scan_field()

    def get_nav_img(self) -> NavImage:
        img = self.device.get_nav_img()
        if img is None:
            return

        if self.m.use_calib_nav_param:
            nav = NavImage(ctime=time.time(), shape=img.shape[:2], nav_param=self.m.nav_param_calibed, img=img)
            logger.debug("use nav_param_calibed")
        else:
            self.m.nav_param = self.device.get_nav_param()
            nav = NavImage(ctime=time.time(), shape=img.shape[:2], nav_param=self.m.nav_param, img=img)
            logger.debug("get and use nav_param")

        self.m.nav_img = nav
        return self.m.nav_img

    def set_nav_param(self, p0x, p0y, cx, cy):
        self.m.nav_param_calibed = NavParam(p0x=p0x, p0y=p0y, cx=cx, cy=cy)
        app_cfg.cfg_db.kv_db.set_obj("nav_param_calibed", self.m.nav_param_calibed)

    def video_play_off(self):
        from zemrpc.zem.models import EnumImageSize

        snap_args = SnapArgs(pixel_avg=5, size=EnumImageSize.S512x512)
        zem_api.snap(snap_args=snap_args)

    def enable_calib_nav_param(self, enable):
        if not enable:
            nav = NavImage(ctime=time.time(), shape=self.m.nav_img.shape, nav_param=self.m.nav_param, img=self.m.nav_img.img)
            self.m.nav_img = nav
            self.m.use_calib_nav_param = False
            logger.debug("use nav_param")
            return True

        if self.m.nav_param_calibed is None:
            return False

        nav = NavImage(ctime=time.time(), shape=self.m.nav_img.shape, nav_param=self.m.nav_param_calibed, img=self.m.nav_img.img)
        self.m.nav_img = nav
        self.m.use_calib_nav_param = True
        logger.debug("use nav_param_calibed")
        return True

    def with_processor(self, p):
        return self.img_processor_mgr.with_processor(p)

    def update_img_processor(self, p):
        self.img_processor_mgr.update(p)

    @ensure_sync_done
    def snap(self, **kwargs) -> ZemImage:
        if (args := kwargs.pop("snap_args", None)) is None:
            args = copy.deepcopy(self.m.snap_args)
            args.save = kwargs.pop("save", args.save)

        if self.device.m.protocol_ng.is_available():
            zem_img = self.snap_ng(args, **kwargs)
        else:
            zem_img = self.snap_v1(args, **kwargs)

        self.m.zem_img = zem_img

        if args.save:
            zem_img.dump(ctx.logdir / "images")

        if kwargs.get("viedo_on", False):
            self.video_play_on()

        return self.m.zem_img

    def snap_v1(self, snap_args: SnapArgs, **kwargs):
        img = self.device.snap_simple(snap_args)
        meta = self.device.m.to_img_meta(snap_args.pixel_avg)
        bounds = FieldWithLoc(scan_info=self.device.m.scan_info, pos=self.device.m.stage_pos).img_bounds()
        img = self.img_processor_mgr(img)
        zem_img = ZemImage(img=img, meta=meta, bounds=bounds)
        return zem_img

    def snap_ng(self, snap_args: SnapArgs, **kwargs):
        resp = self.device.snap_rpc(snap_args.size.width, snap_args.size.height, snap_args.pixel_avg, snap_args.frame_avg)
        if not resp.success():
            raise ZemException.snap_ng_failed(f"ZEMRPC snap_ng failed: {resp.error}")

        img = resp.parse_image()
        bounds = resp.parse_img_bounds()
        meta = self.device.m.to_img_meta(snap_args.pixel_avg)
        img = self.img_processor_mgr(img)
        zem_img = ZemImage(img=img, meta=meta, bounds=bounds)
        # TODO meta中加入rpc结果
        return zem_img

    def sync(self):
        self.device.get_model()
        self.device.get_protocol_ng()
        # TODO 支持RPC时切换到RPC接口同步状态信息
        self.device.get_hv()
        self.device.get_stage_pos()
        self.device.get_beam_size()
        self.sync_scan_field()

        self.get_nav_img()
        logger.info(f"sync done: \n{json_util.dumps(self.device.m.model_dump(), indent=2)}")

        self._init_sync = True

    def is_api_state_idel(self):
        return self.m.api_state == ZemState.Idel

    def ensure_api_state_idel(self):
        self.device.ensure_connected()

        if not self.is_api_state_idel():
            raise ZemException.zem_api_not_ready("Zem API 忙")


zem_api = ZemApi()

"""JSON-RPC optical state; percentages and signed DAC counts remain distinct."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictInt


class OpticsPair(BaseModel):
    model_config = ConfigDict(strict=True, allow_inf_nan=False)

    # Missing calibration is null; a valid zero is still zero. Report any finite
    # out-of-range state as observed, rather than clipping a remote model value.
    x: float | None
    y: float | None
    x_dac: StrictInt
    y_dac: StrictInt


class AlignmentState(BaseModel):
    up: OpticsPair
    down: OpticsPair


class OpticsState(BaseModel):
    unit: Literal["percent"]
    source: Literal["instrument_model", "virtual_model"]
    astigmatism: OpticsPair
    alignment: AlignmentState


def update_optics_model(model, optics: OpticsState | None):
    """Refresh all optical cache fields together, including older-server absence."""
    model.optics = optics
    model.ast = None if optics is None else (optics.astigmatism.x_dac, optics.astigmatism.y_dac)
    model.stig_x = None if optics is None else optics.astigmatism.x
    model.stig_y = None if optics is None else optics.astigmatism.y
    model.up_center_x = None if optics is None else optics.alignment.up.x
    model.up_center_y = None if optics is None else optics.alignment.up.y
    model.down_center_x = None if optics is None else optics.alignment.down.x
    model.down_center_y = None if optics is None else optics.alignment.down.y

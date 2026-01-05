# SPDX-License-Identifier: GPL-3.0-or-later

import numpy as np
from dataclasses import dataclass
from enum import Enum


class PrimitiveType(Enum):
    POINTS = "POINTS"
    LINES = "LINES"
    TRIS = "TRIS"


@dataclass
class RenderData:
    """GPU-ready render data for a feature"""
    vertices: np.ndarray
    normals: np.ndarray
    colors: np.ndarray
    primitive_type: PrimitiveType
    count: int = 0
    
    def __post_init__(self):
        self.count = len(self.vertices)

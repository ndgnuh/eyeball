from dataclasses import dataclass
from functools import cached_property
from typing import Optional

import torch
import numpy as np
from shapely.geometry import Polygon
from torch import nn
from torchvision.models import mobilenet_v3_small

from ..structures import ModelConfig, ModelType
from .detr_xyxy import DetrHead


class MeganeDetector(nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.feature = mobilenet_v3_small(num_classes=1).features
        if config.type == ModelType.DETR_XYXY:
            self.head = DetrHead(**config.head, num_classes=config.num_classes)

    @cached_property
    def num_feature_channels(self):
        with torch.no_grad():
            image = torch.rand(1, 3, 256, 256)
        feature_channels = self.feature(image).shape[1]
        return feature_channels

    def forward(self, batch):
        images = batch["image"]
        features = self.feature(images)
        outputs = self.head(features, batch)
        return outputs

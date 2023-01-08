from dataclasses import dataclass
from pytorch_lightning import LightningModule
from torch import nn, optim
import torch
from traceback import print_exc

from . import backbones, heads, losses
from .. import processor
from ..tools import init
from ..tools import remember


class Normalize(nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, image):
        return (image - 0.5) * 2


class Detector(nn.Sequential):
    def __init__(self, config):
        super().__init__()
        self.norm = Normalize()
        self.backbone = init.init_from_ns(
            backbones,
            config['backbone'],
            config['backbone_options']
        )
        self.head = init.init_from_ns(
            heads,
            config['head'],
            config['head_options']
        )

        self.processor = init.init_from_ns(
            processor,
            config['processor'],
            config.get('processor_options', {})
        )

        if 'weights' in config:
            try:
                w = torch.load(config['weights'], map_location='cpu')
                self.load_state_dict(w)
            except Exception:
                print_exc()

from os import path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel as _BaseModel
from pydantic import Field


class BaseModel(_BaseModel):
    @classmethod
    def from_file(cls, config_path):
        return cls.parse_obj(read(config_path))


def read(config_path):
    import yaml

    with open(config_path) as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    if "name" not in config:
        config["name"] = path.splitext(path.basename(config_path))[0]
    return config


def default_fabric_config():
    return dict(accelerator="auto")


class AugmentConfig(BaseModel):
    """
    Configuration for augmentation.

    Attributes:
        enabled (bool):
            Flag indicating if augmentation is enabled.
        background_images (List, optional):
            List of background images for augmentation. Defaults to an empty list.
        domain_images (List, optional):
            List of domain images for augmentation. Defaults to an empty list.
        prob (float):
            Probability of applying augmentation.

    Example:
        config = AugmentConfig(
            enabled=True,
            background_images=['bg1.jpg', 'bg2.jpg'],
            prob=0.5
        )
    """

    enabled: bool
    background_images: List = Field(default_factory=list)
    domain_images: List = Field(default_factory=list)
    prob: float = 0.3333


class TrainConfig(BaseModel):
    """Training configuration schema.

    Attributes:
        train_data:
            Path to train data annotation
        val_data:
            Path to validate data annotation
        augment:
            An `AugmentConfig`
        lr:
            Base learning rate
        augment:
            Augmentation config
        total_steps:
            Number of training iterations
        print_every:
            Logging interval in steps
        validate_every:
            Validate interval in steps
        dataloader:
            Dataloader config kwargs, default to `{}`
        fabric:
            Torch Fabric config, default to `dict(accelerator='auto')`
    """

    train_data: str
    val_data: str

    lr: float = 1e-4

    total_steps: int
    print_every: int
    validate_every: int

    augment: AugmentConfig
    dataloader: Dict = Field(default_factory=dict)
    fabric: Dict = Field(default_factory=default_fabric_config)


class ModelConfig(BaseModel):
    classes: List[str]
    name: str
    image_size: int
    head: Dict
    backbone: Dict
    neck: Dict

    single_class: bool = False
    continue_weight: Optional[str] = None
    inference_weight: Optional[str] = None

    # Stuffs for trainer
    @property
    def latest_weight_name(self):
        return f"{self.name}.latest.pt"

    @property
    def best_weight_name(self):
        return f"{self.name}.best.pt"

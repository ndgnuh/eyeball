import albumentations as A
import numpy as np
from typing import Optional
from dataclasses import dataclass
from typing import Callable
from PIL import Image


def no_augment():
    return None


def default_augment(p=0.3):
    keypoint_params = A.KeypointParams(format='xy', remove_invisible=False)

    return A.Compose([
        # Changing image coloring
        A.OneOf([
            A.CLAHE(p=p),
            A.ColorJitter(p=p),
            A.Emboss(p=p),
            A.HueSaturationValue(p=p),
            A.RandomBrightnessContrast(p=p),
            A.InvertImg(p=p),
            A.RGBShift(p=p),
            A.ToSepia(p=p),
            A.ToGray(p=p),
        ]),

        # Noises
        A.OneOf([
            A.ISONoise(p=p),
            A.MultiplicativeNoise(p=p),
        ]),

        # Dropouts
        A.OneOf([
            A.PixelDropout(p=p),
            A.ChannelDropout(p=p),
        ]),

        # Image degration
        A.OneOf([
            A.ImageCompression(p=p),
            A.GaussianBlur(p=p),
            A.Posterize(p=p),
            A.GlassBlur(sigma=0.1, max_delta=1, iterations=1, p=p),
            A.MedianBlur(blur_limit=1, p=p),
            A.MotionBlur(p=p),
        ]),

        # Spatial transform
        A.OneOf([
            # Doesn't work on keypoints
            # A.ElasticTransform(alpha=1, sigma=1, alpha_affine=1, p=p),
            A.Perspective(fit_output=True, p=p),

            # Removed due
            # A.PiecewiseAffine(nb_rows=3, nb_cols=3, p=p),

            # Removed due to making the output out of range
            A.ShiftScaleRotate(p=p),
            # A.SafeRotate((-5, 5), p=p),
        ])
    ], keypoint_params=keypoint_params)


@dataclass
class Augment:
    transform: Optional[Callable]

    def __call__(self, image, annotation):
        if self.transform is None:
            return image, annotation

        width, height = image.size
        polygons = np.array(annotation['polygons'])
        num_polygons = polygons.shape[0]

        # Use keypoints xy format to augment
        # The polygons are 0-1 normalized
        polygons = polygons.reshape(-1, 2)
        polygons[:, 0] *= width
        polygons[:, 1] *= height
        result = self.transform(
            image=np.array(image),
            keypoints=polygons,
        )

        # Outputs
        # Returns to the old annotion format
        image = Image.fromarray(result['image'])
        polygons = np.array(result['keypoints'])
        polygons[:, 0] /= width
        polygons[:, 1] /= height
        polygons = polygons.reshape(num_polygons, 4, 2)
        annotation['polygons'] = polygons.tolist()
        return image, annotation

    @classmethod
    def from_string(cls, augment: str):
        transform = dict(
            default=default_augment,
            none=no_augment,
            yes=default_augment,
            no=no_augment,
        )[augment]()
        return cls(transform)

import albumentations as A
import cv2
import numpy as np
import simpoly
import toolz
from PIL import Image

from megane import utils
from megane.data import Sample


def idendity(**kw):
    return kw


def encode(sample: Sample):
    """
    Encodes a Sample to albumentation inputs.

    Args:
        sample (Sample):
            The Sample object containing image and keypoints data.

    Returns:
        Dict:
            Albumentation input.

    Example:
        sample = Sample(image, boxes)
        enc = encode(sample)
        transform(**enc)
    """
    image = np.array(sample.image)
    classes = sample.classes
    boxes = sample.boxes
    h, w = image.shape[:2]
    masks = []
    keypoints = []
    for i, polygon in enumerate(boxes):
        polygon = simpoly.scale_to(polygon, w, h)
        keypoints.extend(polygon)
        masks.extend([i] * len(polygon))

    assert max(masks) == len(classes) - 1
    return dict(image=image, keypoints=keypoints, box_mapping=masks, classes=classes)


def decode(outputs):
    """
    Decodes the albumenation outputs into a Sample object.

    Args:
        outputs (dict):
            The outputs obtained from the encoding process.

    Returns:
        Sample:
            The decoded Sample object.

    Example:
        sample = Sample(image, boxes, classes, scores)
        outputs = {"image": encoded_image,
            "box_mapping": box_mapping, "keypoints": keypoints}
        decoded_sample = decode(sample, outputs)
    """
    image = Image.fromarray(outputs["image"])
    w, h = image.size
    classes = outputs["classes"]
    masks = outputs["box_mapping"]
    xy = outputs["keypoints"]

    # Conver keypoints to bounding boxes
    groups = toolz.groupby(lambda i: i[1], enumerate(masks))
    out_classes = []
    boxes = []
    for i, idx in groups.items():
        box = simpoly.scale_from([xy[j] for j, _ in idx], w, h)
        if len(box) > 2:
            boxes.append(box)
            out_classes.append(classes[i])

    # Correctness checking
    assert len(boxes) == len(out_classes)

    # Reconstruct another sample
    return Sample(
        image=image,
        boxes=boxes,
        classes=out_classes,
    )


def default_transform(prob, background_images, domain_images):
    transformations = [
        # Color effects
        A.OneOf(
            [
                A.RandomBrightnessContrast(),
                A.InvertImg(),
                A.ToGray(),
                A.Equalize(),
                A.ChannelDropout(),
                A.ChannelShuffle(),
                A.FancyPCA(),
                A.Solarize(),
                A.ToSepia(),
                A.ColorJitter(),
                A.RandomGamma(),
                A.RandomShadow(),
                A.RandomSunFlare(),
                A.RGBShift(),
            ],
            p=prob,
        ),
        # Degrade
        A.OneOf(
            [
                A.PixelDropout(),
                A.Downscale(interpolation=cv2.INTER_LINEAR),
                A.Blur(),
                A.MedianBlur(),
                A.ISONoise(),
                A.MultiplicativeNoise(),
                A.GaussNoise(),
            ],
            p=prob,
        ),
        # Geometric transform/rotate
        # A.OneOf(
        #     [
        #         A.Perspective(fit_output=True),
        #         A.SafeRotate((-180, 180), border_mode=cv2.BORDER_CONSTANT),
        #     ],
        #     p=prob,
        # )
        A.OneOf(
            [
                A.Affine(
                    scale=(0.4, 1),
                    rotate=(-30, 30),
                    translate_percent=0.0,
                    shear=0,
                    keep_ratio=True,
                    fit_output=True,
                ),
                A.RandomRotate90(),
                A.Transpose(),
            ],
            p=prob,
        ),
    ]

    if len(domain_images) > 0:
        domain_transforms = A.OneOf(
            [
                A.FDA(domain_images, beta_limit=0.025),
                A.HistogramMatching(domain_images),
                A.PixelDistributionAdaptation(domain_images),
            ],
            p=prob,
        )
        transformations.append(domain_transforms)
    return A.Compose(
        transformations,
        keypoint_params=A.KeypointParams(format="xy", remove_invisible=False),
    )

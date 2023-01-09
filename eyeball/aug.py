from PIL import Image, ImageOps, ImageColor, ImageEnhance, ImageChops
import random
import numpy as np


def rand(a, b, step):
    return random.choice(np.arange(a, b+step, step=step))


def gaussian_noise(image, level):
    noise = Image.effect_noise(image.size, 255).convert("RGB")
    return ImageChops.blend(image, noise, level)


def salt_and_pepper(image, prob):
    w, h = image.size
    mask = np.random.rand(h, w, 1) <= prob
    pors = (np.random.rand(h, w, 1) < 0.5) * 255
    image = np.array(image)
    image = pors * mask + (1 - mask) * image
    image = image.round().astype('uint8')
    return Image.fromarray(image)


def sometime(f, p=0.3):
    def wrapped(image):
        if random.random() < p:
            return f(image)
        return image
    return wrapped


def oneof(fs):
    def w(image):
        return random.choice(fs)(image)
    return w


def random_apply(fs, p):
    fs = [sometime(f, p) for f in fs]

    def w(image):
        for f in fs:
            image = f(image)
        return image
    return w


def randomized(f, ps):
    def w(image):
        image = f(image, random.choice(ps))
        return image
    return w


def brightness(image, p):
    return ImageEnhance.Brightness(image).enhance(p)


def contrast(image, p):
    return ImageEnhance.Contrast(image).enhance(p)


invert = ImageOps.invert

default_augment = random_apply([
    oneof([
        invert,
        ImageOps.autocontrast,
    ]),
    oneof([
        randomized(brightness, np.arange(0.8, 1.21, step=0.01)),
        randomized(contrast, np.arange(0.8, 1.21, step=0.01))
    ]),
    oneof([
        randomized(gaussian_noise, np.arange(0.05, 0.3, step=0.01)),
        randomized(salt_and_pepper, np.arange(0.05, 0.15, step=0.01)),
    ])
], 0.3)

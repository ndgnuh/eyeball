import random
import os
from pprint import pformat
from dataclasses import dataclass
from typing import Dict, Optional, Iterable, Generator
from collections import defaultdict
from functools import partial, reduce

import numpy as np
import torch
from lightning import Fabric
from torch import nn, optim
from torch.utils.data import DataLoader
from pydantic import BaseModel, Field
from tqdm import tqdm
from tensorboardX import SummaryWriter

from .processors import DetrProcessor
from .models import MeganeDetector
from .data import Dataset, MeganeDataset
from .structures import ModelConfig, TrainConfig
from .utils import Statistics

# augment import compose, RandomPermutation, with_probs


def loop_over_loader(loader: Iterable, n: int) -> Generator:
    """
    Returns a generator that iterates over `loader` steps by steps for `n` steps
    """
    step = 0
    while True:
        for batch in loader:
            step = step + 1
            yield step, batch
            if step >= n:
                return


class Trainer:
    def __init__(self, train_config: TrainConfig, model_config: ModelConfig):
        # Initialize model
        self.model = MeganeDetector(model_config)
        self.processor = DetrProcessor(
            image_width=model_config.image_width, image_height=model_config.image_height
        )
        self.fabric = Fabric(accelerator="auto")
        try:
            weights = utils.load_pt(model_config.pretrained_weights)
            self.model.load_state_dict(weights)
        except Exception as e:
            print(
                f"Can't not load pretrained weight \
                {model_config.pretrained_weights},\
                error: {e}, ignoring"
            )

        #
        # Loading data
        #
        def make_loader(train):
            data = MeganeDataset(train=train, transform=self.processor.encode)
            loader = DataLoader(
                data, collate_fn=self.processor.collate, **train_config.dataloader
            )
            return loader
        self.train_loader = make_loader(True)
        self.validate_loader = make_loader(False)

        # Optimizer
        self.optimizer = optim.AdamW(self.model.parameters(), lr=train_config.lr)
        # self.lr_scheduler = optim.lr_scheduler.OneCycleLR(
        #     self.optimizer,
        #     max_lr=train_config.lr,
        #     pct_start=0.01,
        #     # final_div_factor=2,
        #     total_steps=train_config.total_steps,
        # )
        self.logger = SummaryWriter(logdir=f"logs/{model_config.name}")

        # Store configs
        self.train_config = train_config
        self.model_config = model_config

    def train(self):
        total_steps = self.train_config.total_steps
        print_every = self.train_config.print_every
        validate_every = self.train_config.validate_every
        if print_every is None:
            print_every = max(1, validate_every // 5)

        fabric = self.fabric
        model, optimizer = self.fabric.setup(self.model, self.optimizer)
        # lr_scheduler = self.lr_scheduler
        train_loader = self.fabric.setup_dataloaders(self.train_loader)

        pbar = tqdm(
            loop_over_loader(train_loader, total_steps),
            total=total_steps,
            dynamic_ncols=True,
        )

        train_loss = Statistics(np.mean)
        for step, batch in pbar:
            optimizer.zero_grad()
            output: KieOutput = model(batch)
            fabric.backward(output.loss)
            fabric.clip_gradients(model, optimizer, max_norm=5)
            optimizer.step()
            # lr_scheduler.step()
            pbar.set_description(
                f"#{step}/{total_steps} loss: {output.loss.item():.4e}"
            )
            
            self.logger.add_scalar("loss", output.loss.item(), step)
            train_loss.append(output.loss.item())
            # self.metrics.lr = lr_scheduler.get_last_lr()[0]
            if step % print_every == 0:
                # self.metrics.training_loss.update(train_loss.get())

                # Checkpointing
                self.current_step = step
                self.save_model(self.model_config.latest_weight_path)
                train_loss = Statistics(np.mean)

            # if step % validate_every == 0:
            #     self.validate()

        # Save one last time
        self.save_model()

    @torch.no_grad()
    def validate(self, loader=None):
        model = self.fabric.setup(self.model)
        model = model.eval()
        loader = self.fabric.setup_dataloaders(loader or self.validate_loader)

        def dict_get_index(d, i):
            return {k: v[i] for k, v in d.items()}

        post_process = self.processor.decode

        losses = []
        final_outputs = []
        metrics = defaultdict(list)

        metrics = {k: Statistics(np.mean) for k in vars(self.metrics).keys()}
        for batch in tqdm(loader, "validating"):
            batch_size = batch["texts"].shape[0]
            outputs: KieOutput = model(batch)
            for i in range(batch_size):
                sample = batch[i]

                # Relation scores
                score = get_tensor_f1(outputs.relations, sample.adj).cpu().item()
                metrics["f1_relations"].append(score)

                # Classification score
                score = get_tensor_f1(outputs.classes, sample.classes).cpu().item()
                metrics["f1_classification"].append(score)

                # Extract
                sample = sample.to_numpy()
                output = outputs[i]

                # Postprocess GT
                gt = post_process(sample)

                # Postprocess PR
                sample.classes = output.classes.cpu().numpy()
                sample.adj = output.relations.cpu().numpy()
                pr = post_process(sample)

                # End to end format
                pr = prettify_sample(pr, self.model_config.classes)
                gt = prettify_sample(gt, self.model_config.classes)

                # End to end score
                score = get_e2e_f1(pr, gt)
                metrics["f1_end2end"].append(score)

                final_outputs.append((pr, gt))
            metrics["validation_loss"].append(outputs.loss.item())

        for pr, gt in random.choices(final_outputs, k=1):
            tqdm.write("PR:\t" + str(pr))
            tqdm.write("+" * 3)
            tqdm.write("GT:\t" + str(gt))
            tqdm.write("-" * 30)

        f1_end2end = metrics.pop("f1_end2end")
        if self.metrics.f1_end2end.update(f1_end2end.get()):
            self.save_model(self.model_config.best_weight_path)

        for k, v in metrics.items():
            metric = getattr(self.metrics, k)
            if isinstance(metric, Metric):
                metric.update(v.get())

        tqdm.write(pformat(vars(self.metrics)))

    def save_model(self, save_path):
        dirname = os.path.dirname(save_path)
        os.makedirs(dirname, exist_ok=True)
        torch.save(self.model.state_dict(), save_path)
        tqdm.write(f"Model saved to {save_path}")

"""
FashionMNIST classifier — the "hello GPU + MLflow" training job for the PoC.

Designed for two entry points from the same module:
  - SMUS JupyterLab notebook (interactive iteration on a small subset):
        from train import train
        train(epochs=1, subset=2000)
  - Slurm sbatch (full run):
        python -m train --epochs 10

MLflow tracking URI is taken from the MLFLOW_TRACKING_URI env var. If unset,
logs go to a local ./mlruns directory — useful for standalone DGX testing
before SMUS managed MLflow is wired up.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import mlflow
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms


DEFAULT_DATA_DIR = Path(os.environ.get("DATA_DIR", Path.home() / "data"))
DEFAULT_ARTIFACT_DIR = Path(os.environ.get("ARTIFACT_DIR", Path.home() / "models"))
DEFAULT_EXPERIMENT = os.environ.get("MLFLOW_EXPERIMENT_NAME", "smus-to-dgx")


class SmallCNN(nn.Module):
    def __init__(self, num_classes: int = 10):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 32, 3, padding=1)
        self.conv2 = nn.Conv2d(32, 64, 3, padding=1)
        self.pool = nn.MaxPool2d(2, 2)
        self.fc1 = nn.Linear(64 * 7 * 7, 128)
        self.fc2 = nn.Linear(128, num_classes)

    def forward(self, x):
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = torch.flatten(x, 1)
        x = F.relu(self.fc1(x))
        return self.fc2(x)


def _loaders(batch_size: int, data_dir: Path, subset: int | None):
    tfm = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.286,), (0.353,))])
    train_ds = datasets.FashionMNIST(str(data_dir), train=True, download=True, transform=tfm)
    val_ds = datasets.FashionMNIST(str(data_dir), train=False, download=True, transform=tfm)
    if subset:
        train_ds = Subset(train_ds, range(min(subset, len(train_ds))))
        val_ds = Subset(val_ds, range(min(max(subset // 5, 200), len(val_ds))))
    return (
        DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=2, pin_memory=True),
        DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=2, pin_memory=True),
    )


def _eval(model: nn.Module, loader: DataLoader, device: torch.device) -> tuple[float, float]:
    model.eval()
    loss_sum = 0.0
    correct = 0
    n = 0
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            logits = model(x)
            loss_sum += F.cross_entropy(logits, y, reduction="sum").item()
            correct += (logits.argmax(1) == y).sum().item()
            n += y.size(0)
    return loss_sum / n, correct / n


def train(
    epochs: int = 5,
    batch_size: int = 128,
    lr: float = 1e-3,
    subset: int | None = None,
    data_dir: Path = DEFAULT_DATA_DIR,
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    experiment: str = DEFAULT_EXPERIMENT,
    run_name: str | None = None,
) -> dict:
    """Train SmallCNN on FashionMNIST. Returns a dict of final metrics + artifact path."""
    data_dir = Path(data_dir)
    artifact_dir = Path(artifact_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment)

    train_loader, val_loader = _loaders(batch_size, data_dir, subset)
    model = SmallCNN().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)

    with mlflow.start_run(run_name=run_name) as run:
        mlflow.log_params(
            {
                "epochs": epochs,
                "batch_size": batch_size,
                "lr": lr,
                "subset": subset or 0,
                "device": str(device),
                "gpu": torch.cuda.get_device_name(0) if device.type == "cuda" else "cpu",
                "model": "SmallCNN",
                "dataset": "FashionMNIST",
            }
        )

        for epoch in range(1, epochs + 1):
            model.train()
            t0 = time.time()
            train_loss_sum = 0.0
            n = 0
            for x, y in train_loader:
                x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
                opt.zero_grad()
                logits = model(x)
                loss = F.cross_entropy(logits, y)
                loss.backward()
                opt.step()
                train_loss_sum += loss.item() * y.size(0)
                n += y.size(0)
            train_loss = train_loss_sum / n
            val_loss, val_acc = _eval(model, val_loader, device)
            dt = time.time() - t0

            mlflow.log_metrics(
                {"train_loss": train_loss, "val_loss": val_loss, "val_acc": val_acc, "epoch_sec": dt},
                step=epoch,
            )
            print(
                f"epoch {epoch:>2}/{epochs}  train_loss={train_loss:.4f}  "
                f"val_loss={val_loss:.4f}  val_acc={val_acc:.4f}  ({dt:.1f}s)"
            )

        # Write the artifact to local disk and log only its URI (data stays on-prem).
        artifact_path = artifact_dir / f"smallcnn-{run.info.run_id}.pt"
        torch.save(model.state_dict(), artifact_path)
        mlflow.set_tag("artifact_uri_onprem", f"file://{artifact_path}")
        mlflow.set_tag("hostname", os.uname().nodename)

        return {
            "run_id": run.info.run_id,
            "val_loss": val_loss,
            "val_acc": val_acc,
            "artifact_path": str(artifact_path),
        }


def _cli():
    p = argparse.ArgumentParser(description="Train SmallCNN on FashionMNIST")
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--batch-size", type=int, default=128)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--subset", type=int, default=None, help="limit training set size (for dev iteration)")
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    p.add_argument("--experiment", default=DEFAULT_EXPERIMENT)
    p.add_argument("--run-name", default=None)
    args = p.parse_args()
    result = train(**vars(args))
    print("DONE", result)


if __name__ == "__main__":
    _cli()

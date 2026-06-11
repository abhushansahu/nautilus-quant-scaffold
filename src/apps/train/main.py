"""Training CLI: `tbt-train mlp --seed 0 --steps 500`. Requires the `models` dep group."""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(help="Train models offline and serialize artifacts.")


@app.callback()
def main() -> None:
    """Offline model training."""


@app.command()
def mlp(
    seed: int = typer.Option(0, help="Random seed (training is deterministic per seed)"),
    steps: int = typer.Option(500, help="Number of optimization steps"),
    num_bars: int = typer.Option(5000, help="Synthetic bars in the training set"),
    output: Path = typer.Option(Path("artifacts/mlp_signal"), help="Artifact directory"),
) -> None:
    from models.training.train_mlp import train  # deferred: requires jax

    result = train(seed=seed, num_steps=steps, num_bars=num_bars, artifact_dir=output)
    typer.echo(f"Trained on {result.n_samples} samples; final loss {result.final_loss:.6f}")
    typer.echo(f"Artifact: {result.artifact_dir}")


if __name__ == "__main__":
    app()

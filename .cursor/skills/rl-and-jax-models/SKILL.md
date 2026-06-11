---
name: rl-and-jax-models
description: RL and JAX Model Development
When to use:
  - Implementing or modifying JAX models used for signals.
  - Implementing or updating RL training loops or environments.
---

Instructions for the skill go here. Provide relative paths to other resources in the skill directory as needed.

Goals:
  - Keep training code reproducible and deterministic.
  - Keep model inference easy to plug into strategies.

Workflow:
1. Clearly separate:
   - Feature extraction (from data to arrays).
   - Model architecture (JAX/Flax or pure JAX).
   - Training loops and RL algorithms.
   - Inference wrapper used by strategies.
2. When changing model architectures:
   - Keep the input/output contract of the inference wrapper stable when possible.
   - Add tests for:
     - Shape and dtype of inputs and outputs.
     - Basic sanity checks (e.g., outputs within expected ranges).
3. Ensure training scripts:
   - Use seeded randomness.
   - Save model parameters and training metadata to disk.
4. For integration with strategies:
   - Implement a small adapter that:
     - Receives state/features from the strategy.
     - Calls the model.
     - Translates model outputs into decisions consistent with project conventions.
5. Avoid running heavyweight training in live trading environments; handle that offline and deploy only inference artifacts.
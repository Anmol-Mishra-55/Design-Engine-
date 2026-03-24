import json
import os

import torch
from app.opt_rl.env_spec import SpecEditEnv

try:
    from stable_baselines3 import PPO
    from stable_baselines3.common.env_util import make_vec_env

    SB3_AVAILABLE = True
except ImportError:
    SB3_AVAILABLE = False
    PPO = None
    make_vec_env = None
    # Silently skip - this is optional for RL training


def load_base_spec(path="seed_spec.json"):
    if os.path.exists(path):
        return json.load(open(path))
    return {
        "objects": [{"id": "floor_1", "type": "floor", "material": "wood"}],
        "scene": {},
    }


def train_opt_ppo(steps=200_000, n_envs=4, **kwargs):
    if not SB3_AVAILABLE:
        raise ImportError("stable-baselines3 not available. Install with: pip install stable-baselines3")

    base = load_base_spec()

    # Use CPU for PPO as recommended for MLP policies
    device = "cpu"

    def _make():
        return SpecEditEnv(base_spec=base, device=device)

    env = make_vec_env(_make, n_envs=n_envs)

    # Extract training parameters from kwargs
    learning_rate = kwargs.get("learning_rate", 3e-4)
    batch_size = kwargs.get("batch_size", 2048)
    n_epochs = kwargs.get("n_epochs", 10)
    gamma = kwargs.get("gamma", 0.99)
    gae_lambda = kwargs.get("gae_lambda", 0.95)
    clip_range = kwargs.get("clip_range", 0.2)

    # Ensure batch_size <= n_steps for PPO
    n_steps = 512
    if batch_size > n_steps:
        batch_size = n_steps

    model = PPO(
        "MlpPolicy",
        env,
        verbose=1,
        n_steps=n_steps,
        batch_size=batch_size,
        learning_rate=learning_rate,
        n_epochs=n_epochs,
        gamma=gamma,
        gae_lambda=gae_lambda,
        clip_range=clip_range,
        device=device,
    )

    model.learn(total_timesteps=steps)
    os.makedirs("models_ckpt/opt_ppo", exist_ok=True)
    out = "models_ckpt/opt_ppo/policy.zip"
    model.save(out)
    return out

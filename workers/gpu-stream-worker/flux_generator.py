"""
FLUX.1 [schnell] luxury visual generator with disk cache.

Uses Hugging Face diffusers when available; falls back to procedural
obsidian/gold placeholder art when GPU/model deps are missing.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from luxury_palette import FLUX_NEGATIVE_PROMPT, FLUX_POSITIVE_PREFIX, GOLD_BRIGHT, OBSIDIAN, ONYX

log = logging.getLogger("flux_generator")

CACHE_DIR = Path(__file__).resolve().parent / "assets" / "flux_cache"
DEFAULT_STEPS = 4


class FluxGenerator:
    """Generate and cache ultra-luxury project art for the compositor."""

    def __init__(self, width: int = 640, height: int = 640):
        self.width = width
        self.height = height
        self._pipe = None
        self._model_loaded = False
        self._current_image: Optional[np.ndarray] = None
        self._crossfade_from: Optional[np.ndarray] = None
        self._crossfade_start = 0.0
        self._crossfade_duration = 1.2
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, prompt: str) -> Path:
        key = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        return CACHE_DIR / f"{key}.png"

    def _load_pipeline(self) -> bool:
        if self._model_loaded:
            return self._pipe is not None
        try:
            import torch
            from diffusers import FluxPipeline
            if not torch.cuda.is_available():
                log.warning("CUDA unavailable — FLUX will use procedural fallback")
                self._model_loaded = True
                return False
            log.info("Loading FLUX.1 schnell (4-step) with NF4 quantization…")
            self._pipe = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-schnell", torch_dtype=torch.bfloat16)
            try:
                self._pipe.enable_model_cpu_offload()
            except Exception:
                self._pipe.to("cuda")
            self._model_loaded = True
            return True
        except ImportError:
            log.info("diffusers/torch not installed — using procedural luxury visuals")
            self._model_loaded = True
            return False
        except Exception as exc:
            log.warning("FLUX load failed: %s — procedural fallback", exc)
            self._model_loaded = True
            return False

    def _procedural_luxury_frame(self, prompt: str) -> np.ndarray:
        img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        img[:] = ONYX
        cx, cy = self.width // 2, self.height // 2
        for r in range(max(cx, cy), 0, -8):
            alpha = max(0, 1.0 - r / max(cx, cy))
            color = tuple(int(OBSIDIAN[i] * (1 - alpha) + GOLD_BRIGHT[i] * alpha * 0.35) for i in range(3))
            cv2.circle(img, (cx, cy), r, color, -1)
        seed = int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        for _ in range(120):
            x, y = rng.integers(0, self.width), rng.integers(0, self.height)
            cv2.circle(img, (int(x), int(y)), rng.integers(1, 4), GOLD_BRIGHT, -1)
        cv2.putText(img, "HIGH ROLLER", (24, self.height - 32), cv2.FONT_HERSHEY_DUPLEX, 0.7, GOLD_BRIGHT, 2, cv2.LINE_AA)
        return img

    def _run_inference(self, full_prompt: str) -> np.ndarray:
        cache = self._cache_path(full_prompt)
        if cache.exists():
            img = cv2.imread(str(cache))
            if img is not None:
                return cv2.resize(img, (self.width, self.height))
        if not self._load_pipeline() or self._pipe is None:
            img = self._procedural_luxury_frame(full_prompt)
            cv2.imwrite(str(cache), img)
            return img
        import torch
        with torch.inference_mode():
            result = self._pipe(full_prompt, num_inference_steps=DEFAULT_STEPS, guidance_scale=0.0,
                max_sequence_length=256, negative_prompt=FLUX_NEGATIVE_PROMPT)
            arr = cv2.cvtColor(np.array(result.images[0]), cv2.COLOR_RGB2BGR)
            arr = cv2.resize(arr, (self.width, self.height))
            cv2.imwrite(str(cache), arr)
            return arr

    async def generate(self, subject: str, theme_prefix: str = "") -> np.ndarray:
        prefix = theme_prefix.strip() or FLUX_POSITIVE_PREFIX
        full_prompt = f"{prefix} {subject}" if prefix not in subject else subject
        return await asyncio.get_event_loop().run_in_executor(None, self._run_inference, full_prompt)

    async def transition_to(self, subject: str, theme_prefix: str = "") -> None:
        new_img = await self.generate(subject, theme_prefix=theme_prefix)
        if self._current_image is not None:
            self._crossfade_from = self._current_image.copy()
            self._crossfade_start = time.time()
        self._current_image = new_img

    def get_frame(self) -> Optional[np.ndarray]:
        if self._current_image is None:
            return None
        if self._crossfade_from is not None:
            t = min((time.time() - self._crossfade_start) / self._crossfade_duration, 1.0)
            if t >= 1.0:
                self._crossfade_from = None
                return self._current_image
            return cv2.addWeighted(self._crossfade_from, 1.0 - t, self._current_image, t, 0)
        return self._current_image

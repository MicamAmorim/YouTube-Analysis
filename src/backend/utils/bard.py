"""Google Generative AI helper (Gemini / PaLM‑2 family)

⬤ Public coroutine: **rewrite_text(text, prompt, …)**
   – Keeps the same signature we used before, but is now more defensive:
     * Default model is ``models/text-bison-001`` (widely available).
     * If the requested model returns *404 Not Found*, we automatically
       fall back to the first model that supports *generateContent*.

⬤ Environment variable: looks for ``GOOGLE_BARD_KEY`` first (for
  backward‑compatibility) and then ``GOOGLE_API_KEY``.

Usage example
-------------
```python
from backend.utils.bard_client import rewrite_text  # name kept for retro‑compat

novo = await rewrite_text(
    text="O pequeno Pokémon foi à floresta…",
    prompt="Re‑escreva o texto abaixo em tom épico, em até 3 frases."
)
```
"""
from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

import google.generativeai as genai
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Default config & helpers
# ---------------------------------------------------------------------------

_DEFAULT_CFG: Dict[str, Any] = {
    "temperature": 0.7,
    "max_output_tokens": 4096,
}

# model ID more broadly available than gemini‑pro (works for v1beta* accounts)
_DEFAULT_MODEL = "models/gemini-2.0-flash"

_executor = ThreadPoolExecutor(max_workers=4)


class GeminiError(RuntimeError):
    """Any error raised while talking to Generative AI."""


async def rewrite_text(
    text: str,
    prompt: str,
    *,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
    model_name: str = _DEFAULT_MODEL,
) -> str:
    """Rewrite *text* according to *prompt* using Google Generative AI.

    If *model_name* is not available for the account, the function tries
    to discover an alternative that supports *generateContent* and
    re‑issues the request automatically.
    """

    load_dotenv()
    api_key = os.getenv("GOOGLE_BARD_KEY") or os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_BARD_KEY/GOOGLE_API_KEY não encontrado em .env – adicione sua chave."  # noqa: E501
        )

    genai.configure(api_key=api_key)

    cfg = _DEFAULT_CFG.copy()
    if temperature is not None:
        cfg["temperature"] = temperature
    if max_output_tokens is not None:
        cfg["max_output_tokens"] = max_output_tokens

    full_prompt = f"{prompt}\n\nTexto:\n{text}"

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor, _sync_call, model_name, full_prompt, cfg
    )


# ---------------------------------------------------------------------------
# Blocking part – executed in thread pool
# ---------------------------------------------------------------------------

def _sync_call(model_name: str, full_prompt: str, cfg: Dict[str, Any]) -> str:
    try:
        return _invoke_model(model_name, full_prompt, cfg)
    except Exception as exc:  # noqa: BLE001
        # Handle 404 or missing method gracefully
        if "not found" in str(exc).lower() or "is not supported" in str(exc).lower():
            # Try to find first available model with generateContent
            alt = _find_first_supported()
            if alt:
                return _invoke_model(alt, full_prompt, cfg)
        raise GeminiError(f"Erro ao chamar Generative AI: {exc}") from exc


def _invoke_model(model_name: str, full_prompt: str, cfg: Dict[str, Any]) -> str:
    model = genai.GenerativeModel(model_name)
    resp = model.generate_content(full_prompt, generation_config=cfg)

    if getattr(resp, "text", None):
        return resp.text

    feedback = getattr(resp, "prompt_feedback", None)
    raise GeminiError(
        "Modelo não retornou texto. Feedback: "
        f"{feedback if feedback is not None else resp}"
    )


def _find_first_supported() -> str | None:
    """Return first model that supports generateContent or None."""
    try:
        models: List[Any] = genai.list_models()
    except Exception:
        return None

    for m in models:
        if "generateContent" in getattr(m, "supported_generation_methods", []):
            return m.name  # type: ignore[attr-defined]
    return None


# ---------------------------------------------------------------------------
# Debug usage – python bard_client.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    sample_prompt = "Reescreva e aumente o texto em tom épico."
    sample_text = (
        "O pequeno Pokémon foi à floresta e encontrou um aliado poderoso. "
        "Juntos dominaram a natureza e jamais se esqueceram da força da amizade."
    )

    async def _demo():
        print(">>> Chamando Google Generative AI…")
        try:
            print(await rewrite_text(sample_text, sample_prompt))
        except Exception as e:  # pragma: no cover
            print("Falhou:", e)

    asyncio.run(_demo())

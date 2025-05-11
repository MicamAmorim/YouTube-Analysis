"""
youtube-analysis.py
--------------------

• Recebe uma *lista de links* do YouTube;  
• Extrai a transcrição de cada vídeo (por padrão em PT, com fallback para EN);  
• Faz **apenas uma** chamada ao Google Generative AI (Gemini/Bard) para cada
  transcrição usando o *prompt* solicitado, **exigindo** que o modelo devolva
  um JSON;  
• Constrói um CSV `analise_pregacoes.csv` com as colunas:

    link | centralidade de cristo | salvação pela graça mediante a fé  
    | chamado ao arrependimento e discipulado | proclamação do reino de Deus  
    | autoridade das Escrituras | transcrição

• Aguarda **5 s** entre requisições ao Bard para evitar sobre-carga.

Dependências:

```bash
pip install youtube_transcript_api google-generativeai python-dotenv pandas
```

Coloque a sua chave API na raiz em `.env`:

```dotenv
GOOGLE_BARD_KEY=SEU_TOKEN_AQUI
```
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import pandas as pd
from dotenv import load_dotenv
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    NoTranscriptFound,
    TranscriptsDisabled,
)

#  cliente Bard (mesmo módulo que você enviou)
from src.backend.utils.bard import rewrite_text  # mantém compatibilidade

_PROMPT = """
Critique a pregação a seguir avaliando de acordo com os seguintes critérios:

• centralidade de Cristo
• salvação pela graça mediante a fé
• chamado ao arrependimento e ao discipulado
• proclamação do Reino de Deus
• autoridade das Escrituras

=> Responda APENAS com um objeto JSON contendo EXACTAMENTE estas chaves:
   centralidade_de_cristo
   salvacao_pela_graca_mediante_a_fe
   chamado_ao_arrepentimento_e_discipulado
   proclamacao_do_reino_de_deus
   autoridade_das_escrituras
   transcricao_corrigida

Para cada critério, responda “Sim”, “Não” ou “Parcialmente”.
Use uma curta justificativa entre parênteses após o valor, se necessário.
Em transcricao_corrigida devolva a transcrição revisada (pontuação,
acentos e erros comuns de reconhecimento corrigidos).
"""


def _extract_video_id(url: str) -> Optional[str]:
    parsed = urlparse(url)
    if parsed.hostname in {"www.youtube.com", "youtube.com"}:
        return parse_qs(parsed.query).get("v", [None])[0]
    if parsed.hostname == "youtu.be":
        return parsed.path.lstrip("/")
    return None


def fetch_transcript(url: str, languages: List[str] | None = None) -> Optional[str]:
    languages = languages or ["pt"]
    vid = _extract_video_id(url)
    if not vid:
        print(f"[!] URL inválida → {url}")
        return None
    for lang in languages:
        try:
            lines = YouTubeTranscriptApi.get_transcript(vid, languages=[lang])
            return "\n".join(chunk["text"] for chunk in lines)
        except (NoTranscriptFound, TranscriptsDisabled):
            continue
    print(f"[!] Sem transcrição disponível → {url}")
    return None

def _normalize(text: str) -> str:
    """Remove [Música]/[Risos] etc., múltiplos espaços e quebras de linha."""
    cleaned = re.sub(r"\[[^\]]*\]", " ", text)  # remove colchetes
    return re.sub(r"\s+", " ", cleaned).strip()

def _to_json(text: str) -> dict:
    """
    Remove blocos ```...``` ou texto fora de {...} e faz json.loads().
    """
    # pega só o que está entre o 1º { e o último }
    m = re.search(r'{.*}', text, flags=re.S)
    if not m:
        raise ValueError("Nenhum objeto JSON encontrado")
    clean = m.group(0)
    return json.loads(clean)

async def _analyse_one(url: str) -> Optional[Dict[str, Any]]:
    text = fetch_transcript(url)
    text = _normalize(text)
    if not text:
        print(f"[!] Sem transcrição disponível → {url}")
        return None
    else:
        print(f"[✔] Transcrição obtida → {url}")
    try:
        raw = await rewrite_text(text=text, prompt=_PROMPT, temperature=0.3)
        #data = json.loads(raw)
        print(raw)
        data = _to_json(raw)
    except Exception as exc:
        print(f"[!] Falhou Bard → {url}\n    {exc}")
        return None
    return {
        "link": url,
        "centralidade de cristo": data.get("centralidade_de_cristo", "").strip(),
        "salvação pela graça mediante a fé": data.get(
            "salvacao_pela_graca_mediante_a_fe", ""
        ).strip(),
        "chamado ao arrependimento e discipulado": data.get(
            "chamado_ao_arrepentimento_e_discipulado", ""
        ).strip(),
        "proclamação do reino de Deus": data.get(
            "proclamacao_do_reino_de_deus", ""
        ).strip(),
        "autoridade das Escrituras": data.get(
            "autoridade_das_escrituras", ""
        ).strip(),
        "transcrição": data.get("transcricao_corrigida", "").strip(),
    }


async def analyse_videos(urls: List[str]) -> None:
    rows: List[Dict[str, Any]] = []
    for idx, link in enumerate(urls, start=1):
        print(f"({idx}/{len(urls)}) → {link}")
        row = await _analyse_one(link)
        if row:
            rows.append(row)
        await asyncio.sleep(5)
    if not rows:
        print("[x] Nada a salvar.")
        return
    df = pd.DataFrame(rows)
    out = Path("analise_pregacoes.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[✔] CSV salvo em {out.resolve()}")


if __name__ == "__main__":
    load_dotenv()
    LINKS = [
        "https://www.youtube.com/watch?v=CeuqAIsrVpY",
        "https://www.youtube.com/watch?v=HZvTW4hlSVQ"
    ]
    asyncio.run(analyse_videos(LINKS))

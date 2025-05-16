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
import backoff

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

@backoff.on_exception(backoff.expo, Exception, max_time=60)
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
    try:
        # Tenta extrair a transcrição
        text = fetch_transcript(url)
        if not text:
            print(f"[!] Sem transcrição disponível → {url}")
            return None

        # Limpa o texto
        text = _normalize(text)
        print(f"[✔] Transcrição obtida → {url}")

        # Envia para o Bard
        try:
            raw = await rewrite_text(text=text, prompt=_PROMPT, temperature=0.3)
            data = _to_json(raw)
        except Exception as exc:
            print(f"[!] Falhou Bard → {url}\n    {exc}")
            return None

        # Formata os dados para o CSV
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

    except Exception as exc:
        # Garante que qualquer erro seja logado sem interromper o loop
        print(f"[!] Erro inesperado ao processar → {url}\n    {exc}")
        return None


async def analyse_videos(urls: List[str]) -> None:
    rows: List[Dict[str, Any]] = []
    for idx, link in enumerate(urls, start=1):
        print(f"({idx}/{len(urls)}) → {link}")
        row = await _analyse_one(link)
        if row:
            rows.append(row)
        await asyncio.sleep(10)
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
    "https://youtu.be/CeuqAIsrVpY?si=tNmQhZs8WuIffPfc",
    "https://youtu.be/HZvTW4hlSVQ?si=eh2cf4k-0A0L6XWg",
    "https://youtu.be/esh3dsqnOCc?si=1FySTpSPxvyeftUn",
    "https://youtu.be/gBsfbhEZbSc?si=sWvPzfGKKRurneY2",
    "https://youtu.be/aWHB2VOJRFU?si=UyXeFZ7g0WMfEGtj",
    "https://youtu.be/RNP510cFz_o?si=YmV33w_iSUhahaeQ",
    "https://youtu.be/PGFgCwN0dls?si=zIloq_wXemQNJQAV",
    "https://youtu.be/1z4awMCsX7Q?si=nnrS2eIE1Aqq296-",
    "https://youtu.be/582Wt63bJkw?si=mDOm2InKec8swc9x",
    "https://youtu.be/4FyFrUcsXUw?si=xvRH5xoKr10eEtPQ",
    "https://youtu.be/IFTZIoEdJTU?si=cpf94tauZ2t4UVjk",
    "https://youtu.be/KYUJTz-EAzk?si=nOwM4vLYZJx6Xh0Z",
    "https://youtu.be/hYRmXkT9G58?si=M-iENKxIjEdgxcA2",
    "https://youtu.be/L9Jis0mM3Kc?si=fUDZrLoVfgxgXBnh",
    "https://youtu.be/ufNVVX0sLso?si=w3AOilDKyWdCSeq0",
    "https://youtu.be/k8bIuDAlNF0?si=6eCwFG5PX2V5Q246",
    "https://youtu.be/sKka4iIyFpU?si=rKGPh7r08I_Bo5i-",
    "https://youtu.be/9XCLjuNutlU?si=la3-4F7wwGjgQOI0",
    "https://youtu.be/YL3LJfcaBzE?si=aS4OvbD2o_Tgx1Hf",
    "https://youtu.be/IQjlH-P1k_U?si=FUuj-J4Dqmztz76P",
    "https://youtu.be/upRoAD8a6zw?si=iLs6zsOAy_iypvjF",
    "https://youtu.be/4gG9PLtTG-w?si=OuBO8tzd86EXocka",
    "https://youtu.be/XTAG62Lt_5M?si=E-cOpsZ9txD6Q7Rc",
    "https://youtu.be/8nZyHwgpG3M?si=2rHaRFaLd0kjh4Qg",
    "https://youtu.be/-259SkK8WF0?si=rfWLJQC6UUZBTc8g"
]
    asyncio.run(analyse_videos(LINKS))

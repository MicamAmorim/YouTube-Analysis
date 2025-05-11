# YouTube‑Analysis

Script **enxuto** em Python para **coletar transcrições de vídeos do YouTube**
e analisá‑las via **Google Generative AI (Gemini / Bard)**.  
Tudo é controlado por um **_prompt_** definido no código; o modelo responde em
JSON, e cada chave vira uma coluna no CSV final.

> ⚙️ Use para *qualquer* pesquisa textual: resumo, extração de tópicos,
análise de sentimentos, checklist de critérios, etc.  Basta editar o
`_PROMPT`.

---

## Como funciona

1. Edite a lista `LINKS` no topo de `main.py` (pode renomear o
   arquivo se desejar).
2. Ajuste a constante `_PROMPT` com a tarefa desejada e instrua **claramente**
   o modelo a responder **somente um objeto JSON**.
3. Execute o script – ele:
   * extrai legendas automáticas ou manuais (PT → EN fallback);
   * limpa ruídos (`[Música]`, quebras de linha, etc.);
   * envia ao Gemini/Bard (1 chamada por vídeo); aguarda 5 s para não exceder
     quota;
   * grava `youtube_analysis.csv` (ou nome que você definir) com o *link* e as
     colunas derivadas do JSON + a transcrição revisada (quando presente).

---

## Instalação

```bash
# clone o projeto
$ git clone https://github.com/seu_usuario/youtube-analysis.git
$ cd youtube-analysis

# ambiente virtual (opcional)
$ python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate

# dependências mínimas
(venv)$ pip install youtube-transcript-api google-generativeai python-dotenv pandas
```

Crie um arquivo **`.env`** com sua chave da Google Generative AI:
```dotenv
GOOGLE_BARD_KEY=SEU_TOKEN_AQUI
```

---

## Executando

```bash
(venv)$ python main.py
```

*O nome do script não importa; mantenha a mesma estrutura interna.*

O CSV será gerado na pasta corrente.  Cada coluna corresponde às chaves do
JSON devolvido pelo modelo. Exemplo genérico:

| link | resumo | polaridade | entidades |
|------|--------|-----------|-----------|
| https://youtu.be/… | "Vídeo discute…" | 0.75 | ["YouTube", "Python"] |

---

## Personalizando

| O que mudar | Onde | Notas |
|-------------|------|-------|
| **Prompt** | Constante `_PROMPT` | Instrua: *"Responda apenas JSON {…}"*. |
| **Nome do CSV** | Variável `out` no final de `analyse_videos()` | Por padrão `youtube_analysis.csv`. |
| **Idiomas preferidos** | Lista `languages` em `fetch_transcript()` | Ordem de tentativa. |
| **Delay entre requisições** | `asyncio.sleep(5)` | Ajuste conforme sua quota. |
| **Chaves adicionais** | Basta o modelo incluí‑las no JSON | Aparecerão como novas colunas. |

---

## Principais funções

* `_extract_video_id(url)` → ID do vídeo.
* `fetch_transcript(url, languages)` → legenda limpa.
* `_normalize(text)` → remove tags / colapsa espaços.
* `_to_json(text)` → extrai o primeiro objeto JSON do retorno do Gemini.
* `_analyse_one(url)` → pipeline completo para 1 vídeo.
* `analyse_videos(urls)` → itera sobre a lista e salva o CSV.

> Você pode importar essas funções em outro projeto e compor um fluxo próprio.

---

## Licença

MIT © 2025 Seu Nome — aproveite e compartilhe melhorias 😊

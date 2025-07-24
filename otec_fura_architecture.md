# Architektura Jarvik + Otec Fura: Detailní popis funkcí modulů

## 🏢 Servery a jejich role

### Server 1: Jarvik (Primární AI asistent)

* **HW**: GPU, 1 CPU, 64 GB RAM, 2 TB SSD
* **Moduly**:

  * **Jarvik Core** (Flask / FastAPI backend)
  * **Ollama / vLLM**: Lokální LLM (LLaMA 3, Dolphin, OpenHermes)
  * **RAG vrstva**: dotazy na paměť + znalosti
  * **Paměť**: public.jsonl / private.jsonl
  * **Knowledge Base**: složka `knowledge/` s texty
  * **Connectors**: IMAP, kalendáře, soubory
  * **DevLab**: Generování kódu, Codex

### Server 2: Otec Fura (Znalostní backend)

* **HW**: 2 CPU, 144 GB RAM, HDD / SSD pro indexaci
* **Moduly**:

  * **Webový crawler**: sběr dat z webu (např. beautifulsoup4 + requests)
  * **Embedder**: all-MiniLM-L6-v2 (sentence-transformers)
  * **Indexer**: FAISS indexy (tematický, doménový, timestamp)
  * **API**: odpovídá na dotazy z Jarvika přes HTTP
  * **Knowledge store**: synchronizované knihovny v textové formě

## 🤖 AI komponenty

### Jarvik (vLLM / Ollama API)

* **Modely**:

  * Meta-LLaMA-3-8B-Instruct
  * OpenHermes 2.5 (Mistral)
  * DeepSeek Coder 6.7B
* **Dotazová logika**:

  1. Vstup: dotaz uživatele (přes UI nebo API)
  2. Předzpracování: kontrola klíčových slov, režimů (soukromý, öffentlich)
  3. Paměť: dotaz na JSONL historii (např. GPT memory format)
  4. Knowledge: RAG vyhledávání v textových souborech
  5. Odeslání dotazu na model (OpenAI API / Ollama / vLLM)
  6. Výstup: odpověď + uložení do paměti

### Otec Fura

* **Zdroje dat**:

  * ručně určené domény (seznam .txt)
  * automatické tématické vyhledávání
* **Moduly**:

  * **crawler.py**: hloubkový sběr, ořez reklamy, ukládání do raw/
  * **embedder.py**: vektorová reprezentace (sentence-transformer)
  * **indexer.py**: staví FAISS index, tříděný podle témat
  * **query.py**: příjem dotazu, vrácení nejrelevantnějších pasáží
* **Fungování**:

  1. Jarvik pošle dotaz
  2. API server otce FURY najde vektor dotazu
  3. Vyhledá nejbližší pasáže v indexu
  4. Vrátí větší kontext pro odpověď
  5. Jarvik doplní prompt a odpoví

## 📊 Datová struktura

* `memory/<user>/private.jsonl` – osobní paměť
* `memory/public.jsonl` – veřejná znalost
* `knowledge/` – .txt soubory v kategoriích
* `web_corpus/` – strojově sesbírané webové texty
* `indexes/` – FAISS vektorové indexy
* `api/` – rozhraní pro dotaz na znalosti z Furů

## 🚦 Komunikace

* Jarvik → Otec Fura: `GET /query?q=...`
* Fura → Jarvik: JSON s kontextem (text, URL, timestamp)
* Fura může běžet paralelně na jiném portu / serveru

## 🔹 Shrnutí

* Jarvik: myslí, chatuje, generuje
* Fura: zná věci, indexuje, obohacuje odpovědi
* AI: LLM odpovídá na dotazy s vektorovým kontextem z paměti + webu
* Komunikace oddělena – znalosti můžou různě růst nezávisle

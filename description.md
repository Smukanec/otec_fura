Běží zde:

Znalostní databáze (knowledge/)

Paměť (memory/)

Crawler (prohledávání webu podle témat)

Embedder (např. all-MiniLM)

FAISS indexer

REST API server (např. FastAPI): /get_context

Funkce:

Vyhledávání odpovědí v offline znalostech i web indexech

Správa znalostní knihovny

Poskytuje odpovědi na dotazy od Jarvika

3. ⚙️ Proces dotazování (schéma)

Uživatel položí dotaz v UI Jarvika

Jarvik zkontroluje modelovou odpověď (např. LLaMA3)

Současně odešle dotaz na server 2 (Otec Fura):

POST /get_context
{
  "query": "Jak funguje transformer?"
}

Otec Fura vyhledá v paměti, knowledge, nebo FAISS indexu

Vrátí nejrelevantnější kontext

Jarvik doplní odpověď s přidaným kontextem a odešle uživateli

4. 📂 Složky na serveru 2 (Fura)

/knowledge         # Tematicky členěné TXT/PDF soubory
/memory            # Veřejná + soukromá paměť
/embeddings        # .npy embedovaná data
/indexes           # FAISS indexy
/api/main.py       # FastAPI server
/crawler.py        # Hloubkový crawler
/embedder.py       # MiniLM encoder
/indexer.py        # FAISS builder + retriever

5. 🤸🏻 Možné rozšíření

Tagging a klasifikace obsahu

UI pro správu znalostí

Detekce duplicity věd a obsahu

Monitoring zdrojů + scheduler

Podpora pro soukromé vs. úplně anonymní znalosti

6. ⚡ Příklad odpovědi z Otce Fury

{
  "context": "Transformer modely pracují s pozorností (attention)...",
  "source": "knowledge/ml_transformers.txt"
}


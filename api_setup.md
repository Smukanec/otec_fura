Technická specifikace API „Otec Fura“
Přehled
Služba je postavena na FastAPI a implicitně naslouchá na portu 8090.
Veškeré chráněné operace používají API klíč předaný v hlavičce Authorization: Bearer <api_key>; middleware kontroluje platnost i stav „approved“ uživatele.

Autentizační a uživatelské endpointy
Metoda & URL	Vstup	Odpověď	Poznámky
POST /auth/register	{"username": str, "password": str, "email": str}	{"message": "..."} 	Vytvoří uživatele se stavem approved=False. Chyba 400 při duplicitním jménu.
POST /auth/token	{"username": str, "password": str}	{"api_key": str}	Vrací API klíč pouze schváleným uživatelům; 401/403 při chybě jména/hesla nebo neodsouhlaseném účtu.
GET /auth/me	– (pouze hlavička Authorization)	{"username": str, "email": str, "approved": bool}	Slouží k ověření API klíče.
| GET /user | – (vyžaduje API klíč) | {"username": str, "email": str, "api_key": str, "approved": bool, "created_at": str} | Vrací informace o právě přihlášeném uživateli. |

Práce se znalostmi a pamětí
Modely požadavků
AddNote: {"title": str, "content": str, "tags": [str]}

SearchReq: {"query": str, "top_k": int=5}

CrawlReq: {"url": str?, "raw_text": str?, "title": str?, "tags": [str]?}

Endpoints
Metoda & URL	Vstup	Odpověď	Popis
POST /knowledge/add	AddNote	{"ok": True, "id": str, "title": str, "chunks": int}	Uloží ručně zadaný text do znalostní databáze (FAISS + metadata).
POST /admin/reindex_knowledge	–	{"ok": True, "docs": int, "chunks": int}	Provede kompletní rebuild: smaže uložené dokumenty i vektory a znovu projde soubory ve složce knowledge/
POST /knowledge/search	SearchReq	{"results": [...]}	Vyhledá podobné úryvky v indexu. Každý výsledek obsahuje title, source, tags, score, snippet.
POST /crawl	CrawlReq	- Pro raw_text: {"ok": True, "mode": "raw_text", "id": str, "title": str, "chunks": int} - Pro url: {"ok": True, "mode": "url", "id": str, "title": str, "chunks": int}	Přidá do znalostní báze buď zadaný text, nebo stáhne obsah z URL a zaindexuje jej. Chybí-li oboje, vrací 400.
POST /get_context	{"query": str, "user": str=\"anonymous\", "remember": bool=False}	{"memory": [...], "knowledge": [...], "embedding": [...]}	Vrací kontext z paměti i znalostí. Pokud remember=True, dotaz se uloží do privátní paměti uživatele.
POST /crawl (alternativní router)	{"url": str}	{"status": "OK", "chars": int}	Jednoduché stažení URL, vytvoření embeddingu a uložení do knowledge/web_index.json. Chyby pro chybějící URL nebo neúspěšné stažení.
Tok autentizovaného dotazu
Klient získá API klíč (registrace → schválení administrátorem → přihlášení).

Každý chráněný HTTP požadavek nese hlavičku Authorization: Bearer <api_key>; middleware ověří platnost a vloží uživatele do request.state.current_user pro následné handlery.

Endpoints využívají tento kontext (Depends(current_user) nebo request.state.current_user) k autorizaci.

Datové složky
knowledge/ – textové/PDF zdroje, z nichž se tvoří FAISS index.

memory/ – public.jsonl a /<uživatel>/private.jsonl pro ukládání dotazů/poznámek.

Tato specifikace poskytuje všechny informace potřebné pro implementaci klienta komunikujícího se serverem „Otec Fura“.

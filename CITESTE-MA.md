# Alertă Return Trading – varianta online (24/7)

Verifică https://www.returntrading.nl/available-stock/ la ~5 minute pe serverele GitHub
și trimite notificare pe iPhone (aplicația ntfy) când apare orice lot nou.
Merge și cu calculatorul oprit.

## Instalare (o singură dată)
1. Cont gratuit pe https://github.com (dacă nu ai).
2. Creează un repository nou: https://github.com/new
   - Nume: `alerta-return-trading`
   - **Public** (la Private, minutele gratuite nu ajung pentru verificări la 5 minute)
   - Bifează „Add a README file” → Create repository
3. În repository: **Add file → Upload files** → trage în pagină `monitor.py` și folderul `.github`
   (din acest zip, dezarhivat) → **Commit changes**.
   Dacă folderul `.github` nu se vede (e ascuns): **Add file → Create new file**, scrie numele
   `.github/workflows/alerta.yml`, lipește conținutul fișierului și dă Commit.
4. **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `NTFY_TOPIC`
   - Secret: numele canalului tău ntfy (cel din extensie, ex. `rt-alerta-xxxxxxxxxx`)
5. **Actions** → dacă cere, apasă „I understand my workflows, go ahead and enable them”
   → „Alerta Return Trading” → **Run workflow**.
   În ~1 minut primești pe iPhone „Monitorizarea online a pornit ✅”.
6. În extensia din Chrome **debifează „Trimite și pe iPhone”**, ca să nu primești fiecare alertă de două ori.

## Opțional
- Doar anumite produse (ex. doar iPhone): Settings → Secrets and variables → Actions → tab **Variables** →
  New variable `KEYWORDS` = `iphone` sau `iphone, ipad`. Fără variabilă = toate loturile.
- Caută și în descriere: variabila `SEARCH_DESC` = `true`.
- Oprire: Actions → Alerta Return Trading → „…” → Disable workflow.
- Dacă site-ul nu poate fi verificat ~1 oră, primești o singură notificare „⚠️ … nu merge”.

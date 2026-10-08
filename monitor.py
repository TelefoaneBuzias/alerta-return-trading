#!/usr/bin/env python3
"""Return Trading – alertă stoc nou (varianta online, rulează pe GitHub Actions).

Verifică https://www.returntrading.nl/available-stock/ și trimite notificare pe
telefon (aplicația ntfy) când apare un lot nou care conține cuvintele cheie.
Folosește doar biblioteca standard Python.
"""
import html as htmllib
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

PAGE_URL = "https://www.returntrading.nl/available-stock/"
STATE_FILE = os.environ.get("STATE_FILE", "state.json")
NTFY_URL = os.environ.get("NTFY_URL", "https://ntfy.sh/")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
KEYWORDS = [k.strip().lower() for k in os.environ.get("KEYWORDS", "").split(",") if k.strip()]
SEARCH_DESC = os.environ.get("SEARCH_DESC", "false").lower() in ("1", "true", "da", "yes")
FAIL_ALERT_AFTER = 12  # ~1 oră de erori la rând -> te anunță o singură dată
HTML_FILE = os.environ.get("HTML_FILE")  # doar pentru teste
TEST_PUSH = os.environ.get("TEST_PUSH", "false").lower() == "true"  # rulare manuală = test
LAST_PUSH = {}


def log(*a):
    print(*a, flush=True)


def clean(s):
    s = re.sub(r"<[^>]*>", " ", s or "")
    return re.sub(r"\s+", " ", htmllib.unescape(s)).strip()


def fetch_page():
    if HTML_FILE:
        with open(HTML_FILE, encoding="utf-8") as f:
            return f.read()
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                f"{PAGE_URL}?_={int(time.time())}",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                  "(KHTML, like Gecko) Chrome/129.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Cache-Control": "no-cache",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Nu pot accesa site-ul: {last}")


def parse_products(page):
    items = []
    for raw in re.split(r"<article\b", page, flags=re.I)[1:]:
        b = re.split(r"</article>", raw, flags=re.I)[0]
        cls = (re.search(r'class="([^"]*)"', b) or [None, ""])[1]
        if not re.search(r"\bproduct-item\b", cls):
            continue
        post_id = (re.search(r"\bpost-(\d+)", cls) or [None, None])[1]
        url = (re.search(r'<a[^>]+href="([^"]+)"', b, re.I) or [None, PAGE_URL])[1]
        title = clean((re.search(r"<h[1-6][^>]*>([\s\S]*?)</h[1-6]>", b, re.I) or [None, ""])[1])
        batch = (re.search(r"\bRT\d{3,6}\b", b) or [""])[0]
        status = (re.search(r"\bstatus-(?!publish\b)([a-z0-9-]+)", cls, re.I) or [None, ""])[1].replace("-", " ")
        if not title and not batch:
            continue
        items.append({
            "id": post_id or batch or url,
            "title": title,
            "batch": batch,
            "url": htmllib.unescape(url),
            "status": status,
            "text": clean(b)[:600],
        })
    return items


def matches(p):
    if not KEYWORDS:
        return True
    hay = (p["title"] + " " + (p["text"] if SEARCH_DESC else "")).lower()
    return any(k in hay for k in KEYWORDS)


def push(title, message, click=PAGE_URL, priority=5, tags=("bell",)):
    """Trimite pe telefon. Întoarce True dacă ntfy a confirmat primirea."""
    LAST_PUSH.clear()
    LAST_PUSH.update(time=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), title=title)
    if not NTFY_TOPIC:
        LAST_PUSH["result"] = "NETRIMIS: lipsește secretul NTFY_TOPIC"
        print("::error::Secretul NTFY_TOPIC lipsește sau e gol – notificarea NU a fost trimisă.", flush=True)
        return False
    body = json.dumps({"topic": NTFY_TOPIC, "title": title, "message": message,
                       "click": click, "priority": priority, "tags": list(tags)}).encode()
    req = urllib.request.Request(NTFY_URL, data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                LAST_PUSH["result"] = f"trimis OK ({r.status})"
                log(f"Notificare trimisă ({r.status}): {title}")
                return True
        except Exception as e:  # noqa: BLE001
            LAST_PUSH["result"] = f"EROARE: {e}"
            print(f"::warning::Trimiterea către ntfy a eșuat (încercarea {attempt + 1}): {e}", flush=True)
            time.sleep(5 * (attempt + 1))
    return False


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def main():
    state = load_state()
    first_run = state is None
    state = state or {"seen": [], "fails": 0}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        products = parse_products(fetch_page())
        if not products:
            raise RuntimeError("Nu am găsit loturi pe pagină (poate s-a schimbat site-ul).")
    except Exception as e:  # noqa: BLE001
        state["fails"] = state.get("fails", 0) + 1
        log(f"Eroare ({state['fails']} la rând): {e}")
        if state["fails"] == FAIL_ALERT_AFTER:
            push("⚠️ Alerta Return Trading nu merge", f"Nu pot verifica site-ul de ceva timp: {e}",
                 priority=3, tags=("warning",))
        save_state(state)
        return 0

    if state.get("fails", 0) >= FAIL_ALERT_AFTER:
        push("✅ Alerta Return Trading merge din nou", "Site-ul se poate verifica iar.", priority=2, tags=("ok",))
    state["fails"] = 0

    seen = set(state.get("seen", []))
    fresh = [] if first_run else [p for p in products if p["id"] not in seen and matches(p)]
    log(f"{len(products)} loturi, {sum(map(matches, products))} cu {KEYWORDS}, noi: {len(fresh)}")

    if TEST_PUSH:
        push("Test Return Trading 👍",
             f"Notificările de pe GitHub ajung pe telefon. Acum sunt {len(products)} loturi pe site.",
             priority=4, tags=("white_check_mark",))

    sent_ok = True
    if first_run:
        n = sum(map(matches, products))
        filt = f"Filtru: „{', '.join(KEYWORDS)}” ({n} din {len(products)} loturi). " if KEYWORDS \
            else f"Acum sunt {len(products)} loturi pe site. "
        push("Monitorizarea online a pornit ✅",
             filt + "Te anunț la orice lot nou" + (" care se potrivește" if KEYWORDS else "") +
             " – și cu calculatorul oprit.", priority=3, tags=("white_check_mark",))
    elif len(fresh) == 1:
        p = fresh[0]
        sent_ok = push(f"Lot nou {p['batch']} – Return Trading".replace("  ", " "), p["title"], click=p["url"])
    elif fresh:
        sent_ok = push(f"{len(fresh)} loturi noi – Return Trading",
             "\n".join(f"{p['batch']}: {p['title']}" if p["batch"] else p["title"] for p in fresh))

    # dacă trimiterea a eșuat, nu marchez loturile noi ca văzute -> reîncerc la rularea următoare
    retry = {p["id"] for p in fresh} if not sent_ok else set()
    state["seen"] = (state.get("seen", []) + [p["id"] for p in products
                                               if p["id"] not in seen and p["id"] not in retry])[-1000:]
    old = state.get("ultima_notificare") or {}
    if LAST_PUSH and (old.get("title"), old.get("result")) != (LAST_PUSH["title"], LAST_PUSH["result"]):
        state["ultima_notificare"] = dict(LAST_PUSH)  # nu fac commit la fiecare rulare cu aceeași eroare
    state["canal_setat"] = bool(NTFY_TOPIC)
    # GitHub oprește programarea după 60 de zile fără activitate; o dată pe lună
    # actualizez data ca să rămână pornit.
    if state.get("heartbeat", "")[:7] != today[:7]:
        state["heartbeat"] = today
    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())

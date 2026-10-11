#!/usr/bin/env python3
"""Robot LOTTO AI AT : résultats officiels du Lotto « 6 aus 45 » (API publique des Österreichische Lotterien, lotterien.at).
- 30 derniers tirages : 6 numéros, Zusatzzahl, gain par gagnant et nombre de gagnants des 8 rangs (Quoten)
- prochain tirage (date, clôture des mises) + jackpot annoncé du 1er rang
Écrit at_results.json UNIQUEMENT si tout est cohérent (sinon : sortie en erreur, l'ancien fichier reste).
Ajoute aussi les nouveaux tirages à history.json (historique complet depuis le 07/09/1986, sans réécrire l'existant)."""
import json, urllib.request, datetime, time, os, sys
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
B = "https://www.lotterien.at/api"

def get(path, tries=4):
    for t in range(tries):
        try:
            req = urllib.request.Request(B + path, headers={"User-Agent": UA, "Accept": "application/json"})
            return json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))
        except Exception:
            if t == tries - 1: raise
            time.sleep(5 * (t + 1))

def draw(d):
    """Un tirage de l'API → format de l'app"""
    o = d["__original__"]
    nums = sorted(d["results"]["regular"]); zz = d["results"]["bonus"]
    assert len(nums) == 6 and len(set(nums + [zz])) == 7 and all(1 <= n <= 45 for n in nums + [zz]), o["drawDate"]
    pay, win = {}, {}
    for r in d.get("odds") or []:
        k = str(r["number"]); n = r.get("count") or 0
        win[k] = n
        pay[k] = float(r["value"]) if n and r.get("value") else None   # pas de gagnant (jackpot) → None
    jp = None
    if d.get("odds"):
        f = (d["odds"][0].get("forecast") or {})
        jp = f.get("jackpot")
    day = datetime.date.fromisoformat(o["drawDate"])
    return {"date": o["drawDate"], "draw": o["drawNo"], "numbers": nums, "bonus": [zz],
            "bonusDraw": day.weekday() == 4,             # Bonus-Ziehung du vendredi
            "payouts": pay or None, "winners": win or None, "jackpotCarried": jp}

def main():
    api = get("/results/lotto/30")
    draws = [draw(d) for d in api]
    draws.sort(key=lambda x: x["date"], reverse=True)
    assert len(draws) >= 20, "trop peu de tirages"
    # 8 rangs quand les Quoten sont publiées
    for x in draws:
        if x["winners"]: assert len(x["winners"]) == 8, x["date"]
    nxt = None
    try:
        j = get("/jackpot/all")["lotto"]["__original__"]
        amt = j.get("announcedFirstRankPrize", {}).get("amount", {})
        val = amt.get("value"); w = amt.get("weight")
        est = val * 1_000_000 if (val is not None and w == "BASE_CURRENCY_MILLIONS") else val
        nxt = {"date": j["drawDate"], "salesClose": j.get("endPayin"), "estimatedPrize": est,
               "jackpotCounter": j.get("announcedFirstRankPrize", {}).get("jackpotCounter")}
    except Exception as e:
        print("prochain tirage indisponible :", e, file=sys.stderr)
    out = {"lotto": draws, "next": nxt, "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")}
    new = json.dumps(out, ensure_ascii=False, indent=1)
    old = open("at_results.json").read() if os.path.exists("at_results.json") else ""
    def strip(s):
        try: d = json.loads(s); d.pop("updated", None); return d
        except Exception: return None
    if strip(old) != strip(new):
        open("at_results.json", "w").write(new); print("at_results.json mis à jour :", draws[0]["date"])
    else:
        print("aucun changement")
    # Historique : ajoute les tirages nouveaux (jamais de réécriture d'un tirage déjà présent, sauf Quoten absentes)
    if os.path.exists("history.json"):
        H = json.load(open("history.json")); idx = {h["date"]: i for i, h in enumerate(H)}; changed = False
        for x in sorted(draws, key=lambda x: x["date"]):
            h = {k: x[k] for k in ("date", "numbers", "bonus", "payouts", "winners")}
            if x["date"] not in idx:
                H.append(h); changed = True
            elif not H[idx[x["date"]]].get("winners") and x["winners"]:
                H[idx[x["date"]]] = h; changed = True
        if changed:
            H.sort(key=lambda h: h["date"]); json.dump(H, open("history.json", "w"), ensure_ascii=False, separators=(",", ":"))
            print("history.json :", len(H), "tirages")

if __name__ == "__main__":
    main()

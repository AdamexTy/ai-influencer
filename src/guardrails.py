BLOCKED = ["vaccin", "cura per", "diagnosi", "investi", "criptovalut", "scommess",
           "elezioni", "partito", "porn", "suicid", "armi", "droga", "complott"]

def check(plan, mem):
    text = (plan.get("title", "") + " " + plan.get("script", "")).lower()
    for w in BLOCKED:
        if w in text:
            return False, "parola vietata: " + w
    words = len(plan.get("script", "").split())
    if words < 50 or words > 160:
        return False, "lunghezza script non valida (%d parole)" % words
    if len(plan.get("keywords", [])) < 3:
        return False, "parole chiave insufficienti"
    old = [v["title"].lower() for v in mem.get("videos", [])]
    if plan.get("title", "").lower() in old:
        return False, "titolo duplicato"
    return True, ""

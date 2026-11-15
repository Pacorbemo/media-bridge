import sys, re, unicodedata, difflib

def norm(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

def agrupar(p):
    partes = p.split("/")
    if len(partes) > 2:
        return "/".join(partes[:2]) + "/"
    return p

palabras = norm(" ".join(sys.argv[1:])).split()
if not palabras:
    sys.exit('Uso: medios buscar "texto"')

rutas = [l.rstrip("\n") for l in sys.stdin if l.strip()]
exactos, parecidos = {}, {}
for p in rutas:
    n = norm(p)
    tokens = n.split()
    clave = agrupar(p)
    if all(w in n for w in palabras):
        exactos[clave] = exactos.get(clave, 0) + 1
        continue
    nota = 0
    for w in palabras:
        if w in n:
            nota += 1
            continue
        margen = max(2, len(w) // 4)
        mejor = max((difflib.SequenceMatcher(None, w, t).ratio() for t in tokens if abs(len(t) - len(w)) <= margen), default=0)
        if mejor < 0.8:
            break
        nota += mejor
    else:
        parecidos[p] = nota

def mostrar(clave, n):
    extra = f"  ({n} vídeos)" if clave.endswith("/") and n > 1 else ""
    print(f"  {clave}{extra}")

print(f"Buscado en {len(rutas)} vídeos del servidor")
if exactos:
    print(f"\nCoincidencias ({len(exactos)}):")
    for k in sorted(exactos)[:40]:
        mostrar(k, exactos[k])
    if len(exactos) > 40:
        print(f"  ... y {len(exactos) - 40} más; afina la búsqueda")
if parecidos:
    print(f"\nParecidos ({len(parecidos)}):")
    for k in sorted(parecidos, key=lambda k: -parecidos[k])[:15]:
        print(f"  {k}")
if not exactos and not parecidos:
    print("\nNo hay nada parecido")

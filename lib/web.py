import argparse
import hmac
import json
import secrets
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ANFITRIONES = {"127.0.0.1", "localhost", "::1"}
ACCIONES = {
    "encender": (["on"], 240),
    "apagar": (["off"], 90),
    "reescanear": (["reescanear"], 120),
}
MAXIMO_CUERPO = 4096


def registrar(texto):
    print(texto, flush=True)


def ejecutar(medios, argumentos, limite):
    try:
        r = subprocess.run(
            [medios, *argumentos],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=limite,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as e:
        parcial = e.stdout or ""
        if isinstance(parcial, bytes):
            parcial = parcial.decode("utf-8", "replace")
        return 124, f"{parcial}\nNo terminó en {limite} s"
    except OSError as e:
        return 127, f"No puedo ejecutar {medios}: {e}"
    return r.returncode, r.stdout


class Progreso:
    def __init__(self, medios, reloj=time.monotonic):
        self.medios = medios
        self.reloj = reloj
        self.cerrojo = threading.Lock()
        self.inicio = None
        self.n0 = 0
        self.total = None
        self.contando = False
        self.ultimo_intento = None

    def _contar_total(self):
        rc, salida = ejecutar(self.medios, ["_total-videos"], 180)
        with self.cerrojo:
            self.contando = False
            if self.inicio is not None and rc == 0 and salida.strip().isdigit():
                self.total = int(salida.strip())

    def calcular(self, dlna):
        with self.cerrojo:
            if not dlna.get("indexando"):
                self.inicio = None
                self.total = None
                return None
            n = dlna.get("videos") or 0
            ahora = self.reloj()
            if self.inicio is None:
                self.inicio = ahora
                self.n0 = n
                self.ultimo_intento = None
            if self.total is None and not self.contando and (
                self.ultimo_intento is None or ahora - self.ultimo_intento >= 60
            ):
                self.contando = True
                self.ultimo_intento = ahora
                threading.Thread(target=self._contar_total, daemon=True).start()
            t = ahora - self.inicio
            total = self.total
            ritmo = minutos = porcentaje = None
            if t >= 10 and n > self.n0:
                ritmo = int((n - self.n0) * 60 / t)
                if ritmo > 0 and total and total > n:
                    minutos = -(-(total - n) // ritmo)
            if total:
                porcentaje = n * 100 // total
            return {"videos": n, "total": total, "porcentaje": porcentaje, "ritmo": ritmo, "minutos": minutos}


class Qr:
    def __init__(self):
        self.cerrojo = threading.Lock()
        self.url = None
        self.svg = None

    def para(self, url):
        with self.cerrojo:
            if url != self.url or self.svg is None:
                self.url = url
                self.svg = generar_qr(url)
            return self.svg


def generar_qr(url):
    if not shutil.which("qrencode"):
        return None
    try:
        r = subprocess.run(
            ["qrencode", "-t", "SVG", "-m", "2", "-o", "-", url],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    inicio = r.stdout.find("<svg")
    if r.returncode != 0 or inicio < 0:
        return None
    return r.stdout[inicio:]


class Servidor(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, puerto, medios):
        super().__init__(("127.0.0.1", puerto), Pagina)
        self.medios = medios
        self.token = secrets.token_urlsafe(32)
        self.nonce = secrets.token_urlsafe(16)
        self.progreso = Progreso(medios)
        self.qr = Qr()
        self.cerrojo_accion = threading.Lock()
        self.accion = None

    def estado(self):
        rc, salida = ejecutar(self.medios, ["_estado-json"], 30)
        if rc != 0:
            return {"error": salida.strip() or f"medios terminó con código {rc}"}
        try:
            datos = json.loads(salida)
        except ValueError:
            return {"error": "No entiendo lo que devuelve medios: " + salida.strip()[:500]}
        datos["progreso"] = self.progreso.calcular(datos.get("dlna") or {})
        jellyfin = datos.get("jellyfin") or {}
        datos["qr"] = self.qr.para(jellyfin["url"]) if jellyfin.get("activo") and jellyfin.get("url") else None
        datos["qrencode"] = shutil.which("qrencode") is not None
        datos["accion"] = self.accion
        return datos

    def accionar(self, nombre):
        argumentos, limite = ACCIONES[nombre]
        if not self.cerrojo_accion.acquire(blocking=False):
            return 409, {"error": f"Espera: todavía se está ejecutando «{self.accion}»"}
        try:
            self.accion = nombre
            registrar(f"Acción: {nombre}")
            rc, salida = ejecutar(self.medios, argumentos, limite)
            registrar(f"Acción {nombre} terminada con código {rc}")
            return 200, {"codigo": rc, "salida": salida}
        finally:
            self.accion = None
            self.cerrojo_accion.release()

    def buscar(self, texto):
        rc, salida = ejecutar(self.medios, ["buscar", texto], 120)
        return {"codigo": rc, "salida": salida}


class Pagina(BaseHTTPRequestHandler):
    server_version = "media-bridge"
    sys_version = ""

    def log_message(self, formato, *argumentos):
        pass

    def anfitrion(self):
        host = self.headers.get("Host", "")
        try:
            nombre = urlsplit("//" + host).hostname
        except ValueError:
            return None
        return host if nombre in ANFITRIONES else None

    def responder(self, codigo, cuerpo, tipo="application/json; charset=utf-8"):
        if isinstance(cuerpo, (dict, list)):
            cuerpo = json.dumps(cuerpo, ensure_ascii=False)
        datos = cuerpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        nonce = self.server.nonce
        self.send_header(
            "Content-Security-Policy",
            f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
            "connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(datos)

    def token_valido(self):
        return hmac.compare_digest(self.headers.get("X-Token", ""), self.server.token)

    def do_GET(self):
        if not self.anfitrion():
            return self.responder(403, {"error": "Solo se puede abrir desde este equipo (127.0.0.1)"})
        ruta = urlsplit(self.path).path
        if ruta == "/":
            html = HTML.replace("__TOKEN__", self.server.token).replace("__NONCE__", self.server.nonce)
            return self.responder(200, html, "text/html; charset=utf-8")
        if ruta == "/api/estado":
            if not self.token_valido():
                return self.responder(403, {"error": "Falta el permiso de la página; recárgala"})
            return self.responder(200, self.server.estado())
        return self.responder(404, {"error": "No existe"})

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        host = self.anfitrion()
        if not host:
            return self.responder(403, {"error": "Solo se puede abrir desde este equipo (127.0.0.1)"})
        if self.headers.get("Origin") != f"http://{host}":
            return self.responder(403, {"error": "Petición desde otra página: no la hago"})
        if not self.token_valido():
            return self.responder(403, {"error": "Falta el permiso de la página; recárgala"})
        try:
            largo = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            largo = -1
        if largo < 0 or largo > MAXIMO_CUERPO:
            return self.responder(400, {"error": "Petición demasiado grande"})
        try:
            cuerpo = json.loads(self.rfile.read(largo) or b"{}")
        except ValueError:
            return self.responder(400, {"error": "Petición no válida"})
        if not isinstance(cuerpo, dict):
            return self.responder(400, {"error": "Petición no válida"})
        ruta = urlsplit(self.path).path
        if ruta == "/api/buscar":
            texto = cuerpo.get("texto")
            if not isinstance(texto, str) or not texto.strip() or len(texto) > 200:
                return self.responder(400, {"error": "Escribe qué quieres buscar"})
            return self.responder(200, self.server.buscar(texto.strip()))
        nombre = ruta.removeprefix("/api/")
        if ruta.startswith("/api/") and nombre in ACCIONES:
            codigo, respuesta = self.server.accionar(nombre)
            return self.responder(codigo, respuesta)
        return self.responder(404, {"error": "No existe"})


HTML = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="token" content="__TOKEN__">
<title>media-bridge</title>
<style nonce="__NONCE__">
:root {
  --fondo: #f4f5f7;
  --tarjeta: #ffffff;
  --texto: #1d2129;
  --suave: #5f6673;
  --borde: #dfe2e7;
  --acento: #2f6fdf;
  --acento-texto: #ffffff;
  --bien: #1f8a4c;
  --mal: #c8362d;
  --aviso: #a86500;
  --pastilla-bien: #e2f4ea;
  --pastilla-mal: #fbe5e3;
  --pastilla-neutra: #eceef2;
}
@media (prefers-color-scheme: dark) {
  :root {
    --fondo: #14161a;
    --tarjeta: #1d2026;
    --texto: #e7e9ee;
    --suave: #9aa1ad;
    --borde: #30343c;
    --acento: #6a9bf4;
    --acento-texto: #0d1117;
    --bien: #4cc27f;
    --mal: #f07167;
    --aviso: #e8a33d;
    --pastilla-bien: #183326;
    --pastilla-mal: #3a1d1b;
    --pastilla-neutra: #2a2e36;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--fondo);
  color: var(--texto);
  font: 16px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
main { max-width: 960px; margin: 0 auto; padding: 16px; }
header { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; margin-bottom: 16px; }
h1 { font-size: 1.4rem; margin: 0; }
h2 { font-size: 1.05rem; margin: 0 0 10px; }
.version { color: var(--suave); font-size: .85rem; }
.pastilla {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: .85rem;
  font-weight: 600;
  background: var(--pastilla-neutra);
  color: var(--suave);
  white-space: nowrap;
}
.pastilla.bien { background: var(--pastilla-bien); color: var(--bien); }
.pastilla.mal { background: var(--pastilla-mal); color: var(--mal); }
.botones { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
button {
  font: inherit;
  border: 1px solid var(--borde);
  background: var(--tarjeta);
  color: var(--texto);
  border-radius: 8px;
  padding: 8px 16px;
  cursor: pointer;
  min-height: 44px;
}
button.principal { background: var(--acento); border-color: var(--acento); color: var(--acento-texto); }
button.peligro { color: var(--mal); }
button:disabled { opacity: .5; cursor: default; }
.rejilla { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
.tarjeta { background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 12px; padding: 14px 16px; min-width: 0; }
.ancha { grid-column: 1 / -1; }
#caja-salida { margin-bottom: 12px; }
#aparatos { margin-top: 10px; }
ul, ol { margin: 0; padding-left: 20px; }
li { margin: 2px 0; overflow-wrap: anywhere; }
.lista-limpia { list-style: none; padding: 0; }
.fila { display: flex; justify-content: space-between; gap: 8px; padding: 4px 0; border-bottom: 1px solid var(--borde); }
.fila:last-child { border-bottom: 0; }
.suave { color: var(--suave); }
.bien { color: var(--bien); }
.mal { color: var(--mal); }
.aviso { color: var(--aviso); }
a { color: var(--acento); overflow-wrap: anywhere; }
pre {
  margin: 10px 0 0;
  padding: 10px;
  border-radius: 8px;
  background: var(--fondo);
  border: 1px solid var(--borde);
  overflow-x: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font: 13px/1.4 ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
}
.barra { height: 10px; border-radius: 999px; background: var(--pastilla-neutra); overflow: hidden; margin: 8px 0 4px; }
.barra > div { height: 100%; width: 0; background: var(--acento); transition: width .5s; }
#qr { max-width: 220px; margin-top: 10px; background: #fff; border-radius: 8px; padding: 4px; }
#qr svg { display: block; width: 100%; height: auto; }
#error { background: var(--pastilla-mal); color: var(--mal); border-radius: 8px; padding: 10px 14px; margin-bottom: 16px; white-space: pre-wrap; }
form { display: flex; gap: 8px; }
input[type=search] {
  flex: 1;
  min-width: 0;
  font: inherit;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--borde);
  background: var(--fondo);
  color: var(--texto);
  min-height: 44px;
}
dialog {
  border: 1px solid var(--borde);
  border-radius: 12px;
  background: var(--tarjeta);
  color: var(--texto);
  max-width: min(420px, calc(100vw - 32px));
  padding: 18px;
}
dialog::backdrop { background: rgba(0, 0, 0, .45); }
dialog .botones { justify-content: flex-end; margin: 16px 0 0; }
[hidden] { display: none !important; }
</style>
</head>
<body>
<main>
  <header>
    <h1>media-bridge</h1>
    <span id="encendido" class="pastilla">…</span>
    <span id="version" class="version"></span>
  </header>
  <div id="error" hidden></div>
  <div class="botones">
    <button id="encender" class="principal">Encender</button>
    <button id="apagar" class="peligro">Apagar</button>
    <button id="reescanear">Reescanear</button>
    <span id="en-marcha" class="suave" hidden></span>
  </div>
  <section id="caja-salida" class="tarjeta ancha" hidden>
    <h2 id="titulo-salida">Resultado</h2>
    <pre id="salida"></pre>
  </section>
  <div class="rejilla">
    <section class="tarjeta">
      <h2>Servicios</h2>
      <ul id="servicios" class="lista-limpia"></ul>
      <ul id="reenvios" class="lista-limpia"></ul>
    </section>
    <section class="tarjeta" id="caja-jellyfin" hidden>
      <h2>Jellyfin</h2>
      <div id="jellyfin"></div>
      <div id="qr" hidden></div>
    </section>
    <section class="tarjeta" id="caja-dlna" hidden>
      <h2>DLNA</h2>
      <div id="dlna"></div>
      <div id="progreso" hidden>
        <div class="barra"><div id="barra"></div></div>
        <div id="texto-progreso" class="suave"></div>
      </div>
      <ul id="aparatos" class="lista-limpia"></ul>
    </section>
    <section class="tarjeta" id="caja-recientes" hidden>
      <h2>Añadidos recientemente</h2>
      <ol id="recientes"></ol>
    </section>
    <section class="tarjeta ancha">
      <h2>Buscar en el servidor</h2>
      <form id="buscador">
        <input type="search" id="texto" placeholder="Título de una película o serie" maxlength="200" autocomplete="off" aria-label="Qué buscar">
        <button type="submit" class="principal">Buscar</button>
      </form>
      <pre id="resultados" hidden></pre>
    </section>
  </div>
</main>
<dialog id="confirmar">
  <p id="pregunta"></p>
  <p id="advertencia" class="aviso" hidden></p>
  <div class="botones">
    <button id="cancelar">Cancelar</button>
    <button id="aceptar" class="principal">Sí</button>
  </div>
</dialog>
<script nonce="__NONCE__">
"use strict";
const TOKEN = document.querySelector('meta[name="token"]').content;
const $ = (id) => document.getElementById(id);
let ultimo = null;
let ocupado = false;

const NOMBRES = {
  "media-bridge-mount.service": "Montaje de las carpetas",
  "media-bridge-dlna.service": "DLNA",
  "media-bridge-rescan.service": "Reescaneo automático",
  "media-bridge-descubrimiento.service": "Descubrimiento de Jellyfin",
};
const ESTADOS = {
  active: ["encendido", "bien"],
  inactive: ["apagado", ""],
  failed: ["ha fallado", "mal"],
  activating: ["arrancando", ""],
  deactivating: ["parando", ""],
  reloading: ["recargando", ""],
};

function el(etiqueta, clase, texto) {
  const e = document.createElement(etiqueta);
  if (clase) e.className = clase;
  if (texto !== undefined) e.textContent = texto;
  return e;
}

function nombreServicio(u) {
  if (NOMBRES[u]) return NOMBRES[u];
  const m = u.match(/^media-bridge-forward@(\d+)\.service$/);
  return m ? "Reenvío del puerto " + m[1] : u;
}

async function api(ruta, cuerpo) {
  const opciones = { headers: { "X-Token": TOKEN }, cache: "no-store" };
  if (cuerpo !== undefined) {
    opciones.method = "POST";
    opciones.headers["Content-Type"] = "application/json";
    opciones.body = JSON.stringify(cuerpo);
  }
  let r;
  try {
    r = await fetch(ruta, opciones);
  } catch (e) {
    return { error: "No hay respuesta de la página. ¿Se ha apagado con medios web off?" };
  }
  let datos;
  try {
    datos = await r.json();
  } catch (e) {
    datos = {};
  }
  if (!r.ok && !datos.error) datos.error = "Error " + r.status;
  return datos;
}

function conectadosDlna(d) {
  return (d.dlna.aparatos || []).filter((a) => a.conectado).map((a) => a.ip);
}

function pintar(d) {
  $("error").hidden = !d.error;
  if (d.error) {
    $("error").textContent = d.error;
    return;
  }
  ultimo = d;
  const pastilla = $("encendido");
  pastilla.textContent = d.encendido ? "Encendido" : "Apagado";
  pastilla.className = "pastilla" + (d.encendido ? " bien" : "");
  $("version").textContent = "versión " + d.version;

  const servicios = $("servicios");
  servicios.replaceChildren();
  if (!d.servicios.length) {
    servicios.append(el("li", "suave", "Nada encendido todavía"));
  }
  for (const s of d.servicios) {
    const [texto, clase] = ESTADOS[s.estado] || [s.estado, ""];
    const fila = el("li", "fila");
    fila.append(el("span", "", nombreServicio(s.nombre)), el("span", "pastilla " + clase, texto));
    servicios.append(fila);
  }
  const reenvios = $("reenvios");
  reenvios.replaceChildren();
  for (const r of d.reenvios.filter((r) => r.activo)) {
    const fila = el("li", "fila");
    const enlace = el("a", "", r.url);
    enlace.href = r.url;
    enlace.target = "_blank";
    enlace.rel = "noopener";
    fila.append(el("span", "suave", "Reenvío"), enlace);
    reenvios.append(fila);
  }

  const j = d.jellyfin;
  $("caja-jellyfin").hidden = !j.previsto;
  const jellyfin = $("jellyfin");
  jellyfin.replaceChildren();
  if (j.activo) {
    const p = el("p");
    const enlace = el("a", "", j.url);
    enlace.href = j.url;
    enlace.target = "_blank";
    enlace.rel = "noopener";
    p.append(enlace);
    jellyfin.append(p);
    jellyfin.append(el("p", "", j.conexiones.length ? "Conectados ahora: " + j.conexiones.join(", ") : "Nadie conectado ahora"));
    if (j.descubrimiento) jellyfin.append(el("p", "suave", "Las apps de Jellyfin de la red lo encuentran solas."));
    if (!d.qr && !d.qrencode) jellyfin.append(el("p", "suave", "Para ver aquí el código QR, instala qrencode."));
  } else {
    jellyfin.append(el("p", "suave", "El reenvío de Jellyfin está apagado."));
  }
  $("qr").hidden = !d.qr;
  if (d.qr && $("qr").dataset.url !== j.url) {
    $("qr").innerHTML = d.qr;
    $("qr").dataset.url = j.url;
  }

  const n = d.dlna;
  $("caja-dlna").hidden = !n.previsto;
  const dlna = $("dlna");
  dlna.replaceChildren();
  if (n.activo) {
    dlna.append(el("p", "", "En la televisión aparece como «" + n.nombre + "»."));
    dlna.append(el("p", "suave", n.reescaneo));
  } else {
    dlna.append(el("p", "suave", "El DLNA está apagado."));
  }
  const pr = d.progreso;
  $("progreso").hidden = !pr;
  if (pr) {
    $("barra").style.width = (pr.porcentaje || 0) + "%";
    let texto = "Indexando: " + pr.videos + (pr.total ? " de " + pr.total + " vídeos (" + pr.porcentaje + " %)" : " vídeos (contando el total…)");
    if (pr.ritmo) texto += " · " + pr.ritmo + "/min";
    if (pr.minutos) texto += " · faltan unos " + pr.minutos + " min";
    $("texto-progreso").textContent = texto;
  }
  const aparatos = $("aparatos");
  aparatos.replaceChildren();
  if (n.activo) {
    aparatos.append(el("li", "suave", n.aparatos.length ? "Aparatos que han encontrado el DLNA:" : "Ningún aparato ha encontrado todavía el DLNA"));
    for (const a of n.aparatos) {
      const fila = el("li", "fila");
      fila.append(el("span", "", a.ip + " (" + a.tipo + ")"));
      if (a.conectado) fila.append(el("span", "pastilla bien", "conectado ahora"));
      aparatos.append(fila);
    }
  }

  const rc = d.recientes;
  $("caja-recientes").hidden = !rc.activo;
  const recientes = $("recientes");
  recientes.replaceChildren();
  for (const t of rc.lista) recientes.append(el("li", "", t.replace(/^\d+ · /, "")));
  if (rc.activo && !rc.lista.length) recientes.append(el("li", "suave", "Todavía no hay ninguno: se rellena al encender"));

  if (!ocupado) {
    $("en-marcha").hidden = !d.accion;
    $("en-marcha").textContent = d.accion ? "En marcha: " + d.accion + "…" : "";
  }
  $("apagar").disabled = ocupado || !!d.accion || !d.encendido;
  $("reescanear").disabled = ocupado || !!d.accion || !n.activo;
  $("encender").disabled = ocupado || !!d.accion;
}

async function refrescar() {
  if (document.hidden) return;
  pintar(await api("/api/estado"));
}

function pintarSalida(titulo, texto) {
  $("caja-salida").hidden = false;
  $("titulo-salida").textContent = titulo;
  const pre = $("salida");
  pre.replaceChildren();
  for (const linea of texto.replace(/\s+$/, "").split("\n")) {
    let clase = "";
    if (linea.includes("✘")) clase = "mal";
    else if (/^\s*!/.test(linea) || linea.startsWith("Aviso")) clase = "aviso";
    else if (linea.includes("✔")) clase = "bien";
    pre.append(el("span", clase, linea + "\n"));
  }
}

function confirmar(pregunta, advertencia, boton) {
  return new Promise((resolver) => {
    const dialogo = $("confirmar");
    $("pregunta").textContent = pregunta;
    $("advertencia").textContent = advertencia || "";
    $("advertencia").hidden = !advertencia;
    $("aceptar").textContent = boton;
    const cerrar = (valor) => {
      $("aceptar").onclick = $("cancelar").onclick = dialogo.oncancel = null;
      dialogo.close();
      resolver(valor);
    };
    $("aceptar").onclick = () => cerrar(true);
    $("cancelar").onclick = () => cerrar(false);
    dialogo.oncancel = () => cerrar(false);
    dialogo.showModal();
  });
}

const TEXTOS = {
  encender: ["Encendiendo…", "Encender"],
  apagar: ["Apagando…", "Apagar"],
  reescanear: ["Reescaneando (tarda unos 20 s)…", "Reescanear"],
};

async function accion(nombre) {
  if (ultimo && nombre === "apagar") {
    const quien = [...new Set([...conectadosDlna(ultimo), ...ultimo.jellyfin.conexiones])];
    const aviso = quien.length ? "Hay alguien conectado ahora (" + quien.join(", ") + "): se cortará lo que esté viendo." : "";
    if (!(await confirmar("¿Apagar media-bridge? La televisión dejará de ver el servidor.", aviso, "Apagar"))) return;
  }
  if (ultimo && nombre === "reescanear") {
    const quien = conectadosDlna(ultimo);
    const aviso = quien.length || ultimo.dlna.viendo
      ? "Hay alguien viendo algo por DLNA" + (quien.length ? " (" + quien.join(", ") + ")" : "") + ": se cortará."
      : "";
    if (!(await confirmar("¿Reescanear ahora? El DLNA se reinicia para buscar vídeos nuevos.", aviso, "Reescanear"))) return;
  }
  ocupado = true;
  for (const b of ["encender", "apagar", "reescanear"]) $(b).disabled = true;
  $("en-marcha").hidden = false;
  $("en-marcha").textContent = TEXTOS[nombre][0];
  const r = await api("/api/" + nombre, {});
  ocupado = false;
  $("en-marcha").hidden = true;
  if (r.error) {
    pintarSalida(TEXTOS[nombre][1], r.error);
  } else {
    pintarSalida(TEXTOS[nombre][1] + (r.codigo === 0 ? "" : " (no ha ido bien)"), r.salida || "Hecho");
  }
  await refrescar();
}

$("encender").addEventListener("click", () => accion("encender"));
$("apagar").addEventListener("click", () => accion("apagar"));
$("reescanear").addEventListener("click", () => accion("reescanear"));

$("buscador").addEventListener("submit", async (e) => {
  e.preventDefault();
  const texto = $("texto").value.trim();
  if (!texto) return;
  const pre = $("resultados");
  pre.hidden = false;
  pre.textContent = "Buscando en el servidor…";
  const r = await api("/api/buscar", { texto });
  pre.textContent = r.error || r.salida || "Sin resultados";
});

document.addEventListener("visibilitychange", refrescar);
refrescar();
setInterval(refrescar, 5000);
</script>
</body>
</html>
"""


def main():
    a = argparse.ArgumentParser(description="Página web local de media-bridge")
    a.add_argument("--puerto", type=int, default=8787)
    a.add_argument("--medios", required=True)
    a = a.parse_args()
    try:
        servidor = Servidor(a.puerto, a.medios)
    except OSError as e:
        sys.exit(f"No puedo escuchar en 127.0.0.1:{a.puerto}: {e}")
    registrar(f"Página web en http://127.0.0.1:{servidor.server_address[1]}")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

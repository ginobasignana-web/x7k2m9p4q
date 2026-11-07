#!/usr/bin/env python3
# BASINGAME · acceso privado por cliente, ARMADO EN GITHUB (no depende de ninguna computadora).
# Lo ejecuta GitHub Actions cada ~30 min y cada vez que cambia liga_argentina_analytics.html.
# Cifra el tablero con la clave del cliente (secreto del repositorio), lo publica en acc/<slug>.html y lo retira al vencer.
import os, re, sys, json, hashlib, gzip, base64, time, datetime, secrets, subprocess
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

RAIZ = Path(os.environ.get("BG_RAIZ") or Path(__file__).resolve().parent.parent)
AQUI = Path(__file__).resolve().parent
ART = datetime.timezone(datetime.timedelta(hours=-3))
ITER = 200000

def log(m): print(f"{datetime.datetime.now(ART):%Y-%m-%d %H:%M:%S} {m}", flush=True)
def hora_art(ts): return datetime.datetime.fromtimestamp(ts, ART)
def clave_aes(clave, sal): return hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), sal, ITER, 32)

def cifrar(b, clave, vence):
    sal, iv = secrets.token_bytes(16), secrets.token_bytes(12)
    ct = AESGCM(clave_aes(clave, sal)).encrypt(iv, gzip.compress(b, 9), vence.encode("utf-8"))
    return base64.b64encode(sal + iv + ct).decode("ascii")

def descifrar(b64, clave, vence):
    raw = base64.b64decode(b64); sal, iv, ct = raw[:16], raw[16:28], raw[28:]
    return gzip.decompress(AESGCM(clave_aes(clave, sal)).decrypt(iv, ct, vence.encode("utf-8")))

def armar_pagina(cfg, payload):
    t = (AQUI / "plantilla_acceso.html").read_text(encoding="utf-8")
    vd = datetime.datetime.fromisoformat(cfg["vence"])
    rep = {"{{CLUB}}": cfg["club"], "{{LIGA}}": cfg["liga"], "{{VENCE_ISO}}": cfg["vence"],
           "{{VENCE_TXT}}": f"{vd:%d/%m/%Y} a las {vd:%H:%M} (hora de Argentina)", "{{ITER}}": str(ITER), "{{PAYLOAD}}": payload}
    for k, v in rep.items(): t = t.replace(k, v)
    return t

def fecha_datos(b):
    t = b.decode("utf-8", "replace"); lim = time.time() + 600; c = []
    for d, m, y, H, M in re.findall(r"\b(\d{2})/(\d{2})/(20\d{2}) (\d{2}):(\d{2})\b", t):
        try: ts = datetime.datetime(int(y), int(m), int(d), int(H), int(M), tzinfo=ART).timestamp()
        except ValueError: continue
        if ts <= lim: c.append(ts)
    return max(c) if c else None

def sello(html, ts):
    txt = f"Datos actualizados: {hora_art(ts):%d/%m/%Y %H:%M} (hora de Argentina)"
    div = ('<div id="bg-sello" style="position:fixed;right:10px;bottom:8px;z-index:2147483000;font:600 11px/1.2 Barlow,Arial,sans-serif;'
           'letter-spacing:.04em;color:#c8a74d;background:rgba(7,16,31,.9);border:1px solid rgba(200,167,77,.45);padding:5px 9px;'
           'border-radius:6px;pointer-events:none">' + txt + '</div>').encode("utf-8")
    i = html.rfind(b"</body>")
    return html[:i] + div + html[i:] if i >= 0 else html + div

def main():
    cid = sys.argv[1] if len(sys.argv) > 1 else "ucolon"
    cfg = json.loads((AQUI / "clientes" / f"{cid}.json").read_text(encoding="utf-8"))
    rel = Path(cfg["carpeta"]) / f'{cfg["slug"]}.html'; destino = RAIZ / rel
    est_f = RAIZ / ".acceso_estado" / f"{cid}.json"; est_f.parent.mkdir(exist_ok=True)
    est = json.loads(est_f.read_text()) if est_f.exists() else {}
    if datetime.datetime.now(datetime.timezone.utc) > datetime.datetime.fromisoformat(cfg["vence"]):
        if destino.exists(): destino.unlink(); log(f"[{cid}] VENCIDO el {cfg['vence']}: acceso retirado")
        else: log(f"[{cid}] vencido: ya estaba retirado")
        return
    clave = os.environ.get("ACCESO_CLAVE", "").strip()
    if not clave: log(f"[{cid}] ERROR: falta el secreto ACCESO_UCOLON_CLAVE en GitHub (Settings > Secrets and variables > Actions)"); sys.exit(1)
    fuente = RAIZ / cfg.get("fuente_nube", "liga_argentina_analytics.html")
    if not fuente.exists(): log(f"[{cid}] ERROR: no existe {fuente.name} en el repositorio"); sys.exit(2)
    html0 = fuente.read_bytes()
    if len(html0) < 2_000_000 or b"const DATA" not in html0: log(f"[{cid}] ERROR: el HTML de origen no parece válido ({len(html0)} bytes); no se publica"); sys.exit(3)
    ts = fecha_datos(html0)
    if ts is None:
        r = subprocess.run(["git", "-C", str(RAIZ), "log", "-1", "--format=%ct", "--", fuente.name], capture_output=True, text=True)
        ts = float(r.stdout.strip()) if r.stdout.strip() else time.time()
    h0 = hashlib.sha256(html0).hexdigest()
    if est.get("fuente_hash") == h0 and est.get("clave_hash") == hashlib.sha256(clave.encode()).hexdigest() and destino.exists():
        log(f"[{cid}] sin novedades (datos del {hora_art(ts):%d/%m/%Y %H:%M})"); return
    if est.get("datos_ts") and ts < est["datos_ts"] - 60 and destino.exists():
        log(f"[{cid}] el origen trae datos MÁS VIEJOS ({hora_art(ts):%d/%m %H:%M}) que lo publicado ({hora_art(est['datos_ts']):%d/%m %H:%M}): no se retrocede"); return
    html = sello(html0, ts)
    payload = cifrar(html, clave, cfg["vence"])
    if hashlib.sha256(descifrar(payload, clave, cfg["vence"])).hexdigest() != hashlib.sha256(html).hexdigest():
        log(f"[{cid}] ERROR: la verificación del cifrado falló"); sys.exit(4)
    destino.parent.mkdir(parents=True, exist_ok=True); destino.write_text(armar_pagina(cfg, payload), encoding="utf-8")
    est.update(fuente_hash=h0, clave_hash=hashlib.sha256(clave.encode()).hexdigest(), datos_ts=ts, datos=hora_art(ts).isoformat(timespec="minutes"),
               publicado=datetime.datetime.now(ART).isoformat(timespec="seconds"))
    est_f.write_text(json.dumps(est, indent=1))
    log(f"[{cid}] publicado con datos del {hora_art(ts):%d/%m/%Y %H:%M} -> {rel}")

if __name__ == "__main__": main()

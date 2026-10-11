"""Installa la "scatola" WebAssembly per eseguire in sicurezza il codice generato dai modelli.

Scarica solo da fonti ufficiali e verifica l'impronta SHA-256 pubblicata da GitHub:
  - wasmtime (Bytecode Alliance): motore WebAssembly con isolamento a capacità
  - CPython per WASI (build di Brett Cannon, core developer di CPython)
Tutto finisce in strumenti/valutazione/runtime/ (esclusa da git).
"""

import hashlib
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

RUNTIME = Path(__file__).resolve().parent / "runtime"
PACCHETTI = [
    ("bytecodealliance/wasmtime", "v49.0.1", "wasmtime-v49.0.1-x86_64-windows.zip", "wasmtime"),
    ("brettcannon/cpython-wasi-build", "v3.14.7", "python-3.14.7-wasi_sdk-24.zip", "python"),
]


def digest_ufficiale(repo, tag, nome):
    url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "mia-installer"}), timeout=30) as r:
        release = json.load(r)
    for asset in release["assets"]:
        if asset["name"] == nome:
            return asset["browser_download_url"], (asset.get("digest") or "").removeprefix("sha256:"), asset["size"]
    raise SystemExit(f"File {nome} non trovato nella release {repo} {tag}")


def scarica(repo, tag, nome, cartella):
    destinazione = RUNTIME / cartella
    if destinazione.exists():
        print(f"  {cartella}: già presente")
        return
    url, sha_atteso, dimensione = digest_ufficiale(repo, tag, nome)
    print(f"  scarico {nome} ({dimensione / 1e6:.1f} MB) da {repo}...")
    archivio = RUNTIME / nome
    h = hashlib.sha256()
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "mia-installer"}), timeout=120) as r, \
            open(archivio, "wb") as f:
        while blocco := r.read(1 << 20):
            h.update(blocco)
            f.write(blocco)
    if archivio.stat().st_size != dimensione:
        archivio.unlink()
        raise SystemExit(f"Dimensione errata per {nome}: download incompleto")
    if sha_atteso and h.hexdigest() != sha_atteso:
        archivio.unlink()
        raise SystemExit(f"Impronta SHA-256 NON corrispondente per {nome}: file scartato")
    print(f"  impronta SHA-256 {'verificata' if sha_atteso else 'non pubblicata (verificata solo la dimensione)'}")
    with zipfile.ZipFile(archivio) as z:
        z.extractall(destinazione)
    archivio.unlink()


def main():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    for pacchetto in PACCHETTI:
        scarica(*pacchetto)
    wasmtime = next(RUNTIME.glob("wasmtime/**/wasmtime.exe"), None)
    python_wasm = next(RUNTIME.glob("python/**/python.wasm"), None)
    if not wasmtime or not python_wasm:
        raise SystemExit("Installazione incompleta: wasmtime.exe o python.wasm mancanti")
    print("Pronto:", wasmtime.relative_to(RUNTIME), "|", python_wasm.relative_to(RUNTIME))


if __name__ == "__main__":
    sys.exit(main())

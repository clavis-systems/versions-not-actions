"""Esecuzione isolata del codice generato dai modelli, senza Docker.

Il programma gira dentro CPython compilato in WebAssembly (WASI) sul motore wasmtime.
WebAssembly non ha accesso al sistema: vede solo ciò che gli viene concesso esplicitamente.
Qui gli si concede soltanto una cartella temporanea usa-e-getta con il programma e una copia
della libreria standard, cancellata a fine esecuzione.

Garanzie:
  - nessun file del PC, nessuna variabile d'ambiente, nessun avvio di programmi
  - nessuna rete (le socket non vengono concesse)
  - limite di tempo (wasmtime + controllo esterno), di memoria e di output
  - nessuna persistenza: ogni esecuzione parte da una copia pulita

Stessa interfaccia di safe_runner: preflight(linguaggi) e run(codice, linguaggio, timeout).
In più run(..., files={...}) copia i file di un progetto in /sandbox/progetto (usato dagli
strumenti dell'agente in strumenti/agenti/mcp_sandbox.py per eseguire i test).
Esegue solo Python: per JavaScript resta necessario Docker.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
import zipfile
from pathlib import Path, PurePosixPath

RUNTIME = Path(__file__).resolve().parent / "runtime"
MEMORY_BYTES = 256 * 1024 * 1024
OUTPUT_LIMIT = 64_000
ESCLUSI = {"__pycache__", "test", "tests", "idlelib", "tkinter", "turtledemo", "ensurepip"}
_preparazione = threading.Lock()


class SandboxUnavailable(RuntimeError):
    pass


def _paths():
    wasmtime = next(RUNTIME.glob("wasmtime/**/wasmtime.exe"), None)
    python = RUNTIME / "python" / "python.wasm"
    stdlib = next((p for p in (RUNTIME / "python" / "lib").glob("python3.*") if p.is_dir()), None) \
        if (RUNTIME / "python" / "lib").exists() else None
    if not wasmtime or not python.exists() or not stdlib:
        raise SandboxUnavailable("Sandbox WebAssembly non installata: esegui strumenti/valutazione/installa_sandbox.py")
    return wasmtime, python, stdlib


def _prepare():
    """Una volta sola: precompila l'interprete (avvio rapido) e impacchetta la libreria standard."""
    wasmtime, python, stdlib = _paths()
    versione = stdlib.name.replace("python", "").replace(".", "")          # "3.14" -> "314"
    cwasm = RUNTIME / "python.cwasm"
    stdzip = RUNTIME / f"python{versione}.zip"
    with _preparazione:
        if not cwasm.exists() or cwasm.stat().st_mtime < python.stat().st_mtime:
            # stesse opzioni dell'esecuzione: il limite di tempo usa l'interruzione a "epoch"
            r = subprocess.run([str(wasmtime), "compile", "-W", "epoch-interruption=y",
                                "-W", f"max-memory-size={MEMORY_BYTES}", str(python), "-o", str(cwasm)],
                               capture_output=True, text=True, timeout=900)
            if r.returncode:
                raise SandboxUnavailable("Precompilazione dell'interprete non riuscita: " + r.stderr[-300:])
        if not stdzip.exists():
            provvisorio = stdzip.with_suffix(".tmp")
            # senza compressione: questa build WASI non include zlib, necessario per leggere zip compressi
            with zipfile.ZipFile(provvisorio, "w", zipfile.ZIP_STORED) as z:
                for f in stdlib.rglob("*"):
                    relativo = f.relative_to(stdlib)
                    if f.is_file() and not ESCLUSI.intersection(relativo.parts):
                        z.write(f, relativo.as_posix())
            provvisorio.replace(stdzip)
    return wasmtime, cwasm, stdzip


def _prepare_sicuro():
    """Come _prepare, ma ogni problema di avvio diventa SandboxUnavailable (W1): i chiamanti gestiscono un solo tipo."""
    try:
        return _prepare()
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SandboxUnavailable(f"Sandbox WebAssembly non utilizzabile: {exc}") from exc


def preflight(languages: set[str]) -> None:
    if languages - {"python"}:
        raise SandboxUnavailable("La sandbox WebAssembly esegue solo Python; per JavaScript serve Docker.")
    _prepare_sicuro()


def run(code: str, lang: str, timeout: int = 20,
        files: dict[str, str | bytes] | None = None) -> tuple[bool, str, str]:
    """files: file extra (percorso relativo -> contenuto) che il programma trova in /sandbox/progetto."""
    if lang != "python":
        raise SandboxUnavailable("La sandbox WebAssembly esegue solo Python; per JavaScript serve Docker.")
    wasmtime, cwasm, stdzip = _prepare_sicuro()
    try:
        return _esegui(code, timeout, wasmtime, cwasm, stdzip, files)
    except OSError as exc:  # es. wasmtime.exe non avviabile: stesso tipo di errore del preflight (W1)
        raise SandboxUnavailable(f"Sandbox WebAssembly non utilizzabile: {exc}") from exc


NOMI_RISERVATI = {"CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(10)), *(f"LPT{n}" for n in range(10))}


def _parti_ammesse(nome) -> tuple[str, ...]:
    """Parti di un percorso relativo semplice. Rifiuta percorsi assoluti o ancorati (anche //server e \\\\server),
    unità (C:), "..", caratteri di controllo e nomi di dispositivo di Windows (CON, NUL, COM1...)."""
    testo = str(nome).replace("\\", "/")
    parti = PurePosixPath(testo).parts
    if not parti or testo.startswith("/") or any(
            p == ".." or ":" in p or p != p.rstrip(". ") or any(ord(c) < 32 for c in p)
            or p.split(".")[0].upper() in NOMI_RISERVATI for p in parti):
        raise ValueError(f"Percorso non ammesso nella sandbox: {nome!r}")
    return parti


def _copia_file(destinazione: Path, files):
    """Scrive i file extra dentro la cartella usa-e-getta; rifiuta percorsi che proverebbero a uscirne e
    controlla che ogni file resti dentro la cartella prima di scriverlo."""
    destinazione.mkdir(parents=True, exist_ok=True)
    radice = destinazione.resolve()
    for nome, contenuto in files.items():
        percorso = radice.joinpath(*_parti_ammesse(nome))
        if not percorso.resolve().is_relative_to(radice):
            raise ValueError(f"Percorso non ammesso nella sandbox: {nome!r}")
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_bytes(contenuto if isinstance(contenuto, bytes) else contenuto.encode("utf-8"))


def _esegui(code, timeout, wasmtime, cwasm, stdzip, files=None):
    with tempfile.TemporaryDirectory(prefix="mia-wasm-") as cartella:
        radice = Path(cartella)
        (radice / "lib").mkdir()
        shutil.copyfile(stdzip, radice / "lib" / stdzip.name)            # copia usa-e-getta
        (radice / "program.py").write_text(code, encoding="utf-8")
        if files:
            _copia_file(radice / "progetto", files)
        comando = [str(wasmtime), "run", "--allow-precompiled",
                   "-W", f"max-memory-size={MEMORY_BYTES}", "-W", f"timeout={timeout}s",
                   "-S", "inherit-network=n", "-S", "http=n",
                   "--dir", f"{radice}::/sandbox",
                   "--env", "PYTHONHOME=/sandbox", "--env", "PYTHONDONTWRITEBYTECODE=1",
                   "--env", "PYTHONIOENCODING=utf-8", "--env", "PYTHONSAFEPATH=1",
                   str(cwasm), "/sandbox/program.py"]
        processo = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    stdin=subprocess.DEVNULL)
        uscita = {"stdout": bytearray(), "stderr": bytearray()}
        troppo = threading.Event()
        blocco = threading.Lock()

        def svuota(tubo, nome):
            while pezzo := tubo.read(4096):
                with blocco:
                    if sum(len(v) for v in uscita.values()) + len(pezzo) > OUTPUT_LIMIT:
                        troppo.set()
                    else:
                        uscita[nome].extend(pezzo)
                if troppo.is_set():
                    processo.kill()
                    break

        fili = [threading.Thread(target=svuota, args=(processo.stdout, "stdout"), daemon=True),
                threading.Thread(target=svuota, args=(processo.stderr, "stderr"), daemon=True)]
        for filo in fili:
            filo.start()
        scaduto = False
        try:
            processo.wait(timeout=timeout + 10)          # rete di sicurezza oltre al limite interno
        except subprocess.TimeoutExpired:
            scaduto = True
            processo.kill()
            processo.wait(timeout=5)
        for filo in fili:
            filo.join(timeout=2)
        processo.stdout.close()
        processo.stderr.close()
        out = bytes(uscita["stdout"]).decode("utf-8", "replace")
        err = bytes(uscita["stderr"]).decode("utf-8", "replace")
        if scaduto or "wasm trap: interrupt" in err or "epoch deadline" in err:
            return False, "", "Timeout: limite di esecuzione superato."
        if troppo.is_set():
            return False, "", "Output troppo grande: limite di 64 KB superato."
        return processo.returncode == 0, out[-12000:], err[-3000:]

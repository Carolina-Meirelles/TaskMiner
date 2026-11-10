"""Envio dos eventos coletados para o servidor da empresa (painel web).

O agente sempre grava primeiro no banco local; este módulo envia em lotes o que ainda
não foi enviado. Se o servidor estiver fora do ar ou sem rede, os eventos esperam no
computador e são enviados na próxima tentativa. Nada se perde.
"""
import json
import threading
import urllib.error
import urllib.request

import db

TAMANHO_LOTE = 1000


class ErroServidor(Exception):
    pass


def _post(servidor, token, caminho, corpo, timeout=20):
    req = urllib.request.Request(
        servidor.rstrip("/") + caminho,
        data=json.dumps(corpo, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("erro")
        except Exception:
            msg = None
        raise ErroServidor(msg or f"O servidor respondeu com erro {e.code}.") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ConnectionError(f"Não foi possível falar com o servidor ({servidor}): {e}") from None


def registrar_consentimento(servidor, token, texto):
    """Confirma o código de coleta e registra o consentimento no servidor. Retorna o nome do colaborador."""
    return _post(servidor, token, "/api/consentimento", {"texto": texto}).get("colaborador")


def enviar_pendentes(con, servidor, token, usuario):
    """Envia os eventos locais ainda não enviados. Retorna quantos foram enviados."""
    chave = f"ultimo_enviado:{usuario}"
    total = 0
    while True:
        ultimo = int(db.get_meta(con, chave) or 0)
        linhas = con.execute(
            "SELECT id, ts, tipo, app, titulo, detalhe FROM eventos WHERE usuario = ? AND id > ? ORDER BY id LIMIT ?",
            (usuario, ultimo, TAMANHO_LOTE),
        ).fetchall()
        if not linhas:
            return total
        lote = [{"ts": r["ts"], "tipo": r["tipo"], "app": r["app"], "titulo": r["titulo"],
                 "detalhe": json.loads(r["detalhe"]) if r["detalhe"] else None} for r in linhas]
        _post(servidor, token, "/api/eventos", {"eventos": lote})
        db.set_meta(con, chave, linhas[-1]["id"])
        total += len(linhas)


class Enviador(threading.Thread):
    """Thread que envia os eventos a cada `intervalo` segundos enquanto o agente roda."""

    def __init__(self, servidor, token, usuario, intervalo=60):
        super().__init__(daemon=True)
        self.servidor, self.token, self.usuario, self.intervalo = servidor, token, usuario, intervalo
        self._parar = threading.Event()
        self.erro = None

    def run(self):
        con = db.conectar()
        while True:
            try:
                enviar_pendentes(con, self.servidor, self.token, self.usuario)
                self.erro = None
            except ConnectionError as e:
                self.erro = str(e)            # sem rede: tenta de novo no próximo ciclo
            except ErroServidor as e:
                if self.erro != str(e):
                    print(f"Aviso do servidor: {e}")
                self.erro = str(e)
            if self._parar.wait(self.intervalo):
                break
        try:  # última tentativa ao encerrar
            enviar_pendentes(con, self.servidor, self.token, self.usuario)
        except Exception:
            pass
        con.close()

    def parar(self):
        self._parar.set()

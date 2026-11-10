"""Executor local — roda no computador do colaborador e executa o que o Claude pede.

Uso:  python executor.py --servidor https://SEU-SITE --token SEU_CODIGO

Como funciona: a cada poucos segundos pergunta ao servidor se há um comando APROVADO para esta conta.
Se houver, tira uma captura da tela, envia ao servidor (que conversa com o Claude) e executa a ação
devolvida (clicar, digitar, rolar...), repetindo até a tarefa acabar.

Segurança embutida:
  * só executa comandos aprovados no painel e só com o executor liberado (Executor > Liberar);
  * mouse em qualquer canto da tela = para tudo na hora (pyautogui FAILSAFE); Ctrl+C também;
  * antes de cada captura confere a janela ativa: se for de senha, banco, gerenciador de senhas ou
    navegação anônima, NÃO envia captura e encerra o comando como "bloqueado";
  * limite de passos por comando (definido no servidor).
"""
import argparse
import base64
import io
import json
import sys
import time
import urllib.error
import urllib.request

import config

TERMOS_BLOQUEIO = [t.lower() for t in config.TERMOS_SENSIVEIS_TITULO] + [
    "internet banking", "bitwarden", "keepass", "1password", "lastpass", "banco do brasil", "itaú", "itau",
    "bradesco", "santander", "nubank", "caixa econômica",
]
APPS_BLOQUEIO = {a.lower() for a in config.APPS_IGNORADOS}


# ---------------------------------------------------------------------- servidor
class ErroServidor(Exception):
    pass


def _post(servidor, token, caminho, corpo, timeout=120):
    req = urllib.request.Request(
        servidor.rstrip("/") + caminho, data=json.dumps(corpo).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("erro")
        except Exception:
            msg = None
        raise ErroServidor(msg or f"O servidor respondeu com erro {e.code}.") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ConnectionError(f"Sem conexão com o servidor: {e}") from None


# ---------------------------------------------------------------------- tela
def _pyautogui():
    try:
        import pyautogui
    except ImportError:
        sys.exit("Instale as dependências: pip install -r requirements-executor.txt")
    pyautogui.FAILSAFE = True      # mouse num canto da tela interrompe tudo
    pyautogui.PAUSE = 0.05
    return pyautogui


def janela_ativa():
    """(título, executável) da janela em foco. Só Windows; nos outros sistemas devolve vazio."""
    if sys.platform != "win32":
        return "", ""
    try:
        import ctypes
        from ctypes import wintypes
        u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
        hwnd = u32.GetForegroundWindow()
        n = u32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        u32.GetWindowTextW(hwnd, buf, n + 1)
        pid = wintypes.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h = k32.OpenProcess(0x1000, False, pid.value)
        exe = ""
        if h:
            tam = wintypes.DWORD(260)
            caminho = ctypes.create_unicode_buffer(260)
            if k32.QueryFullProcessImageNameW(h, 0, caminho, ctypes.byref(tam)):
                exe = caminho.value.rsplit("\\", 1)[-1]
            k32.CloseHandle(h)
        return buf.value, exe
    except Exception:
        return "", ""


def janela_sensivel(titulo, exe):
    t = (titulo or "").lower()
    return (exe or "").lower() in APPS_BLOQUEIO or any(p in t for p in TERMOS_BLOQUEIO)


class Tela:
    """Captura reduzida e conversão de coordenadas (o Claude enxerga a captura reduzida)."""

    def __init__(self, pg):
        self.pg = pg
        real_w, real_h = pg.size()
        self.escala = min(1.0, config.EXECUTOR_TELA_MAX / max(real_w, real_h))
        self.w, self.h = int(real_w * self.escala), int(real_h * self.escala)

    def capturar_b64(self):
        img = self.pg.screenshot().convert("RGB").resize((self.w, self.h))
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return base64.b64encode(buf.getvalue()).decode()

    def real(self, coord):
        x, y = coord
        return int(x / self.escala), int(y / self.escala)


# ---------------------------------------------------------------------- ações
TECLAS = {"return": "enter", "super": "win", "page_down": "pagedown", "page_up": "pageup", "escape": "esc",
          "control": "ctrl", "backspace": "backspace", "ctrl": "ctrl", "alt": "alt", "shift": "shift"}


def _teclas(texto):
    return [TECLAS.get(p.strip().lower(), p.strip().lower()) for p in texto.split("+") if p.strip()]


def executar(pg, tela, a):
    """Executa uma ação da ferramenta de computador do Claude. Ações desconhecidas são recusadas."""
    tipo = a.get("action")
    coord = a.get("coordinate")
    if coord:
        x, y = tela.real(coord)
    if tipo == "screenshot":
        return
    if tipo == "mouse_move":
        pg.moveTo(x, y)
    elif tipo in ("left_click", "right_click", "middle_click", "double_click", "triple_click"):
        botao = {"right_click": "right", "middle_click": "middle"}.get(tipo, "left")
        cliques = {"double_click": 2, "triple_click": 3}.get(tipo, 1)
        if coord:
            pg.click(x, y, clicks=cliques, button=botao)
        else:
            pg.click(clicks=cliques, button=botao)
    elif tipo == "left_click_drag":
        sx, sy = tela.real(a["start_coordinate"]) if a.get("start_coordinate") else pg.position()
        pg.moveTo(sx, sy)
        pg.dragTo(x, y, duration=0.4, button="left")
    elif tipo == "type":
        pg.write(str(a.get("text", "")), interval=0.02)
    elif tipo == "key":
        pg.hotkey(*_teclas(str(a.get("text", ""))))
    elif tipo == "scroll":
        if coord:
            pg.moveTo(x, y)
        qtd = int(a.get("scroll_amount", 3)) * 100
        direcao = a.get("scroll_direction", "down")
        if direcao in ("up", "down"):
            pg.scroll(qtd if direcao == "up" else -qtd)
        else:
            pg.hscroll(qtd if direcao == "right" else -qtd)
    elif tipo == "wait":
        time.sleep(min(float(a.get("duration", 1)), 10))
    elif tipo == "cursor_position":
        return
    else:
        raise ValueError(f"Ação não suportada: {tipo}")


# ---------------------------------------------------------------------- laço principal
def rodar_comando(servidor, token, pg, tela, cmd):
    cid = cmd["id"]
    print(f"\n▶ Comando #{cid}: {cmd['instrucao']}")
    _post(servidor, token, "/api/executor/iniciar", {"comando_id": cid, "tela_w": tela.w, "tela_h": tela.h})
    try:
        _laco(servidor, token, pg, tela, cid)
    except (KeyboardInterrupt, pg.FailSafeException):
        try:
            _post(servidor, token, "/api/executor/fim",
                  {"comando_id": cid, "status": "cancelado", "resumo": "Interrompido no computador (Ctrl+C ou mouse no canto)."})
        finally:
            raise


def _laco(servidor, token, pg, tela, cid):
    tool_use_id = None
    while True:
        titulo, exe = janela_ativa()
        if janela_sensivel(titulo, exe):
            msg = "Parei por segurança: há uma janela sensível em foco (senha, banco ou navegação anônima)."
            print("  ⛔", msg)
            _post(servidor, token, "/api/executor/fim", {"comando_id": cid, "status": "bloqueado", "resumo": msg})
            return
        resp = _post(servidor, token, "/api/executor/passo",
                     {"comando_id": cid, "screenshot": tela.capturar_b64(), "tool_use_id": tool_use_id})
        if resp.get("fim"):
            print(f"  ■ {resp.get('status')}: {resp.get('resumo')}")
            return
        acao, tool_use_id = resp["acao"], resp["tool_use_id"]
        print("  →", {k: v for k, v in acao.items() if k != "text"} if acao.get("action") == "type" else acao)
        try:
            executar(pg, tela, acao)
        except ValueError as e:
            _post(servidor, token, "/api/executor/fim", {"comando_id": cid, "status": "falhou", "resumo": str(e)})
            return
        time.sleep(config.EXECUTOR_PAUSA_ACAO)


def main():
    ap = argparse.ArgumentParser(description="Executor local do TaskMiner")
    ap.add_argument("--servidor", required=True)
    ap.add_argument("--token", required=True)
    ap.add_argument("--intervalo", type=float, default=5, help="segundos entre consultas ao servidor")
    a = ap.parse_args()
    pg = _pyautogui()
    tela = Tela(pg)
    print(f"Executor ligado ({tela.w}x{tela.h}). Para parar: Ctrl+C, ou mouse num canto da tela.")
    aviso = None
    while True:
        try:
            r = _post(a.servidor, a.token, "/api/executor/proximo", {}, timeout=30)
            aviso = None
            if r.get("comando"):
                rodar_comando(a.servidor, a.token, pg, tela, r["comando"])
                continue
        except (ConnectionError, ErroServidor) as e:
            if str(e) != aviso:
                print("Aviso:", e)
            aviso = str(e)
        except pg.FailSafeException:
            print("\n⛔ Interrompido: mouse no canto da tela.")
            return
        except KeyboardInterrupt:
            print("\nExecutor encerrado.")
            return
        try:
            time.sleep(a.intervalo)
        except KeyboardInterrupt:
            print("\nExecutor encerrado.")
            return


if __name__ == "__main__":
    main()

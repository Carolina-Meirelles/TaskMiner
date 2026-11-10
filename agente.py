"""Agente de coleta para Windows.

Registra, durante o período configurado (padrão: 14 dias):
  - qual janela/aplicativo está em uso e quando o colaborador troca de janela;
  - cliques, com o NOME do botão/campo clicado (via UI Automation do Windows);
  - atalhos de teclado (Ctrl+C, Ctrl+S...) e teclas como Enter/Tab;
  - QUANTOS caracteres foram digitados e em qual campo (nunca O QUE foi digitado);
  - períodos de ociosidade.

Atalho global Ctrl+Alt+P pausa/retoma a coleta a qualquer momento.
"""
import contextlib
import ctypes
import getpass
import queue
import re
import sys
import threading
import time
from datetime import datetime

import config
import db
import sistemas
from privacidade import mascarar, titulo_sensivel

TERMO_CONSENTIMENTO = (
    "TERMO DE CIÊNCIA E CONSENTIMENTO — MAPEAMENTO DE PROCESSOS\n\n"
    "Este programa vai registrar, por {dias} dias, quais aplicativos, janelas e sistemas você usa "
    "(nos navegadores, apenas o domínio do site, ex.: crm.empresa.com.br), os botões e campos em que "
    "você clica e os atalhos de teclado utilizados, com o objetivo exclusivo de documentar os "
    "processos da sua função.\n\n"
    "O que NÃO é registrado: o endereço completo das páginas, o conteúdo do que você digita (apenas a quantidade de caracteres), "
    "senhas, capturas de tela, e-mails/CPFs/telefones que apareçam em títulos (são mascarados), "
    "nem janelas de navegação anônima ou gerenciadores de senha.\n\n"
    "Você pode pausar a coleta a qualquer momento com Ctrl+Alt+P. Os dados ficam armazenados "
    "localmente e você pode pedir sua exclusão (LGPD, art. 18).\n\n"
    "Você concorda em participar?"
)

ATALHOS_CONHECIDOS = {
    "C": "Copiar", "V": "Colar", "X": "Recortar", "S": "Salvar", "Z": "Desfazer",
    "Y": "Refazer", "F": "Localizar", "P": "Imprimir", "N": "Novo", "A": "Selecionar tudo",
    "T": "Nova aba", "W": "Fechar", "R": "Responder", "ENTER": "Enviar", "O": "Abrir",
}


def _verificar_windows():
    if sys.platform != "win32":
        sys.exit(
            "O agente de coleta roda apenas no Windows.\n"
            "Para testar o projeto em outro sistema, gere dados de exemplo com: python main.py simular"
        )


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def segundos_ocioso():
    info = _LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
    return (ctypes.windll.kernel32.GetTickCount() - info.dwTime) / 1000.0


class Agente:
    def __init__(self, usuario):
        import psutil
        import win32gui
        import win32process
        self._psutil, self._win32gui, self._win32process = psutil, win32gui, win32process

        self.usuario = usuario
        self.fila_eventos = queue.Queue()
        self.fila_cliques = queue.Queue()
        self.rodando = True
        self.pausado = False
        self.ocioso = False

        self.janela_bruta = (None, None)      # usado só para detectar troca de janela
        self.janela_reg = (None, None)        # versão mascarada que vai para o banco
        self.janela_protegida = False

        self.modificadores = set()
        self.digitados = 0
        self.inicio_digitacao = None
        self.ultimo_campo = None
        self._trava = threading.Lock()
        self._cache_produto = {}
        self._auto = None
        if config.CAPTURAR_SITES:
            try:
                import uiautomation as auto
                auto.SetGlobalSearchTimeout(1)
                self._auto = auto
            except ImportError:
                print("Aviso: 'uiautomation' não instalado; os sites serão identificados só pelo título da aba.")

    # ------------------------------------------------------------------ registro
    def registrar(self, tipo, app=None, titulo=None, detalhe=None, ts=None):
        if self.pausado and tipo not in ("pausa", "retomada"):
            return
        self.fila_eventos.put((ts or time.time(), tipo, app, titulo, detalhe))

    def _gravador(self):
        """Única thread que escreve no SQLite (grava em lotes)."""
        con = db.conectar()
        while self.rodando or not self.fila_eventos.empty():
            try:
                lote = [self.fila_eventos.get(timeout=1)]
            except queue.Empty:
                continue
            while len(lote) < 500:
                try:
                    lote.append(self.fila_eventos.get_nowait())
                except queue.Empty:
                    break
            for ts, tipo, app, titulo, det in lote:
                db.inserir_evento(con, ts, self.usuario, tipo, app, titulo, det)
            con.commit()
        con.close()

    # ------------------------------------------------------------------ janela ativa
    def _janela_ativa(self):
        hwnd = self._win32gui.GetForegroundWindow()
        if not hwnd:
            return None, None
        titulo = self._win32gui.GetWindowText(hwnd)
        _, pid = self._win32process.GetWindowThreadProcessId(hwnd)
        try:
            proc = self._psutil.Process(pid)
            app = proc.name().lower()
            self._ultimo = (hwnd, proc)
        except Exception:
            app = "desconhecido"
            self._ultimo = (hwnd, None)
        return app, titulo

    def _endereco_navegador(self, hwnd):
        """Lê o endereço na barra do navegador (UI Automation) e devolve só (domínio, 1º trecho)."""
        if not self._auto:
            return None, None
        try:
            janela = self._auto.ControlFromHandle(hwnd)
            barra = None
            for nome in config.NOMES_BARRA_ENDERECO:
                c = janela.EditControl(searchDepth=14, Name=nome)
                if c.Exists(0, 0):
                    barra = c
                    break
            if barra is None:                       # reserva: campo da barra de ferramentas (raso, fora da página)
                c = janela.EditControl(searchDepth=8, foundIndex=1)
                barra = c if c.Exists(0, 0) else None
            if barra is None:
                return None, None
            valor = barra.GetValuePattern().Value or ""
            if not re.match(r"^(https?://)?[\w.-]+\.[a-z]{2,}(:\d+)?(/|$)", valor.strip(), re.I):
                return None, None                   # não é endereço (ex.: o usuário digitando uma busca)
            return sistemas.reduzir_endereco(valor)
        except Exception:
            return None, None

    def _produto(self, proc):
        """Nome do produto gravado no .exe (ex.: 'TOTVS SmartClient'), para programas desconhecidos."""
        if proc is None:
            return None
        try:
            caminho = proc.exe()
        except Exception:
            return None
        if caminho in self._cache_produto:
            return self._cache_produto[caminho]
        nome = None
        try:
            import win32api
            lingua, pagina = win32api.GetFileVersionInfo(caminho, "\\VarFileInfo\\Translation")[0]
            for campo in ("ProductName", "FileDescription"):
                v = win32api.GetFileVersionInfo(caminho, f"\\StringFileInfo\\{lingua:04X}{pagina:04X}\\{campo}")
                if v and v.strip():
                    nome = v.strip()[:60]
                    break
        except Exception:
            pass
        self._cache_produto[caminho] = nome
        return nome

    def _verificar_janela(self):
        app, titulo = self._janela_ativa()
        if app is None or (app, titulo) == self.janela_bruta:
            return
        self._descarregar_digitacao()
        self.janela_bruta = (app, titulo)
        ignorado = app in config.APPS_IGNORADOS
        sensivel = titulo_sensivel(titulo)
        self.janela_protegida = ignorado or sensivel
        if ignorado:
            titulo_reg = "[aplicativo ignorado]"
        elif sensivel:
            titulo_reg = "[conteúdo oculto]"
        else:
            titulo_reg = mascarar(titulo)
        self.janela_reg = (app, titulo_reg)
        self.ultimo_campo = None
        detalhe = None
        if not self.janela_protegida:
            hwnd, proc = getattr(self, "_ultimo", (None, None))
            if app in sistemas.NAVEGADORES:
                dominio, trecho = self._endereco_navegador(hwnd)
                if dominio and dominio not in config.DOMINIOS_IGNORADOS:
                    detalhe = {"dominio": dominio, "trecho": trecho}
            elif app not in sistemas.PROGRAMAS:
                produto = self._produto(proc)
                if produto:
                    detalhe = {"produto": mascarar(produto)}
        self.registrar("foco", app, titulo_reg, detalhe)

    # ------------------------------------------------------------------ teclado
    def _descarregar_digitacao(self):
        with self._trava:
            if self.digitados > 0:
                self.registrar("digitacao", *self.janela_reg,
                               {"caracteres": self.digitados, "campo": self.ultimo_campo},
                               ts=self.inicio_digitacao)
            self.digitados = 0
            self.inicio_digitacao = None

    def _nome_modificador(self, tecla):
        from pynput.keyboard import Key
        if tecla in (Key.ctrl, Key.ctrl_l, Key.ctrl_r):
            return "Ctrl"
        if tecla in (Key.alt, Key.alt_l, Key.alt_r, Key.alt_gr):
            return "Alt"
        if tecla in (Key.shift, Key.shift_l, Key.shift_r):
            return "Shift"
        return None

    def _ao_pressionar(self, tecla):
        from pynput.keyboard import Key, KeyCode
        mod = self._nome_modificador(tecla)
        if mod:
            self.modificadores.add(mod)
            return

        letra = None
        if isinstance(tecla, KeyCode):
            vk = getattr(tecla, "vk", None)
            if vk and (48 <= vk <= 57 or 65 <= vk <= 90):
                letra = chr(vk)
            elif tecla.char and tecla.char.isprintable():
                letra = tecla.char.upper()

        if {"Ctrl", "Alt"} <= self.modificadores and letra == "P":
            self._alternar_pausa()
            return
        if self.pausado or self.janela_reg[0] in config.APPS_IGNORADOS:
            return

        if self.modificadores & {"Ctrl", "Alt"}:
            nome = letra or (tecla.name.upper() if isinstance(tecla, Key) else "?")
            combo = "+".join(m for m in ("Ctrl", "Alt", "Shift") if m in self.modificadores) + "+" + nome
            acao = ATALHOS_CONHECIDOS.get(nome) if self.modificadores == {"Ctrl"} else None
            self._descarregar_digitacao()
            self.registrar("atalho", *self.janela_reg, {"combinacao": combo, "acao": acao})
            return

        especiais = {Key.enter: "Enter", Key.tab: "Tab", Key.esc: "Esc", Key.f5: "F5", Key.delete: "Delete"}
        if tecla in especiais:
            self._descarregar_digitacao()
            self.registrar("tecla", *self.janela_reg, {"tecla": especiais[tecla]})
            return

        if isinstance(tecla, KeyCode) or tecla in (Key.space, Key.backspace):
            with self._trava:
                if self.digitados == 0:
                    self.inicio_digitacao = time.time()
                self.digitados += 1

    def _ao_soltar(self, tecla):
        mod = self._nome_modificador(tecla)
        if mod:
            self.modificadores.discard(mod)

    def _alternar_pausa(self):
        if self.pausado:
            self.pausado = False
            self.janela_bruta = (None, None)  # força registrar a janela atual de novo
            self.registrar("retomada")
            print(f"[{datetime.now():%H:%M}] Coleta RETOMADA.")
        else:
            self._descarregar_digitacao()
            self.registrar("pausa")
            self.pausado = True
            print(f"[{datetime.now():%H:%M}] Coleta PAUSADA (Ctrl+Alt+P para retomar).")

    # ------------------------------------------------------------------ mouse
    def _ao_clicar(self, x, y, botao, pressionado):
        if not pressionado or self.pausado or self.ocioso:
            return
        if self.janela_reg[0] in config.APPS_IGNORADOS:
            return
        self._descarregar_digitacao()
        self.fila_cliques.put((time.time(), x, y, str(botao).replace("Button.", ""),
                               self.janela_reg, self.janela_protegida))

    def _resolvedor_cliques(self):
        """Descobre qual botão/campo está sob o mouse (UI Automation) e registra o clique."""
        auto = None
        if config.CAPTURAR_ELEMENTOS_CLICADOS:
            try:
                import uiautomation as auto
            except ImportError:
                print("Aviso: 'uiautomation' não instalado; cliques serão registrados sem o nome do elemento.")
        ctx = auto.UIAutomationInitializerInThread() if auto else contextlib.nullcontext()
        with ctx:
            while self.rodando:
                try:
                    ts, x, y, botao, (app, titulo), protegido = self.fila_cliques.get(timeout=1)
                except queue.Empty:
                    continue
                detalhe = {"botao": botao}
                if auto and not protegido:
                    try:
                        c = auto.ControlFromPoint(x, y)
                        if c:
                            tipo = c.ControlTypeName.replace("Control", "")
                            senha = bool(getattr(c, "IsPassword", False))
                            nome = "" if senha else mascarar((c.Name or "").strip())[:80]
                            detalhe.update(tipo_elemento=tipo, elemento=nome)
                            if senha:
                                detalhe["campo_senha"] = True
                            if tipo in ("Edit", "ComboBox", "Document", "DataItem"):
                                self.ultimo_campo = "[campo de senha]" if senha else (nome or tipo)
                    except Exception:
                        pass
                self.registrar("clique", app, titulo, detalhe, ts=ts)

    # ------------------------------------------------------------------ laço principal
    def executar(self, fim_ts, enviador=None):
        from pynput import keyboard, mouse

        threads = [threading.Thread(target=self._gravador, daemon=True),
                   threading.Thread(target=self._resolvedor_cliques, daemon=True)]
        for t in threads:
            t.start()
        if enviador:
            enviador.start()
        ouvinte_mouse = mouse.Listener(on_click=self._ao_clicar)
        ouvinte_teclado = keyboard.Listener(on_press=self._ao_pressionar, on_release=self._ao_soltar)
        ouvinte_mouse.start()
        ouvinte_teclado.start()

        try:
            while time.time() < fim_ts:
                if not self.pausado:
                    parado = segundos_ocioso()
                    if parado >= config.LIMITE_OCIOSO and not self.ocioso:
                        self._descarregar_digitacao()
                        self.registrar("ocioso", ts=time.time() - parado)
                        self.ocioso = True
                    elif parado < config.LIMITE_OCIOSO and self.ocioso:
                        self.ocioso = False
                        self.registrar("ativo")
                        self.janela_bruta = (None, None)
                    if not self.ocioso:
                        self._verificar_janela()
                time.sleep(config.INTERVALO_VERIFICACAO)
            print("Período de coleta concluído! Rode: python main.py analisar")
        except KeyboardInterrupt:
            print("\nColeta interrompida pelo usuário. Ela continua de onde parou na próxima execução.")
        finally:
            self._descarregar_digitacao()
            ouvinte_mouse.stop()
            ouvinte_teclado.stop()
            self.rodando = False
            threads[0].join(timeout=10)
            if enviador:
                enviador.parar()
                enviador.join(timeout=30)


def _pedir_consentimento(texto):
    """Caixa de diálogo do Windows (funciona mesmo rodando com pythonw, sem console)."""
    MB_YESNO, MB_ICONQUESTION, IDYES = 0x04, 0x20, 6
    return ctypes.windll.user32.MessageBoxW(0, texto, "TaskMiner — Consentimento", MB_YESNO | MB_ICONQUESTION) == IDYES


def iniciar(usuario=None, dias=None, servidor=None, token=None):
    """Inicia (ou retoma) a coleta.

    Com --servidor e --token (o código pessoal mostrado no painel), os eventos também são
    enviados ao servidor da empresa. Os dois ficam salvos: nas próximas vezes basta
    `python main.py coletar`.
    """
    _verificar_windows()
    import envio

    usuario = usuario or getpass.getuser()
    dias = dias or config.DIAS_DE_COLETA
    con = db.conectar()

    if servidor and token:
        db.set_meta(con, "servidor", servidor.rstrip("/"))
        db.set_meta(con, "token", token)
    servidor, token = db.get_meta(con, "servidor"), db.get_meta(con, "token")

    texto = TERMO_CONSENTIMENTO.format(dias=dias)
    if not db.tem_consentimento(con, usuario):
        if not _pedir_consentimento(texto):
            sys.exit("Coleta cancelada: o colaborador não deu consentimento.")
        db.registrar_consentimento(con, usuario, texto)

    enviador = None
    if servidor and token:
        try:
            nome = envio.registrar_consentimento(servidor, token, texto)
            print(f"Conectado ao servidor {servidor} como {nome}.")
        except envio.ErroServidor as e:
            sys.exit(f"O servidor recusou o código de coleta: {e}\nConfira o comando na página 'Minha coleta' do painel.")
        except ConnectionError as e:
            print(f"Aviso: {e}\nA coleta continua e os dados serão enviados quando o servidor estiver acessível.")
        enviador = envio.Enviador(servidor, token, usuario)
    else:
        print("Modo local: os dados ficam só neste computador (sem --servidor/--token).")

    chave = f"inicio_coleta:{usuario}"
    inicio = float(db.get_meta(con, chave) or 0)
    if not inicio:
        inicio = time.time()
        db.set_meta(con, chave, inicio)
    fim = inicio + dias * 86400
    con.close()

    if time.time() >= fim:
        print("O período de coleta deste colaborador já terminou.")
        if enviador:
            enviador.parar()
            enviador.run()  # envia o que tiver ficado pendente
        return
    print(f"Coletando atividades de '{usuario}' até {datetime.fromtimestamp(fim):%d/%m/%Y %H:%M}.")
    print("Ctrl+Alt+P pausa/retoma. Ctrl+C neste terminal encerra (a coleta continua na próxima execução).")
    Agente(usuario).executar(fim, enviador)

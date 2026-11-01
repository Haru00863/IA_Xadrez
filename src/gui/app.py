"""Janela principal e controle da partida.

Liga o tabuleiro, as regras (core), o motor de IA e o banco.
"""

from __future__ import annotations

import queue
import sqlite3
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Optional

from src.core.core_logic import BRANCAS, PRETAS, ChessBoardCore, FimDeJogo, ResultadoJogada
from src.engine import MOTORES, MotorDecisao, criar_motor, motor_por_nome
from src.persistence import database_manager as banco

from . import tema
from .dialogos import (SEM_IA, ConfiguracaoPartida, DialogoAtalhos, DialogoNovaPartida,
                       DialogoPromocao)
from .historico import (JanelaHistorico, criar_lista_lances, formatar_data, marcar_linha_atual,
                        preencher_lances)
from .sprites import Sprites
from .tabuleiro import TabuleiroCanvas

TEMPO_LIMITE_IA = 10.0  # segundos
ATRASO_MINIMO_IA = 0.45  # para o lance da IA não aparecer instantâneo
INTERVALO_IA_MS = 50  # frequência de consulta da fila da IA


def _segundos(valor: float) -> str:
    """1.234 -> '1,2 s'."""
    return f"{valor:.1f}".replace(".", ",") + " s"


def _outra(cor: str) -> str:
    return PRETAS if cor == BRANCAS else BRANCAS


class CartaoJogador(tk.Frame):
    """Cartão de um jogador: cor, quem joga, capturas e de quem é a vez."""

    def __init__(self, pai: tk.Misc, sprites: Sprites, fontes: tema.Fontes):
        super().__init__(pai, bg=tema.SUPERFICIE, highlightthickness=1,
                         highlightbackground=tema.LINHA)
        self._sprites = sprites
        self._barra = tk.Frame(self, width=5, bg=tema.SUPERFICIE)
        self._barra.pack(side="left", fill="y")
        self._conteudo = tk.Frame(self, bg=tema.SUPERFICIE, padx=12, pady=8)
        self._conteudo.pack(side="left", fill="both", expand=True)

        linha = tk.Frame(self._conteudo, bg=tema.SUPERFICIE)
        linha.pack(fill="x")
        self._cor = tk.Label(linha, font=fontes.titulo, bg=tema.SUPERFICIE, fg=tema.TINTA)
        self._cor.pack(side="left")
        self._vantagem = tk.Label(linha, font=fontes.forte, bg=tema.SUPERFICIE,
                                  fg=tema.TINTA_SUAVE)
        self._vantagem.pack(side="right")
        self._papel = tk.Label(self._conteudo, font=fontes.base, bg=tema.SUPERFICIE,
                               fg=tema.TINTA_SUAVE, anchor="w")
        self._papel.pack(fill="x")
        self._capturas = tk.Canvas(self._conteudo, bg=tema.SUPERFICIE, height=26,
                                   highlightthickness=0, width=240)
        self._capturas.pack(fill="x", pady=(4, 0))
        self._fonte_suave = fontes.pequena
        self._status = tk.Label(self._conteudo, font=fontes.forte, bg=tema.SUPERFICIE,
                                fg=tema.ACENTO, anchor="w")
        self._status.pack(fill="x")
        self._fundo_atual = tema.SUPERFICIE

    def atualizar(self, *, cor: str, papel: str, capturas: list[str], vantagem: int,
                  ativo: bool, status: str, cor_status: str = tema.ACENTO) -> None:
        fundo = tema.SUPERFICIE_ATIVA if ativo else tema.SUPERFICIE
        self._barra.configure(bg=tema.ACENTO if ativo else tema.SUPERFICIE)
        self.configure(highlightbackground=tema.ACENTO if ativo else tema.LINHA)
        for widget in (self._conteudo, self._cor, self._vantagem, self._papel, self._capturas,
                       self._status, self._cor.master):
            widget.configure(bg=fundo)
        self._cor.configure(text=cor.capitalize())
        self._papel.configure(text=papel)
        self._vantagem.configure(text=f"+{vantagem}" if vantagem > 0 else "")
        self._status.configure(text=status, fg=cor_status)

        self._capturas.delete("all")
        tamanho = self._sprites.tamanhos[0]
        passo = tamanho * 0.62
        for i, simbolo in enumerate(capturas):
            self._capturas.create_image(i * passo, 13, anchor="w",
                                        image=self._sprites.imagem(simbolo, tamanho))
        if not capturas:
            self._capturas.create_text(0, 13, anchor="w", text="Nenhuma captura",
                                       fill=tema.TINTA_SUAVE, font=self._fonte_suave)


class AplicacaoXadrez:
    def __init__(self, raiz: tk.Tk):
        self.raiz = raiz
        self.fontes = tema.aplicar_estilo(raiz)
        self.sprites = Sprites(raiz)
        raiz.title("IA em Xadrez")
        try:
            raiz.iconphoto(True, self.sprites.imagem("N", self.sprites.tamanho_para(64)))
        except tk.TclError:
            pass

        self.jogo = ChessBoardCore()
        self.config = ConfiguracaoPartida()
        self.motor: Optional[MotorDecisao] = None
        self.partida_id: Optional[int] = None
        self.data_inicio: Optional[str] = None
        self.selecionada: Optional[str] = None
        self._token_ia = 0  # muda a cada partida, para descartar respostas antigas da IA
        self._ia_inicio: Optional[float] = None
        self._after_ia: Optional[str] = None
        self._janela_historico: Optional[JanelaHistorico] = None
        self._banco_ok = True

        self._montar_menu()
        self._montar_interface()
        self._registrar_atalhos()
        raiz.protocol("WM_DELETE_WINDOW", self.sair)

        try:
            banco.criar_banco()
        except (sqlite3.Error, OSError) as erro:
            self._banco_ok = False
            messagebox.showwarning(
                "Banco de dados indisponível",
                f"Não foi possível abrir o banco de partidas:\n{erro}\n\n"
                "Você pode jogar normalmente, mas os lances não serão salvos.", parent=raiz)
        raiz.after(50, self._ao_abrir)

    def _montar_menu(self) -> None:
        barra = tk.Menu(self.raiz)
        partida = tk.Menu(barra)
        partida.add_command(label="Nova partida...", accelerator="Ctrl+N",
                            command=self.nova_partida)
        partida.add_command(label="Continuar partida salva...", command=self.abrir_historico)
        partida.add_separator()
        partida.add_command(label="Desistir", command=self.desistir)
        partida.add_command(label="Reivindicar empate", command=self.reivindicar_empate)
        partida.add_separator()
        partida.add_command(label="Sair", accelerator="Ctrl+Q", command=self.sair)
        barra.add_cascade(label="Partida", menu=partida)

        exibir = tk.Menu(barra)
        exibir.add_command(label="Inverter tabuleiro", accelerator="Ctrl+I",
                           command=self.inverter)
        exibir.add_command(label="Histórico de partidas", accelerator="Ctrl+H",
                           command=self.abrir_historico)
        barra.add_cascade(label="Exibir", menu=exibir)

        ajuda = tk.Menu(barra)
        ajuda.add_command(label="Atalhos de teclado", accelerator="F1",
                          command=lambda: DialogoAtalhos(self.raiz, self.fontes).exibir())
        ajuda.add_command(label="Sobre", command=self._sobre)
        barra.add_cascade(label="Ajuda", menu=ajuda)
        self.raiz.configure(menu=barra)

    def _montar_interface(self) -> None:
        raiz = self.raiz
        altura_tela = raiz.winfo_screenheight()
        lado = max(44, min(88, (altura_tela - 240) // 8))

        # o rodapé entra antes do conteúdo para não ser cortado em janelas baixas
        rodape = ttk.Frame(raiz, padding=(16, 0, 16, 10))
        rodape.pack(side="bottom", fill="x")

        principal = ttk.Frame(raiz, padding=(16, 16, 16, 8))
        principal.pack(side="top", fill="both", expand=True)
        principal.columnconfigure(0, weight=1)
        principal.rowconfigure(0, weight=1)

        self.tabuleiro = TabuleiroCanvas(
            principal, self.sprites, lado_inicial=lado, familia_fonte=self.fontes.familia,
            ao_clicar=self._ao_clicar_casa, ao_soltar=self._ao_soltar,
            pode_arrastar=self._pode_mover, ao_cancelar=self._cancelar_selecao)
        self.tabuleiro.grid(row=0, column=0, sticky="nsew")

        lateral = ttk.Frame(principal, width=320)
        lateral.grid(row=0, column=1, sticky="ns", padx=(16, 0))
        lateral.rowconfigure(2, weight=1)
        lateral.columnconfigure(0, weight=1)

        self.cartao_topo = CartaoJogador(lateral, self.sprites, self.fontes)
        self.cartao_topo.grid(row=0, column=0, sticky="ew")

        estado = ttk.Frame(lateral, style="Painel.TFrame", padding=(12, 10))
        estado.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.lbl_partida = ttk.Label(estado, style="PainelTitulo.TLabel")
        self.lbl_partida.pack(anchor="w")
        self.lbl_detalhes = ttk.Label(estado, style="PainelSuave.TLabel", justify="left")
        self.lbl_detalhes.pack(anchor="w")
        self.lbl_estado = tk.Label(estado, font=self.fontes.forte, bg=tema.SUPERFICIE,
                                   fg=tema.TINTA, anchor="w", justify="left", wraplength=280)
        self.lbl_estado.pack(anchor="w", fill="x", pady=(6, 0))

        moldura_lances, self.lista_lances = criar_lista_lances(lateral, altura=8)
        moldura_lances.grid(row=2, column=0, sticky="nsew", pady=(10, 0))

        entrada = ttk.Frame(lateral)
        entrada.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        entrada.columnconfigure(0, weight=1)
        self.campo_lance = ttk.Entry(entrada)
        self.campo_lance.grid(row=0, column=0, sticky="ew")
        self.campo_lance.bind("<Return>", lambda e: self.jogar_digitado())
        self.campo_lance.bind("<KP_Enter>", lambda e: self.jogar_digitado())
        self.btn_jogar = ttk.Button(entrada, text="Jogar", command=self.jogar_digitado)
        self.btn_jogar.grid(row=0, column=1, padx=(6, 0))
        ttk.Label(entrada, text="Digite um lance: e4, Nf3, O-O ou e2e4.",
                  style="Suave.TLabel").grid(row=1, column=0, columnspan=2, sticky="w",
                                             pady=(3, 0))

        botoes = ttk.Frame(lateral)
        botoes.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        botoes.columnconfigure((0, 1), weight=1, uniform="botoes")
        ttk.Button(botoes, text="Nova partida", style="Acento.TButton",
                   command=self.nova_partida).grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ttk.Button(botoes, text="Inverter tabuleiro", command=self.inverter).grid(
            row=0, column=1, sticky="ew", padx=(3, 0))
        self.btn_desistir = ttk.Button(botoes, text="Desistir", command=self.desistir)
        self.btn_desistir.grid(row=1, column=0, sticky="ew", padx=(0, 3), pady=(6, 0))
        self.btn_empate = ttk.Button(botoes, text="Reivindicar empate",
                                     command=self.reivindicar_empate)
        self.btn_empate.grid(row=1, column=1, sticky="ew", padx=(3, 0), pady=(6, 0))
        ttk.Button(botoes, text="Histórico de partidas", command=self.abrir_historico).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        self.cartao_base = CartaoJogador(lateral, self.sprites, self.fontes)
        self.cartao_base.grid(row=5, column=0, sticky="ew", pady=(10, 0))

        self.lbl_mensagem = tk.Label(rodape, font=self.fontes.base, bg=tema.FUNDO,
                                     fg=tema.TINTA, anchor="w", justify="left")
        self.lbl_mensagem.pack(side="left", fill="x", expand=True)
        self.lbl_salvo = ttk.Label(rodape, style="Suave.TLabel")
        self.lbl_salvo.pack(side="right")

        raiz.update_idletasks()
        raiz.minsize(760, 560)
        largura = 8 * lado + 320 + 16 * 3 + 4
        altura = max(8 * lado + 16 + 8 + 40, raiz.winfo_reqheight())
        altura = min(altura, altura_tela - 80)
        raiz.geometry(f"{largura}x{altura}")

    def _registrar_atalhos(self) -> None:
        for tecla, acao in (("n", self.nova_partida), ("h", self.abrir_historico),
                            ("i", self.inverter), ("q", self.sair),
                            ("l", self._focar_campo_lance)):
            self.raiz.bind(f"<Control-{tecla}>", lambda e, a=acao: (a(), "break")[1])
            self.raiz.bind(f"<Control-{tecla.upper()}>", lambda e, a=acao: (a(), "break")[1])
        self.raiz.bind("<F1>", lambda e: DialogoAtalhos(self.raiz, self.fontes).exibir())

    def _ao_abrir(self) -> None:
        """Oferece retomar a última partida que não foi finalizada."""
        pendente = None
        if self._banco_ok:
            try:
                pendente = banco.buscar_partida_em_andamento()
            except sqlite3.Error:
                pendente = None
        if pendente:
            quer_continuar = messagebox.askyesno(
                "Continuar partida?",
                f"A partida nº {pendente['id']}, iniciada em "
                f"{formatar_data(pendente['data_inicio'])}, não foi finalizada "
                f"({pendente['total_lances']} lances salvos).\n\n"
                "Deseja continuar de onde parou?\n\n"
                "Se escolher Não, ela será marcada como abandonada no histórico.",
                parent=self.raiz)
            if quer_continuar:
                if self.continuar_partida(pendente["id"], perguntar_abandono=False):
                    return
            else:
                self._gravar_resultado(pendente["id"], banco.RESULTADO_ABANDONADA)
        self._iniciar(ConfiguracaoPartida())

    def _iniciar(self, config: ConfiguracaoPartida, partida_id: Optional[int] = None,
                 lances: tuple[str, ...] | list[str] = ()) -> None:
        """Começa uma partida nova ou retoma uma salva."""
        self._cancelar_ia()
        self.config = config
        self.motor = criar_motor(config.motor_chave) if config.contra_ia else None
        self.jogo = ChessBoardCore()
        self.selecionada = None
        self.data_inicio = None

        retomada = partida_id is not None
        if lances:
            _, erro = self.jogo.carregar_lances(list(lances))
            if erro:
                messagebox.showwarning("Partida incompleta", erro, parent=self.raiz)

        if self._banco_ok:
            try:
                if retomada:
                    banco.atualizar_dificuldade(partida_id, config.rotulo_banco)
                else:
                    partida_id = banco.iniciar_nova_partida(config.rotulo_banco)
                registro = banco.obter_partida(partida_id)
                self.data_inicio = registro["data_inicio"] if registro else None
            except sqlite3.Error as erro:
                self._mensagem(f"Não foi possível registrar a partida no banco: {erro}", erro=True)
                partida_id = None
        self.partida_id = partida_id

        self.tabuleiro.ocultar_sobreposicao()
        self.tabuleiro.definir_invertido(config.contra_ia and config.cor_humano == PRETAS)
        self._atualizar_tela()
        self._atualizar_salvamento()
        self.tabuleiro.focus_set()

        numero = f"nº {partida_id}" if partida_id else "sem registro"
        if retomada:
            self._mensagem(f"Partida {numero} retomada com {self.jogo.total_meios_lances()} "
                           "lances.")
        else:
            self._mensagem(f"Partida {numero} iniciada. "
                           + ("Você joga com as " + config.cor_humano + "."
                              if config.contra_ia else "Brancas começam."))

        fim = self.jogo.estado_fim()
        if fim:
            self._finalizar(fim)
        elif self._vez_da_ia():
            self._agendar_ia()

    def nova_partida(self) -> None:
        if not self._confirmar_abandono():
            return
        config = DialogoNovaPartida(self.raiz, self.fontes, inicial=self.config).perguntar()
        if config is None:
            return
        self._abandonar_atual()
        self._iniciar(config)

    def continuar_partida(self, partida_id: int, perguntar_abandono: bool = True) -> bool:
        """Retoma uma partida 'Em andamento' (também usado pelo histórico)."""
        try:
            registro = banco.obter_partida(partida_id)
            lances = banco.obter_jogadas(partida_id)
        except sqlite3.Error as erro:
            self._mensagem(f"Não foi possível ler a partida: {erro}", erro=True)
            return False
        if registro is None:
            return False
        if perguntar_abandono and partida_id != self.partida_id and not self._confirmar_abandono():
            return False

        rotulo = registro["dificuldade_ia"] or ""
        classe = motor_por_nome(rotulo)
        if rotulo == SEM_IA:
            inicial = ConfiguracaoPartida(contra_ia=False)
        elif classe is not None:
            inicial = ConfiguracaoPartida(contra_ia=True, motor_chave=classe.chave)
        else:
            inicial = ConfiguracaoPartida()
        config = DialogoNovaPartida(
            self.raiz, self.fontes, titulo=f"Continuar partida nº {partida_id}",
            texto_botao="Continuar partida", inicial=inicial,
            aviso=f"{len(lances)} lances salvos. Confirme o adversário e a sua cor "
                  "para retomar de onde parou.").perguntar()
        if config is None:
            return False
        if partida_id != self.partida_id:
            self._abandonar_atual()
        self._iniciar(config, partida_id=partida_id, lances=lances)
        return True

    def _partida_em_andamento(self) -> bool:
        return self.partida_id is not None and self.jogo.estado_fim() is None

    def _confirmar_abandono(self) -> bool:
        if not self._partida_em_andamento() or self.jogo.total_meios_lances() == 0:
            return True
        return messagebox.askyesno(
            "Abandonar a partida atual?",
            f"A partida nº {self.partida_id} ainda não terminou.\n\n"
            "Se continuar, ela ficará registrada como abandonada no histórico.",
            parent=self.raiz)

    def _abandonar_atual(self) -> None:
        if self._partida_em_andamento():
            self._cancelar_ia()
            self._gravar_resultado(self.partida_id, banco.RESULTADO_ABANDONADA)

    def sair(self) -> None:
        """Partidas com lances continuam 'Em andamento' para serem retomadas; sem lances, ficam
        como abandonadas.
        """
        if self._partida_em_andamento() and self.jogo.total_meios_lances() == 0:
            self._gravar_resultado(self.partida_id, banco.RESULTADO_ABANDONADA)
        self._cancelar_ia()
        self.raiz.destroy()

    def _vez_da_ia(self) -> bool:
        return (self.config.contra_ia and self.motor is not None
                and self.jogo.estado_fim() is None
                and self.jogo.vez() != self.config.cor_humano)

    def _vez_do_humano(self) -> bool:
        return self.jogo.estado_fim() is None and not self._vez_da_ia()

    def _pode_mover(self, casa: str) -> bool:
        return self._vez_do_humano() and self.jogo.cor_em(casa) == self.jogo.vez()

    def _ao_clicar_casa(self, casa: str) -> None:
        if self.jogo.estado_fim() is not None:
            self._mensagem("A partida terminou. Use Nova partida para jogar outra.")
            return
        if not self._vez_do_humano():
            self._mensagem("Aguarde: é a vez da IA.")
            return

        vez = self.jogo.vez()
        cor = self.jogo.cor_em(casa)
        if self.selecionada is None:
            if cor is None:
                return
            if cor != vez:
                self.tabuleiro.piscar_erro(casa)
                self._mensagem(f"Essa peça é das {cor}. Agora é a vez das {vez}.", erro=True)
                return
            self._selecionar(casa)
        elif casa == self.selecionada:
            self._cancelar_selecao()
        elif cor == vez:
            self._selecionar(casa)
        else:
            self._tentar_lance(self.selecionada, casa)

    def _ao_soltar(self, origem: str, destino: str) -> None:
        if not self._pode_mover(origem):
            self._atualizar_tela()
            return
        self.selecionada = origem
        self._tentar_lance(origem, destino)

    def _selecionar(self, casa: str) -> None:
        self.selecionada = casa
        if not self.jogo.destinos_legais(casa):
            self._mensagem(f"A peça em {casa} não tem lances legais nesta posição.", erro=True)
        else:
            self._mensagem("")
        self._atualizar_tela()

    def _cancelar_selecao(self) -> None:
        if self.selecionada:
            self.selecionada = None
            self._atualizar_tela()

    def _tentar_lance(self, origem: str, destino: str) -> None:
        promocao = None
        if self.jogo.exige_promocao(origem, destino):
            promocao = DialogoPromocao(self.raiz, self.sprites, self.fontes,
                                       self.jogo.vez()).perguntar()
            if promocao is None:
                self._mensagem("Promoção cancelada. A peça continua selecionada.")
                self._atualizar_tela()
                return
        resultado = self.jogo.jogar(origem, destino, promocao)
        if not resultado.valido:
            self._recusar(resultado, destino)
            return
        self._concluir_lance(resultado, avaliacao=None)

    def jogar_digitado(self) -> None:
        texto = self.campo_lance.get()
        if self.jogo.estado_fim() is not None:
            self._mensagem("A partida terminou. Use Nova partida para jogar outra.")
            return
        if not self._vez_do_humano():
            self._mensagem("Aguarde: é a vez da IA.")
            return
        resultado = self.jogo.jogar_texto(texto)
        if not resultado.valido:
            self._recusar(resultado, resultado.destino)
            return
        self.campo_lance.delete(0, "end")
        self._concluir_lance(resultado, avaliacao=None)

    def _recusar(self, resultado: ResultadoJogada, casa: Optional[str]) -> None:
        """Lance ilegal: a casa pisca e o motivo aparece no rodapé."""
        self.selecionada = None
        self._atualizar_tela()
        self.tabuleiro.piscar_erro(casa)
        self._mensagem(resultado.mensagem, erro=True)
        self.raiz.bell()

    def _focar_campo_lance(self) -> None:
        self.campo_lance.focus_set()
        self.campo_lance.select_range(0, "end")

    def _concluir_lance(self, resultado: ResultadoJogada, avaliacao: Optional[float]) -> None:
        """Comum aos lances do usuário e da IA: salva, redesenha, verifica o fim e passa a vez."""
        cor_que_jogou = _outra(self.jogo.vez())  # depois do lance a vez já mudou
        autor_ia = self.config.contra_ia and cor_que_jogou != self.config.cor_humano
        self.selecionada = None
        self._salvar_lance(resultado.san, avaliacao)
        self._atualizar_tela()

        if self.config.contra_ia:
            quem = "A IA jogou" if autor_ia else "Você jogou"
        else:
            quem = f"As {cor_que_jogou} jogaram"
        self._mensagem(f"{quem} {resultado.san}.")

        fim = self.jogo.estado_fim()
        if fim:
            self._finalizar(fim)
        elif self._vez_da_ia():
            self._agendar_ia()

    def _salvar_lance(self, san: str, avaliacao: Optional[float]) -> None:
        if self.partida_id is None:
            self._atualizar_salvamento()
            return
        try:
            banco.salvar_jogada(self.partida_id, san,
                                None if avaliacao is None else str(avaliacao))
        except sqlite3.Error as erro:
            self._mensagem(f"O lance foi feito, mas não pôde ser salvo: {erro}", erro=True)
            self.lbl_salvo.configure(text="Falha ao salvar", foreground=tema.ERRO)
            return
        self._atualizar_salvamento(agora=True)

    def _finalizar(self, fim: FimDeJogo) -> None:
        self._cancelar_ia()
        self.selecionada = None
        if self.partida_id is not None:
            self._gravar_resultado(self.partida_id, fim.resultado_banco)
        self._atualizar_tela()

        if self.config.contra_ia:
            if fim.vencedor is None:
                titulo = "Empate"
            elif fim.vencedor == self.config.cor_humano:
                titulo = "Você venceu"
            else:
                titulo = "A IA venceu"
        else:
            titulo = "Empate" if fim.vencedor is None else f"Vitória das {fim.vencedor}"
        self.tabuleiro.mostrar_sobreposicao(titulo, f"Por {fim.motivo}.")
        self._mensagem(f"Partida encerrada. {fim.descricao} Resultado gravado no histórico.")

    def _gravar_resultado(self, partida_id: int, resultado: str) -> None:
        try:
            banco.finalizar_partida(partida_id, resultado)
        except sqlite3.Error as erro:
            self._mensagem(f"Não foi possível gravar o resultado: {erro}", erro=True)

    def desistir(self) -> None:
        if not self._partida_em_andamento():
            return
        cor = self.config.cor_humano if self.config.contra_ia else self.jogo.vez()
        if not messagebox.askyesno(
                "Desistir da partida?",
                f"As {cor} abandonam a partida e a vitória vai para as {_outra(cor)}.",
                parent=self.raiz):
            return
        self._finalizar(self.jogo.desistir(cor))

    def reivindicar_empate(self) -> None:
        motivo = self.jogo.motivo_empate_reivindicavel()
        if motivo is None or not self._vez_do_humano():
            self._mensagem("Não há empate a reivindicar agora. É possível pela repetição tripla "
                           "da posição ou pela regra dos 50 lances.")
            return
        if messagebox.askyesno("Reivindicar empate?",
                               f"A posição permite reivindicar empate por {motivo}. "
                               "Encerrar a partida empatada?", parent=self.raiz):
            fim = self.jogo.reivindicar_empate()
            if fim:
                self._finalizar(fim)

    def _agendar_ia(self) -> None:
        """Roda o motor em uma thread e acompanha a resposta pela fila, sem travar a janela."""
        self._cancelar_ia()
        token = self._token_ia
        motor = self.motor
        # o motor recebe uma cópia; o tabuleiro oficial fica no core
        tabuleiro = self.jogo.copia_tabuleiro()
        fila: queue.Queue = queue.Queue()

        def trabalhar():
            try:
                fila.put(("ok", motor.escolher_jogada(tabuleiro, TEMPO_LIMITE_IA)))
            except Exception as erro:  # qualquer falha do motor vira mensagem na interface
                fila.put(("erro", erro))

        threading.Thread(target=trabalhar, name="motor-ia", daemon=True).start()
        self._ia_inicio = time.monotonic()
        self._atualizar_tela()
        self._after_ia = self.raiz.after(INTERVALO_IA_MS, self._verificar_ia, fila, token)

    def _cancelar_ia(self) -> None:
        """Descarta o cálculo em andamento: a thread não é interrompida, mas a resposta é ignorada.
        """
        self._token_ia += 1
        self._ia_inicio = None
        if self._after_ia is not None:
            try:
                self.raiz.after_cancel(self._after_ia)
            except tk.TclError:
                pass
            self._after_ia = None

    def _verificar_ia(self, fila: queue.Queue, token: int) -> None:
        self._after_ia = None
        # a partida mudou: descarta a resposta
        if token != self._token_ia or self._ia_inicio is None:
            return
        decorrido = time.monotonic() - self._ia_inicio
        try:
            if decorrido < ATRASO_MINIMO_IA:
                raise queue.Empty
            tipo, valor = fila.get_nowait()
        except queue.Empty:
            self._atualizar_cartoes()
            self._after_ia = self.raiz.after(INTERVALO_IA_MS, self._verificar_ia, fila, token)
            return

        self._ia_inicio = None
        if tipo == "erro":
            self._atualizar_tela()
            self._mensagem(f"O motor de IA falhou: {valor}", erro=True)
            return
        if decorrido > TEMPO_LIMITE_IA:
            self._mensagem(f"A IA levou {_segundos(decorrido)}, acima do limite de "
                           f"{_segundos(TEMPO_LIMITE_IA)}.", erro=True)
        resultado = self.jogo.aplicar_jogada_motor(valor.movimento)
        if not resultado.valido:
            self._atualizar_tela()
            self._mensagem(resultado.mensagem, erro=True)
            return
        self._concluir_lance(resultado, avaliacao=valor.avaliacao)

    def inverter(self) -> None:
        self.tabuleiro.definir_invertido(not self.tabuleiro.invertido)
        self._atualizar_cartoes()

    def abrir_historico(self) -> None:
        janela = self._janela_historico
        if janela is not None and janela.winfo_exists():
            janela.recarregar()
            janela.lift()
            janela.focus_set()
            return
        self._janela_historico = JanelaHistorico(
            self.raiz, self.sprites, self.fontes, ao_continuar=self.continuar_partida,
            partida_atual=lambda: self.partida_id if self._partida_em_andamento() else None)

    def _sobre(self) -> None:
        messagebox.showinfo(
            "Sobre",
            "IA em Xadrez\n"
            "Projeto Interdisciplinar II, UNIFASIPE (2026)\n"
            "Haru Oltramari Ludwig\n\n"
            "Interface: Tkinter\nRegras: python-chess\n"
            f"Motores de IA registrados: {len(MOTORES)}",
            parent=self.raiz)

    def _mensagem(self, texto: str, erro: bool = False) -> None:
        self.lbl_mensagem.configure(text=texto, fg=tema.ERRO if erro else tema.TINTA)

    def _atualizar_salvamento(self, agora: bool = False) -> None:
        if self.partida_id is None:
            self.lbl_salvo.configure(text="Sem salvamento (banco indisponível)",
                                     foreground=tema.ERRO)
            return
        total = self.jogo.total_meios_lances()
        if agora:
            hora = datetime.now().strftime("%H:%M:%S")
            texto = f"Lance {total} salvo automaticamente às {hora}"
        else:
            texto = f"{total} lances salvos" if total else "Salvamento automático ativo"
        self.lbl_salvo.configure(text=texto, foreground=tema.TINTA_SUAVE)

    def _atualizar_tela(self) -> None:
        destinos = self.jogo.destinos_legais(self.selecionada) if self.selecionada else []
        self.tabuleiro.atualizar(self.jogo.obter_matriz(), selecionada=self.selecionada,
                                 destinos=destinos, ultimo=self.jogo.ultimo_lance(),
                                 xeque=self.jogo.casa_rei_em_xeque())
        lances = self.jogo.lances_san()
        preencher_lances(self.lista_lances, lances)
        marcar_linha_atual(self.lista_lances, (len(lances) + 1) // 2 if lances else None)
        self._atualizar_cartoes()
        self._atualizar_painel_estado()
        self._atualizar_botoes()

    def _papel(self, cor: str) -> str:
        if not self.config.contra_ia:
            return "Jogador humano"
        if cor == self.config.cor_humano:
            return "Você"
        return f"Computador: {self.motor.nome if self.motor else '-'}"

    def _atualizar_cartoes(self) -> None:
        fim = self.jogo.estado_fim()
        capturas = self.jogo.capturas()
        saldo = self.jogo.vantagem_material()
        cor_topo = BRANCAS if self.tabuleiro.invertido else PRETAS
        for cartao, cor in ((self.cartao_topo, cor_topo), (self.cartao_base, _outra(cor_topo))):
            ativo = fim is None and self.jogo.vez() == cor
            cor_status = tema.ACENTO
            if fim is not None:
                status = "Empate" if fim.vencedor is None else (
                    "Venceu" if fim.vencedor == cor else "")
            elif not ativo:
                status = ""
            elif self._ia_inicio is not None:
                status = f"Pensando... {_segundos(time.monotonic() - self._ia_inicio)}"
            elif self.config.contra_ia and cor != self.config.cor_humano:
                status = "Vez da IA"
            else:
                status = "Sua vez" if self.config.contra_ia else "Vez de jogar"
                if self.jogo.em_xeque():
                    status += " (rei em xeque)"
                    cor_status = tema.ERRO
            cartao.atualizar(cor=cor, papel=self._papel(cor), capturas=capturas[cor],
                             vantagem=saldo if cor == BRANCAS else -saldo, ativo=ativo,
                             status=status, cor_status=cor_status)

    def _atualizar_painel_estado(self) -> None:
        if self.partida_id is not None:
            self.lbl_partida.configure(text=f"Partida nº {self.partida_id}")
        else:
            self.lbl_partida.configure(text="Partida sem registro")
        modo = (f"Contra o computador ({self.motor.nome})" if self.config.contra_ia and self.motor
                else "Dois jogadores no mesmo computador")
        inicio = f"Iniciada em {formatar_data(self.data_inicio)}\n" if self.data_inicio else ""
        self.lbl_detalhes.configure(text=f"{inicio}{modo}")

        fim = self.jogo.estado_fim()
        if fim is not None:
            self.lbl_estado.configure(text=fim.descricao, fg=tema.ACENTO)
        elif self.jogo.em_xeque():
            self.lbl_estado.configure(text=f"Xeque! O rei das {self.jogo.vez()} está atacado.",
                                      fg=tema.ERRO)
        else:
            quem = ""
            if self.config.contra_ia:
                quem = " (você)" if self.jogo.vez() == self.config.cor_humano else " (IA)"
            self.lbl_estado.configure(text=f"Vez das {self.jogo.vez()}{quem}", fg=tema.TINTA)

    def _atualizar_botoes(self) -> None:
        em_andamento = self._partida_em_andamento()
        humano = self._vez_do_humano()
        self.btn_desistir.state(["!disabled"] if em_andamento else ["disabled"])
        pode_empate = humano and self.jogo.motivo_empate_reivindicavel() is not None
        self.btn_empate.state(["!disabled"] if pode_empate else ["disabled"])
        self.btn_jogar.state(["!disabled"] if humano else ["disabled"])
        self.campo_lance.state(["!disabled"] if humano else ["disabled"])


def _ativar_dpi_windows() -> None:
    """Evita texto borrado no Windows com escala de tela acima de 100%."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass


def executar() -> None:
    _ativar_dpi_windows()
    raiz = tk.Tk()
    AplicacaoXadrez(raiz)
    raiz.mainloop()

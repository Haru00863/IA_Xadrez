"""Diálogos: nova partida, promoção do peão e atalhos de teclado."""

from __future__ import annotations

import random
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from typing import Optional

from src.engine import MOTORES

from . import tema
from .sprites import Sprites

BRANCAS, PRETAS = "brancas", "pretas"

# valor de dificuldade_ia quando não há IA
SEM_IA = "Sem IA (dois jogadores)"


@dataclass
class ConfiguracaoPartida:
    """Opções do diálogo de nova partida."""
    contra_ia: bool = True
    motor_chave: Optional[str] = next(iter(MOTORES), None)
    cor_humano: str = BRANCAS

    @property
    def rotulo_banco(self) -> str:
        """Texto gravado em PARTIDA.dificuldade_ia."""
        if not self.contra_ia or self.motor_chave not in MOTORES:
            return SEM_IA
        return MOTORES[self.motor_chave].nome


class _DialogoModal(tk.Toplevel):
    """Base dos diálogos: modal, centralizado, Esc fecha."""

    def __init__(self, pai: tk.Misc, titulo: str):
        super().__init__(pai)
        self.withdraw()  # esconde até centralizar
        self.title(titulo)
        self.transient(pai)
        self.resizable(False, False)
        self.configure(bg=tema.SUPERFICIE)
        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        self.bind("<Escape>", lambda e: self._cancelar())
        self.resultado = None

    def _exibir(self, foco: tk.Widget):
        tema.centralizar(self, self.master)
        self.deiconify()
        self.wait_visibility()
        self.grab_set()
        foco.focus_set()
        self.wait_window()
        return self.resultado

    def _cancelar(self):
        self.resultado = None
        self.destroy()


class DialogoNovaPartida(_DialogoModal):
    def __init__(self, pai: tk.Misc, fontes: tema.Fontes, *, titulo: str = "Nova partida",
                 texto_botao: str = "Começar partida",
                 inicial: Optional[ConfiguracaoPartida] = None,
                 aviso: str = ""):
        super().__init__(pai, titulo)
        inicial = inicial or ConfiguracaoPartida()
        self._chaves = list(MOTORES)

        corpo = ttk.Frame(self, style="Painel.TFrame", padding=(22, 18, 22, 16))
        corpo.pack(fill="both", expand=True)
        ttk.Label(corpo, text=titulo, style="PainelTitulo.TLabel").pack(anchor="w")
        if aviso:
            ttk.Label(corpo, text=aviso, style="PainelSuave.TLabel", wraplength=380,
                      justify="left").pack(anchor="w", pady=(4, 0))

        ttk.Label(corpo, text="Adversário", style="Painel.TLabel",
                  font=fontes.forte).pack(anchor="w", pady=(14, 4))
        self._contra_ia = tk.BooleanVar(value=inicial.contra_ia)
        ttk.Radiobutton(corpo, text="Computador", variable=self._contra_ia, value=True,
                        command=self._atualizar_estado).pack(anchor="w")
        ttk.Radiobutton(corpo, text="Outra pessoa, no mesmo computador",
                        variable=self._contra_ia, value=False,
                        command=self._atualizar_estado).pack(anchor="w")

        ttk.Label(corpo, text="Motor de IA", style="Painel.TLabel",
                  font=fontes.forte).pack(anchor="w", pady=(14, 4))
        nomes = [MOTORES[c].nome for c in self._chaves]
        self._motor = ttk.Combobox(corpo, values=nomes, state="readonly", width=34)
        indice = self._chaves.index(inicial.motor_chave) if inicial.motor_chave in self._chaves else 0
        self._motor.current(indice)
        self._motor.pack(anchor="w")
        self._descricao = ttk.Label(corpo, style="PainelSuave.TLabel", wraplength=380,
                                    justify="left")
        self._descricao.pack(anchor="w", pady=(4, 0))
        self._motor.bind("<<ComboboxSelected>>", lambda e: self._atualizar_estado())

        ttk.Label(corpo, text="Você joga com", style="Painel.TLabel",
                  font=fontes.forte).pack(anchor="w", pady=(14, 4))
        linha_cor = ttk.Frame(corpo, style="Painel.TFrame")
        linha_cor.pack(anchor="w")
        self._cor = tk.StringVar(value=inicial.cor_humano)
        self._radios_cor = [
            ttk.Radiobutton(linha_cor, text=rotulo, variable=self._cor, value=valor)
            for rotulo, valor in (("Brancas", BRANCAS), ("Pretas", PRETAS), ("Sortear", "sortear"))
        ]
        for radio in self._radios_cor:
            radio.pack(side="left", padx=(0, 14))

        botoes = ttk.Frame(corpo, style="Painel.TFrame")
        botoes.pack(fill="x", pady=(22, 0))
        confirmar = ttk.Button(botoes, text=texto_botao, style="Acento.TButton",
                               command=self._confirmar)
        confirmar.pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self._cancelar).pack(side="right", padx=(0, 8))
        self.bind("<Return>", lambda e: self._confirmar())

        self._atualizar_estado()
        self._foco_inicial = confirmar

    def _atualizar_estado(self):
        """Motor e cor só valem contra o computador."""
        estado = "readonly" if self._contra_ia.get() else "disabled"
        self._motor.configure(state=estado)
        for radio in self._radios_cor:
            radio.state(["!disabled"] if self._contra_ia.get() else ["disabled"])
        chave = self._chaves[self._motor.current()] if self._chaves else None
        self._descricao.configure(text=MOTORES[chave].descricao if chave else
                                  "Nenhum motor de IA registrado em src/engine.")

    def _confirmar(self):
        cor = self._cor.get()
        if cor == "sortear":
            cor = random.choice((BRANCAS, PRETAS))
        chave = self._chaves[self._motor.current()] if self._chaves else None
        self.resultado = ConfiguracaoPartida(contra_ia=self._contra_ia.get() and chave is not None,
                                             motor_chave=chave, cor_humano=cor)
        self.destroy()

    def perguntar(self) -> Optional[ConfiguracaoPartida]:
        return self._exibir(self._foco_inicial)


class DialogoPromocao(_DialogoModal):
    """Devolve 'q', 'r', 'b', 'n' ou None se cancelado."""

    OPCOES = (("q", "Dama", "D"), ("r", "Torre", "T"), ("b", "Bispo", "B"), ("n", "Cavalo", "C"))

    def __init__(self, pai: tk.Misc, sprites: Sprites, fontes: tema.Fontes, cor: str):
        super().__init__(pai, "Promoção do peão")
        corpo = ttk.Frame(self, style="Painel.TFrame", padding=(20, 16))
        corpo.pack(fill="both", expand=True)
        ttk.Label(corpo, text="Escolha a peça da promoção", style="PainelTitulo.TLabel").pack(
            anchor="w")
        linha = ttk.Frame(corpo, style="Painel.TFrame")
        linha.pack(pady=(12, 8))
        tamanho = sprites.tamanho_para(64)
        self._botoes = []
        for letra, nome, atalho in self.OPCOES:
            simbolo = letra.upper() if cor == BRANCAS else letra
            botao = ttk.Button(linha, text=f"{nome} ({atalho})", compound="top",
                               image=sprites.imagem(simbolo, tamanho),
                               command=lambda l=letra: self._escolher(l))
            botao.pack(side="left", padx=4)
            botao.bind("<Return>", lambda e, l=letra: self._escolher(l))
            self._botoes.append(botao)
        ttk.Label(corpo, text="Teclas: D, T, B ou C. Esc cancela o lance.",
                  style="PainelSuave.TLabel").pack(anchor="w")
        # teclas em português (D, T, B, C) e em inglês (Q, R, N)
        for teclas, letra in (("dq", "q"), ("tr", "r"), ("b", "b"), ("cn", "n")):
            for tecla in teclas:
                self.bind(f"<KeyPress-{tecla}>", lambda e, l=letra: self._escolher(l))
                self.bind(f"<KeyPress-{tecla.upper()}>", lambda e, l=letra: self._escolher(l))

    def _escolher(self, letra: str):
        self.resultado = letra
        self.destroy()

    def perguntar(self) -> Optional[str]:
        return self._exibir(self._botoes[0])


ATALHOS = (
    ("Mouse", "Clique na peça e depois no destino, ou arraste a peça"),
    ("Setas", "Movem o cursor no tabuleiro (clique nele antes)"),
    ("Enter ou Espaço", "Seleciona a peça ou joga para a casa do cursor"),
    ("Esc", "Cancela a seleção"),
    ("Ctrl+L", "Vai para o campo de lance digitado (ex.: e4, Nf3, e2e4)"),
    ("Ctrl+N", "Nova partida"),
    ("Ctrl+I", "Inverte o tabuleiro"),
    ("Ctrl+H", "Histórico de partidas"),
    ("Ctrl+Q", "Sair"),
    ("F1", "Esta lista de atalhos"),
)


class DialogoAtalhos(_DialogoModal):
    def __init__(self, pai: tk.Misc, fontes: tema.Fontes):
        super().__init__(pai, "Atalhos de teclado")
        corpo = ttk.Frame(self, style="Painel.TFrame", padding=(22, 18))
        corpo.pack(fill="both", expand=True)
        ttk.Label(corpo, text="Atalhos de teclado", style="PainelTitulo.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        for i, (tecla, acao) in enumerate(ATALHOS, start=1):
            ttk.Label(corpo, text=tecla, style="Painel.TLabel", font=fontes.forte).grid(
                row=i, column=0, sticky="nw", padx=(0, 16), pady=2)
            ttk.Label(corpo, text=acao, style="Painel.TLabel").grid(row=i, column=1, sticky="w",
                                                                    pady=2)
        fechar = ttk.Button(corpo, text="Fechar", command=self._cancelar)
        fechar.grid(row=len(ATALHOS) + 1, column=1, sticky="e", pady=(14, 0))
        self.bind("<Return>", lambda e: self._cancelar())
        self._fechar = fechar

    def exibir(self):
        self._exibir(self._fechar)

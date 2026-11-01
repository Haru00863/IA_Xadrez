"""Histórico de partidas e revisão lance a lance."""

from __future__ import annotations

import sqlite3
import tkinter as tk
from datetime import datetime, timezone
from tkinter import ttk
from typing import Callable, Optional

from src.core.core_logic import ChessBoardCore
from src.persistence import database_manager as banco

from . import tema
from .sprites import Sprites
from .tabuleiro import TabuleiroCanvas


def formatar_data(texto_utc: Optional[str]) -> str:
    """Data UTC do SQLite -> 'DD/MM/AAAA HH:MM' no fuso do computador."""
    if not texto_utc:
        return "-"
    try:
        data = datetime.strptime(texto_utc, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return texto_utc
    return data.astimezone().strftime("%d/%m/%Y %H:%M")


def _tag_base(numero: int) -> str:
    return "par" if numero % 2 == 0 else "impar"


def preencher_lances(arvore: ttk.Treeview, lances: list[str]) -> None:
    """Preenche a lista de lances (nº, brancas, pretas)."""
    arvore.delete(*arvore.get_children())
    for i in range(0, len(lances), 2):
        numero = i // 2 + 1
        pretas = lances[i + 1] if i + 1 < len(lances) else ""
        arvore.insert("", "end", iid=str(numero), values=(f"{numero}.", lances[i], pretas),
                      tags=(_tag_base(numero),))


def marcar_linha_atual(arvore: ttk.Treeview, numero: Optional[int]) -> None:
    """Destaca a linha do lance atual.

    Usa uma tag em vez da seleção, porque mudar a seleção por código dispara eventos que voltam
    para cá.
    """
    for iid in arvore.tag_has("atual"):
        arvore.item(iid, tags=(_tag_base(int(iid)),))
    if numero and arvore.exists(str(numero)):
        arvore.item(str(numero), tags=(_tag_base(numero), "atual"))
        arvore.see(str(numero))


def criar_lista_lances(pai: tk.Misc, altura: int = 12) -> tuple[ttk.Frame, ttk.Treeview]:
    """Treeview com barra de rolagem para listas de lances."""
    moldura = ttk.Frame(pai, style="Painel.TFrame")
    arvore = ttk.Treeview(moldura, columns=("n", "brancas", "pretas"), show="headings",
                          height=altura, selectmode="none")
    for coluna, titulo, largura, ancora in (("n", "Nº", 44, "e"), ("brancas", "Brancas", 92, "w"),
                                            ("pretas", "Pretas", 92, "w")):
        arvore.heading(coluna, text=titulo, anchor=ancora)
        arvore.column(coluna, width=largura, minwidth=40, anchor=ancora, stretch=coluna != "n")
    arvore.tag_configure("par", background=tema.misturar(tema.SUPERFICIE, tema.FUNDO, 0.6))
    arvore.tag_configure("atual", background=tema.ACENTO_CLARO)
    rolagem = ttk.Scrollbar(moldura, orient="vertical", command=arvore.yview)
    arvore.configure(yscrollcommand=rolagem.set)
    arvore.pack(side="left", fill="both", expand=True)
    rolagem.pack(side="right", fill="y")
    return moldura, arvore


class JanelaHistorico(tk.Toplevel):
    """Lista as partidas gravadas no banco."""

    def __init__(self, pai: tk.Misc, sprites: Sprites, fontes: tema.Fontes, *,
                 ao_continuar: Callable[[int], None],
                 partida_atual: Callable[[], Optional[int]]):
        super().__init__(pai)
        self.title("Histórico de partidas")
        self.configure(bg=tema.FUNDO)
        self.minsize(560, 320)
        self.transient(pai)
        self._sprites, self._fontes = sprites, fontes
        self._ao_continuar = ao_continuar
        self._partida_atual = partida_atual
        self._partidas: dict[str, dict] = {}

        corpo = ttk.Frame(self, padding=16)
        corpo.pack(fill="both", expand=True)
        ttk.Label(corpo, text="Histórico de partidas", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(corpo, text="Partidas gravadas no banco local (src/persistence/xadrez.db). "
                              "Horários no fuso deste computador.",
                  style="Suave.TLabel").pack(anchor="w", pady=(2, 10))

        tabela = ttk.Frame(corpo)
        tabela.pack(fill="both", expand=True)
        colunas = (("id", "Nº", 50, "e"), ("data", "Início", 130, "w"),
                   ("adversario", "Modo", 190, "w"), ("resultado", "Resultado", 230, "w"),
                   ("lances", "Lances", 60, "e"))
        self._arvore = ttk.Treeview(tabela, columns=[c[0] for c in colunas], show="headings",
                                    height=14, selectmode="browse")
        for chave, titulo, largura, ancora in colunas:
            self._arvore.heading(chave, text=titulo, anchor=ancora)
            self._arvore.column(chave, width=largura, anchor=ancora,
                                stretch=chave in ("adversario", "resultado"))
        self._arvore.tag_configure("andamento", foreground=tema.ACENTO)
        rolagem = ttk.Scrollbar(tabela, orient="vertical", command=self._arvore.yview)
        self._arvore.configure(yscrollcommand=rolagem.set)
        self._arvore.pack(side="left", fill="both", expand=True)
        rolagem.pack(side="right", fill="y")

        self._vazio = ttk.Label(corpo, style="Suave.TLabel")

        botoes = ttk.Frame(corpo)
        botoes.pack(fill="x", pady=(12, 0))
        ttk.Button(botoes, text="Fechar", command=self.destroy).pack(side="right")
        self._btn_continuar = ttk.Button(botoes, text="Continuar partida",
                                         command=self._continuar)
        self._btn_continuar.pack(side="right", padx=(0, 8))
        self._btn_revisar = ttk.Button(botoes, text="Revisar lances", style="Acento.TButton",
                                       command=self._revisar)
        self._btn_revisar.pack(side="right", padx=(0, 8))
        ttk.Button(botoes, text="Atualizar lista", command=self.recarregar).pack(side="left")

        self._arvore.bind("<<TreeviewSelect>>", lambda e: self._atualizar_botoes())
        self._arvore.bind("<Double-1>", lambda e: self._revisar())
        self._arvore.bind("<Return>", lambda e: self._revisar())
        self.bind("<Escape>", lambda e: self.destroy())

        self.recarregar()
        tema.centralizar(self, pai)
        self._arvore.focus_set()

    def recarregar(self) -> None:
        self._arvore.delete(*self._arvore.get_children())
        self._partidas.clear()
        try:
            partidas = banco.listar_partidas()
        except sqlite3.Error as erro:
            partidas = []
            self._vazio.configure(text=f"Não foi possível ler o banco de dados: {erro}")
            self._vazio.pack(anchor="w", pady=(8, 0))
        for p in partidas:
            iid = str(p["id"])
            self._partidas[iid] = p
            tags = ("andamento",) if p["resultado"] == banco.RESULTADO_EM_ANDAMENTO else ()
            self._arvore.insert("", "end", iid=iid, tags=tags, values=(
                p["id"], formatar_data(p["data_inicio"]), p["dificuldade_ia"] or "-",
                p["resultado"] or "-", p["total_lances"]))
        if not partidas and not self._vazio.cget("text"):
            self._vazio.configure(text="Nenhuma partida registrada ainda. As partidas jogadas "
                                       "na interface aparecem aqui automaticamente.")
            self._vazio.pack(anchor="w", pady=(8, 0))
        if partidas:
            primeira = self._arvore.get_children()[0]
            self._arvore.selection_set(primeira)
            self._arvore.focus(primeira)
        self._atualizar_botoes()

    def _selecionada(self) -> Optional[dict]:
        selecao = self._arvore.selection()
        return self._partidas.get(selecao[0]) if selecao else None

    def _atualizar_botoes(self) -> None:
        p = self._selecionada()
        self._btn_revisar.state(["!disabled"] if p and p["total_lances"] else ["disabled"])
        pode_continuar = (p is not None and p["resultado"] == banco.RESULTADO_EM_ANDAMENTO
                          and p["total_lances"] > 0 and p["id"] != self._partida_atual())
        self._btn_continuar.state(["!disabled"] if pode_continuar else ["disabled"])

    def _revisar(self) -> None:
        p = self._selecionada()
        if p and p["total_lances"]:
            JanelaRevisao(self, self._sprites, self._fontes, p)

    def _continuar(self) -> None:
        p = self._selecionada()
        if p and self._btn_continuar.instate(["!disabled"]):
            self.destroy()
            self._ao_continuar(p["id"])


class JanelaRevisao(tk.Toplevel):
    """Reproduz uma partida gravada, lance a lance."""

    def __init__(self, pai: tk.Misc, sprites: Sprites, fontes: tema.Fontes, partida: dict):
        super().__init__(pai)
        self.title(f"Revisão da partida nº {partida['id']}")
        self.configure(bg=tema.FUNDO)
        self.minsize(640, 420)

        lances = banco.obter_jogadas(partida["id"])
        jogo = ChessBoardCore()
        # todas as posições calculadas de uma vez (índice 0 = posição inicial)
        self._posicoes = [(jogo.obter_matriz(), None, None)]
        aplicados, erro = 0, None
        for san in lances:
            if not jogo.executar_movimento(san):
                erro = (f"O lance {aplicados + 1} ({san}) não pôde ser reproduzido a partir da "
                        "posição inicial.")
                break
            aplicados += 1
            self._posicoes.append((jogo.obter_matriz(), jogo.ultimo_lance(),
                                   jogo.casa_rei_em_xeque()))
        self._lances = lances[:aplicados]
        self._indice = len(self._posicoes) - 1

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self._tabuleiro = TabuleiroCanvas(self, sprites, lado_inicial=60,
                                          familia_fonte=fontes.familia)
        self._tabuleiro.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=16)

        lateral = ttk.Frame(self, style="Painel.TFrame", padding=14)
        lateral.grid(row=0, column=1, sticky="ns", padx=(8, 16), pady=16)
        ttk.Label(lateral, text=f"Partida nº {partida['id']}", style="PainelTitulo.TLabel").pack(
            anchor="w")
        for rotulo, valor in (("Início", formatar_data(partida["data_inicio"])),
                              ("Modo", partida["dificuldade_ia"] or "-"),
                              ("Resultado", partida["resultado"] or "-")):
            ttk.Label(lateral, text=f"{rotulo}: {valor}", style="PainelSuave.TLabel",
                      wraplength=240, justify="left").pack(anchor="w", pady=(2, 0))
        if erro:
            ttk.Label(lateral, text=erro, style="PainelSuave.TLabel", foreground=tema.ERRO,
                      wraplength=240, justify="left").pack(anchor="w", pady=(8, 0))

        moldura, self._lista = criar_lista_lances(lateral, altura=12)
        moldura.pack(fill="both", expand=True, pady=(12, 8))
        preencher_lances(self._lista, self._lances)
        self._lista.bind("<Button-1>", self._ao_clicar_lista)

        self._posicao_texto = ttk.Label(lateral, style="PainelSuave.TLabel")
        self._posicao_texto.pack(anchor="w")
        navegacao = ttk.Frame(lateral, style="Painel.TFrame")
        navegacao.pack(fill="x", pady=(8, 0))
        for texto, destino in (("Início", lambda: 0), ("Anterior", lambda: self._indice - 1),
                               ("Próximo", lambda: self._indice + 1),
                               ("Fim", lambda: len(self._posicoes) - 1)):
            ttk.Button(navegacao, text=texto, width=8,
                       command=lambda d=destino: self._ir_para(d())).pack(side="left", padx=(0, 4))
        ttk.Button(lateral, text="Inverter tabuleiro",
                   command=lambda: self._tabuleiro.definir_invertido(
                       not self._tabuleiro.invertido)).pack(anchor="w", pady=(8, 0))
        ttk.Label(lateral, text="Setas esquerda/direita, Home e End navegam.",
                  style="PainelSuave.TLabel").pack(anchor="w", pady=(8, 0))

        self.bind("<Left>", lambda e: self._ir_para(self._indice - 1))
        self.bind("<Right>", lambda e: self._ir_para(self._indice + 1))
        self.bind("<Home>", lambda e: self._ir_para(0))
        self.bind("<End>", lambda e: self._ir_para(len(self._posicoes) - 1))
        self.bind("<Escape>", lambda e: self.destroy())
        self._ir_para(self._indice)
        tema.centralizar(self, pai)
        self.focus_set()

    def _ir_para(self, indice: int) -> str:
        self._indice = max(0, min(len(self._posicoes) - 1, indice))
        matriz, ultimo, xeque = self._posicoes[self._indice]
        self._tabuleiro.atualizar(matriz, ultimo=ultimo, xeque=xeque)
        total = len(self._posicoes) - 1
        self._posicao_texto.configure(
            text="Posição inicial" if self._indice == 0
            else f"Lance {self._indice} de {total}: {self._lances[self._indice - 1]}")
        marcar_linha_atual(self._lista, (self._indice + 1) // 2 if self._indice else None)
        return "break"

    def _ao_clicar_lista(self, evento: tk.Event) -> None:
        """Clique na coluna Brancas ou Pretas vai para aquele lance."""
        linha = self._lista.identify_row(evento.y)
        coluna = self._lista.identify_column(evento.x)
        if linha and coluna in ("#2", "#3"):
            indice = (int(linha) - 1) * 2 + (1 if coluna == "#2" else 2)
            if indice <= len(self._lances):
                self._ir_para(indice)

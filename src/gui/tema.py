"""Cores, fontes e estilos da interface."""

from __future__ import annotations

import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

FUNDO = "#E9E7EF"
SUPERFICIE = "#F7F6FA"
SUPERFICIE_ATIVA = "#FFFFFF"
TINTA = "#26232F"
TINTA_SUAVE = "#6B6778"
LINHA = "#D5D1DE"
ACENTO = "#635994"
ACENTO_ESCURO = "#4B4373"
ACENTO_CLARO = "#DCD8EC"
ERRO = "#B23A3A"
XEQUE = "#D9534F"
OURO = "#D8C45A"

# mesmas cores do tabuleiro do protótipo em terminal
CASA_CLARA = "#F0D9B5"
CASA_ESCURA = "#B58863"


def misturar(cor_a: str, cor_b: str, proporcao: float) -> str:
    """Mistura duas cores hex.

    O Canvas não tem transparência, então os destaques são feitos misturando a cor da casa com a
    do destaque.
    """
    a = [int(cor_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(cor_b[i:i + 2], 16) for i in (1, 3, 5)]
    r = [round(x + (y - x) * proporcao) for x, y in zip(a, b)]
    return "#{:02X}{:02X}{:02X}".format(*r)


_FAMILIAS = {
    "win32": ["Segoe UI", "Tahoma"],
    "darwin": ["SF Pro Text", "Helvetica Neue"],
    "linux": ["Inter", "Noto Sans", "Cantarell", "Ubuntu", "DejaVu Sans", "Liberation Sans"],
}


class Fontes:
    """Fontes da aplicação (usa a primeira família da lista que estiver instalada)."""

    def __init__(self, raiz: tk.Misc):
        instaladas = set(tkfont.families(raiz))
        plataforma = "linux" if sys.platform.startswith("linux") else sys.platform
        familia = next((f for f in _FAMILIAS.get(plataforma, []) if f in instaladas),
                       tkfont.nametofont("TkDefaultFont").actual("family"))
        self.familia = familia
        self.base = tkfont.Font(raiz, family=familia, size=10)
        self.pequena = tkfont.Font(raiz, family=familia, size=9)
        self.forte = tkfont.Font(raiz, family=familia, size=10, weight="bold")
        self.titulo = tkfont.Font(raiz, family=familia, size=12, weight="bold")
        self.destaque = tkfont.Font(raiz, family=familia, size=15, weight="bold")
        for nome in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                tkfont.nametofont(nome).configure(family=familia, size=10)
            except tk.TclError:
                pass


def aplicar_estilo(raiz: tk.Tk) -> Fontes:
    """Configura o tema ttk e devolve as fontes."""
    fontes = Fontes(raiz)
    raiz.configure(bg=FUNDO)
    estilo = ttk.Style(raiz)
    # o 'clam' aceita cores personalizadas igual no Windows e no Linux
    estilo.theme_use("clam")

    estilo.configure(".", background=FUNDO, foreground=TINTA, font=fontes.base,
                     bordercolor=LINHA, lightcolor=FUNDO, darkcolor=FUNDO,
                     troughcolor=FUNDO, focuscolor=ACENTO, selectbackground=ACENTO,
                     selectforeground="#FFFFFF")
    estilo.configure("TFrame", background=FUNDO)
    estilo.configure("Painel.TFrame", background=SUPERFICIE)
    estilo.configure("TLabel", background=FUNDO, foreground=TINTA)
    estilo.configure("Painel.TLabel", background=SUPERFICIE)
    estilo.configure("Suave.TLabel", foreground=TINTA_SUAVE, font=fontes.pequena)
    estilo.configure("PainelSuave.TLabel", background=SUPERFICIE, foreground=TINTA_SUAVE,
                     font=fontes.pequena)
    estilo.configure("Titulo.TLabel", font=fontes.titulo)
    estilo.configure("PainelTitulo.TLabel", background=SUPERFICIE, font=fontes.titulo)

    estilo.configure("TButton", background=SUPERFICIE, foreground=TINTA, padding=(10, 5),
                     bordercolor=LINHA, lightcolor=SUPERFICIE, darkcolor=SUPERFICIE,
                     focusthickness=1)
    estilo.map("TButton",
               background=[("disabled", FUNDO), ("pressed", ACENTO_CLARO), ("active", "#FFFFFF")],
               foreground=[("disabled", "#A9A5B4")],
               bordercolor=[("focus", ACENTO)])
    estilo.configure("Acento.TButton", background=ACENTO, foreground="#FFFFFF",
                     bordercolor=ACENTO_ESCURO, lightcolor=ACENTO, darkcolor=ACENTO,
                     focuscolor="#FFFFFF")
    estilo.map("Acento.TButton",
               background=[("disabled", "#A9A3C4"), ("pressed", ACENTO_ESCURO),
                           ("active", "#716AA3")],
               foreground=[("disabled", "#F0EEF6")])

    estilo.configure("TEntry", fieldbackground="#FFFFFF", foreground=TINTA, padding=(6, 4),
                     insertcolor=TINTA)
    estilo.map("TEntry", bordercolor=[("focus", ACENTO)], lightcolor=[("focus", ACENTO)])
    estilo.configure("TCombobox", fieldbackground="#FFFFFF", foreground=TINTA, padding=(6, 3),
                     arrowcolor=TINTA)
    estilo.map("TCombobox", fieldbackground=[("readonly", "#FFFFFF")],
               bordercolor=[("focus", ACENTO)])
    raiz.option_add("*TCombobox*Listbox.font", fontes.base)
    raiz.option_add("*TCombobox*Listbox.selectBackground", ACENTO)

    for nome in ("TRadiobutton", "TCheckbutton"):
        estilo.configure(nome, background=SUPERFICIE, foreground=TINTA, indicatorcolor="#FFFFFF",
                         focuscolor=ACENTO)
        estilo.map(nome, indicatorcolor=[("selected", ACENTO), ("pressed", ACENTO_CLARO)],
                   background=[("active", SUPERFICIE)])

    altura_linha = fontes.base.metrics("linespace") + 8
    estilo.configure("Treeview", background=SUPERFICIE, fieldbackground=SUPERFICIE,
                     foreground=TINTA, rowheight=altura_linha, bordercolor=LINHA,
                     lightcolor=SUPERFICIE, darkcolor=SUPERFICIE)
    estilo.map("Treeview", background=[("selected", ACENTO)],
               foreground=[("selected", "#FFFFFF")])
    estilo.configure("Treeview.Heading", background=FUNDO, foreground=TINTA_SUAVE,
                     font=fontes.pequena, bordercolor=LINHA, lightcolor=FUNDO, darkcolor=FUNDO,
                     relief="flat", padding=(6, 4))
    estilo.map("Treeview.Heading", background=[("active", FUNDO)])

    estilo.configure("Vertical.TScrollbar", background=FUNDO, troughcolor=SUPERFICIE,
                     bordercolor=SUPERFICIE, arrowcolor=TINTA_SUAVE, lightcolor=FUNDO,
                     darkcolor=FUNDO)
    estilo.configure("TSeparator", background=LINHA)

    raiz.option_add("*Menu.background", SUPERFICIE)
    raiz.option_add("*Menu.foreground", TINTA)
    raiz.option_add("*Menu.activeBackground", ACENTO)
    raiz.option_add("*Menu.activeForeground", "#FFFFFF")
    raiz.option_add("*Menu.font", fontes.base)
    raiz.option_add("*tearOff", False)
    return fontes


def centralizar(janela: tk.Toplevel, sobre: tk.Misc) -> None:
    """Centraliza uma janela sobre outra."""
    janela.update_idletasks()
    largura, altura = janela.winfo_reqwidth(), janela.winfo_reqheight()
    x = sobre.winfo_rootx() + (sobre.winfo_width() - largura) // 2
    y = sobre.winfo_rooty() + (sobre.winfo_height() - altura) // 3
    janela.geometry(f"+{max(x, 0)}+{max(y, 0)}")

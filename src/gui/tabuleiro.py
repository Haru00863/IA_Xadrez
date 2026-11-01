"""Widget do tabuleiro.

Só desenha a posição e converte cliques, arrastos e teclas em casas ("e2"); quem valida os
lances é o core.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from typing import Callable, Iterable, Optional

from . import tema
from .sprites import Sprites

COLUNAS = "abcdefgh"
LIMIAR_ARRASTO = 5  # pixels de movimento até o clique virar arrasto


def nome_casa(linha: int, coluna: int) -> str:
    """(linha, coluna) da matriz -> 'e4'."""
    return f"{COLUNAS[coluna]}{8 - linha}"


def indices_casa(casa: str) -> tuple[int, int]:
    """'e4' -> (linha, coluna) da matriz."""
    return 8 - int(casa[1]), COLUNAS.index(casa[0])


class TabuleiroCanvas(tk.Canvas):
    """Avisa o app pelos callbacks ao_clicar, ao_soltar, pode_arrastar e ao_cancelar."""

    def __init__(self, master: tk.Misc, sprites: Sprites, *, lado_inicial: int = 72,
                 ao_clicar: Optional[Callable[[str], None]] = None,
                 ao_soltar: Optional[Callable[[str, str], None]] = None,
                 pode_arrastar: Optional[Callable[[str], bool]] = None,
                 ao_cancelar: Optional[Callable[[], None]] = None,
                 familia_fonte: str = "TkDefaultFont"):
        interativo = ao_clicar is not None
        super().__init__(master, width=8 * lado_inicial, height=8 * lado_inicial,
                         bg=tema.FUNDO, highlightthickness=0, takefocus=interativo)
        self._sprites = sprites
        self._ao_clicar = ao_clicar
        self._ao_soltar = ao_soltar
        self._pode_arrastar = pode_arrastar or (lambda casa: False)
        self._ao_cancelar = ao_cancelar
        self._familia = familia_fonte

        self._matriz: list[list[str]] = [["."] * 8 for _ in range(8)]
        self._selecionada: Optional[str] = None
        self._destinos: dict[str, bool] = {}
        self._ultimo: tuple[str, ...] = ()
        self._xeque: Optional[str] = None
        self.invertido = False

        self._lado = lado_inicial
        self._x0 = self._y0 = 0
        self._erro: Optional[str] = None
        self._erro_after: Optional[str] = None
        self._cursor: Optional[str] = None
        self._cursor_visivel = False
        self._arrasto: Optional[dict] = None
        self._sobreposicao: Optional[tuple[str, str]] = None
        self._fontes_coord: dict[int, tkfont.Font] = {}
        self._fontes_sobreposicao: dict[int, tuple[tkfont.Font, ...]] = {}

        self.bind("<Configure>", self._ao_redimensionar)
        if interativo:
            self.bind("<ButtonPress-1>", self._ao_pressionar)
            self.bind("<B1-Motion>", self._ao_mover_pressionado)
            self.bind("<ButtonRelease-1>", self._ao_liberar)
            self.bind("<Motion>", self._ao_passar_mouse)
            self.bind("<Leave>", lambda e: self.configure(cursor=""))
            for tecla, delta in (("<Left>", (0, -1)), ("<Right>", (0, 1)),
                                 ("<Up>", (-1, 0)), ("<Down>", (1, 0))):
                self.bind(tecla, lambda e, d=delta: self._mover_cursor(*d))
            self.bind("<Return>", self._ativar_cursor)
            self.bind("<KP_Enter>", self._ativar_cursor)
            self.bind("<space>", self._ativar_cursor)
            self.bind("<Escape>", lambda e: self._ao_cancelar and self._ao_cancelar())
            self.bind("<FocusOut>", lambda e: self._esconder_cursor())

    def atualizar(self, matriz: list[list[str]], *, selecionada: Optional[str] = None,
                  destinos: Iterable[tuple[str, bool]] = (),
                  ultimo: Optional[tuple[str, str]] = None,
                  xeque: Optional[str] = None) -> None:
        """Recebe o estado do jogo e redesenha."""
        self._matriz = [list(linha) for linha in matriz]
        self._selecionada = selecionada
        self._destinos = dict(destinos)
        self._ultimo = tuple(ultimo) if ultimo else ()
        self._xeque = xeque
        self._redesenhar()

    def definir_invertido(self, invertido: bool) -> None:
        self.invertido = invertido
        self._redesenhar()

    def piscar_erro(self, casa: Optional[str]) -> None:
        """Pinta a casa de vermelho por um instante."""
        if not casa:
            return
        if self._erro_after:
            self.after_cancel(self._erro_after)
        self._erro = casa
        self._redesenhar()

        def limpar():
            self._erro = None
            self._erro_after = None
            self._redesenhar()
        self._erro_after = self.after(450, limpar)

    def mostrar_sobreposicao(self, titulo: str, subtitulo: str) -> None:
        """Cartão sobre o tabuleiro no fim da partida."""
        self._sobreposicao = (titulo, subtitulo)
        self._redesenhar()

    def ocultar_sobreposicao(self) -> None:
        self._sobreposicao = None
        self._redesenhar()

    @property
    def tem_sobreposicao(self) -> bool:
        return self._sobreposicao is not None

    def _ao_redimensionar(self, evento: tk.Event) -> None:
        self._lado = max(24, min(evento.width, evento.height) // 8)
        self._x0 = (evento.width - 8 * self._lado) // 2
        self._y0 = (evento.height - 8 * self._lado) // 2
        self._redesenhar()

    def _para_tela(self, linha: int, coluna: int) -> tuple[int, int]:
        return (7 - linha, 7 - coluna) if self.invertido else (linha, coluna)

    def _canto(self, casa: str) -> tuple[int, int]:
        lt, ct = self._para_tela(*indices_casa(casa))
        return self._x0 + ct * self._lado, self._y0 + lt * self._lado

    def casa_em(self, x: float, y: float) -> Optional[str]:
        """Casa sob o ponto (x, y), ou None fora do tabuleiro."""
        coluna = int((x - self._x0) // self._lado)
        linha = int((y - self._y0) // self._lado)
        if not (0 <= linha < 8 and 0 <= coluna < 8):
            return None
        linha, coluna = self._para_tela(linha, coluna)
        return nome_casa(linha, coluna)

    def _fonte_coord(self) -> tkfont.Font:
        pixels = max(11, int(self._lado * 0.17))
        if pixels not in self._fontes_coord:
            self._fontes_coord[pixels] = tkfont.Font(self, family=self._familia,
                                                     size=-pixels, weight="bold")
        return self._fontes_coord[pixels]

    def _cor_casa(self, casa: str) -> tuple[str, str]:
        linha, coluna = indices_casa(casa)
        base = tema.CASA_CLARA if (linha + coluna) % 2 == 0 else tema.CASA_ESCURA
        cor = base
        if casa in self._ultimo:
            cor = tema.misturar(base, tema.OURO, 0.45)
        if casa == self._selecionada:
            cor = tema.misturar(base, tema.ACENTO, 0.55)
        if casa == self._xeque:
            cor = tema.misturar(base, tema.XEQUE, 0.70)
        if casa == self._erro:
            cor = tema.misturar(base, tema.ERRO, 0.75)
        return cor, base

    def _redesenhar(self) -> None:
        self.delete("all")
        lado = self._lado
        fonte = self._fonte_coord()
        origem_arrasto = self._arrasto["casa"] if self._arrasto and self._arrasto["ativo"] else None

        for linha in range(8):
            for coluna in range(8):
                casa = nome_casa(linha, coluna)
                x, y = self._canto(casa)
                cor, base = self._cor_casa(casa)
                self.create_rectangle(x, y, x + lado, y + lado, fill=cor, width=0)

                # coordenadas na cor da casa oposta
                cor_texto = tema.CASA_ESCURA if base == tema.CASA_CLARA else tema.CASA_CLARA
                lt, ct = self._para_tela(linha, coluna)
                margem = max(2, lado // 18)
                if ct == 0:
                    self.create_text(x + margem, y + margem, text=casa[1], anchor="nw",
                                     fill=cor_texto, font=fonte)
                if lt == 7:
                    self.create_text(x + lado - margem, y + lado - margem // 2, text=casa[0],
                                     anchor="se", fill=cor_texto, font=fonte)

        # destinos: ponto em casa livre, anel em captura
        for casa, captura in self._destinos.items():
            x, y = self._canto(casa)
            _, base = self._cor_casa(casa)
            marca = tema.misturar(base, tema.TINTA, 0.30)
            cx, cy = x + lado / 2, y + lado / 2
            if captura:
                r, espessura = lado * 0.45, max(3, lado * 0.08)
                self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=marca, width=espessura)
            else:
                r = lado * 0.15
                self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=marca, width=0)

        tamanho = self._sprites.tamanho_para(lado)
        for linha in range(8):
            for coluna in range(8):
                simbolo = self._matriz[linha][coluna]
                casa = nome_casa(linha, coluna)
                if simbolo == "." or casa == origem_arrasto:
                    continue
                x, y = self._canto(casa)
                self.create_image(x + lado / 2, y + lado / 2,
                                  image=self._sprites.imagem(simbolo, tamanho))

        # cursor do teclado
        if self._cursor_visivel and self._cursor:
            x, y = self._canto(self._cursor)
            espessura = max(2, lado // 20)
            m = espessura / 2 + 1
            self.create_rectangle(x + m, y + m, x + lado - m, y + lado - m,
                                  outline=tema.ACENTO, width=espessura)

        # a peça arrastada é desenhada por último, por cima de tudo
        if origem_arrasto:
            l, c = indices_casa(origem_arrasto)
            simbolo = self._matriz[l][c]
            self._arrasto["item"] = self.create_image(
                self._arrasto["x"], self._arrasto["y"],
                image=self._sprites.imagem(simbolo, tamanho))

        if self._sobreposicao:
            self._desenhar_sobreposicao(*self._sobreposicao)

    def _desenhar_sobreposicao(self, titulo: str, subtitulo: str) -> None:
        largura_tab = 8 * self._lado
        cx, cy = self._x0 + largura_tab / 2, self._y0 + largura_tab / 2
        largura = largura_tab * 0.78
        tamanho_titulo = max(14, int(self._lado * 0.32))
        # fontes em cache: se o objeto Font for coletado, o texto do canvas perde a fonte
        if self._lado not in self._fontes_sobreposicao:
            self._fontes_sobreposicao[self._lado] = (
                tkfont.Font(self, family=self._familia, size=-tamanho_titulo, weight="bold"),
                tkfont.Font(self, family=self._familia, size=-max(11, int(self._lado * 0.2))),
                tkfont.Font(self, family=self._familia, size=-max(10, int(self._lado * 0.17))),
            )
        f_titulo, f_texto, f_dica = self._fontes_sobreposicao[self._lado]
        altura = tamanho_titulo * 1.4 + f_texto.metrics("linespace") * 1.6 + \
            f_dica.metrics("linespace") * 1.6 + self._lado * 0.45
        x0, y0 = cx - largura / 2, cy - altura / 2
        self.create_rectangle(x0 + 4, y0 + 5, x0 + largura + 4, y0 + altura + 5,
                              fill=tema.misturar(tema.CASA_ESCURA, tema.TINTA, 0.5), width=0)
        self.create_rectangle(x0, y0, x0 + largura, y0 + altura, fill=tema.SUPERFICIE_ATIVA,
                              outline=tema.ACENTO, width=3)
        y = y0 + self._lado * 0.25
        self.create_text(cx, y, text=titulo, anchor="n", font=f_titulo, fill=tema.ACENTO,
                         width=largura * 0.9, justify="center")
        y += tamanho_titulo * 1.4
        self.create_text(cx, y, text=subtitulo, anchor="n", font=f_texto, fill=tema.TINTA,
                         width=largura * 0.9, justify="center")
        self.create_text(cx, y0 + altura - self._lado * 0.2,
                         text="Clique no tabuleiro para ver a posição final.", anchor="s",
                         font=f_dica, fill=tema.TINTA_SUAVE, width=largura * 0.9,
                         justify="center")

    def _ao_passar_mouse(self, evento: tk.Event) -> None:
        casa = self.casa_em(evento.x, evento.y)
        clicavel = casa is not None and (casa in self._destinos or self._pode_arrastar(casa))
        self.configure(cursor="hand2" if clicavel else "")

    def _ao_pressionar(self, evento: tk.Event) -> None:
        self.focus_set()
        self._esconder_cursor(redesenhar=False)
        if self._sobreposicao:
            self.ocultar_sobreposicao()
            return
        casa = self.casa_em(evento.x, evento.y)
        if casa is None:
            return
        if self._pode_arrastar(casa):
            ja_selecionada = casa == self._selecionada
            self._arrasto = {"casa": casa, "x": evento.x, "y": evento.y, "x0": evento.x,
                             "y0": evento.y, "ativo": False, "ja_selecionada": ja_selecionada,
                             "item": None}
            if not ja_selecionada:
                self._ao_clicar(casa)
        else:
            self._arrasto = None
            self._ao_clicar(casa)

    def _ao_mover_pressionado(self, evento: tk.Event) -> None:
        if not self._arrasto:
            return
        a = self._arrasto
        a["x"], a["y"] = evento.x, evento.y
        if not a["ativo"]:
            if abs(evento.x - a["x0"]) + abs(evento.y - a["y0"]) < LIMIAR_ARRASTO:
                return
            a["ativo"] = True
            self._redesenhar()
        elif a["item"]:
            self.coords(a["item"], evento.x, evento.y)

    def _ao_liberar(self, evento: tk.Event) -> None:
        a, self._arrasto = self._arrasto, None
        if not a:
            return
        destino = self.casa_em(evento.x, evento.y)
        if a["ativo"]:
            if destino and destino != a["casa"] and self._ao_soltar:
                self._ao_soltar(a["casa"], destino)
            else:
                self._redesenhar()
        # clique simples na peça já selecionada desmarca
        elif a["ja_selecionada"] and destino == a["casa"]:
            self._ao_clicar(a["casa"])

    def _mover_cursor(self, d_linha: int, d_coluna: int) -> str:
        """As setas seguem o sentido da tela, mesmo com o tabuleiro invertido."""
        if self._cursor is None:
            self._cursor = self._selecionada or ("e7" if self.invertido else "e2")
        else:
            lt, ct = self._para_tela(*indices_casa(self._cursor))
            lt = min(7, max(0, lt + d_linha))
            ct = min(7, max(0, ct + d_coluna))
            self._cursor = nome_casa(*self._para_tela(lt, ct))
        self._cursor_visivel = True
        self._redesenhar()
        return "break"

    def _ativar_cursor(self, evento: tk.Event) -> str:
        if self._cursor is None or not self._cursor_visivel:
            self._mover_cursor(0, 0)
            return "break"
        if self._sobreposicao:
            self.ocultar_sobreposicao()
            return "break"
        self._ao_clicar(self._cursor)
        return "break"

    def _esconder_cursor(self, redesenhar: bool = True) -> None:
        if self._cursor_visivel:
            self._cursor_visivel = False
            if redesenhar:
                self._redesenhar()

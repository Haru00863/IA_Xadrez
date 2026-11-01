"""Carrega as imagens das peças (geradas por scripts/gerar_sprites_pecas.py)."""

from __future__ import annotations

import os
import tkinter as tk

_PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "pecas")


class Sprites:
    def __init__(self, raiz: tk.Misc):
        self._raiz = raiz
        # o Tkinter só mostra a imagem enquanto ela tiver referência, por isso o cache
        self._cache: dict[tuple[str, int], tk.PhotoImage] = {}
        self.tamanhos = sorted(int(nome) for nome in os.listdir(_PASTA) if nome.isdigit())
        if not self.tamanhos:
            raise FileNotFoundError(f"Nenhum sprite encontrado em {_PASTA}")

    def tamanho_para(self, lado_casa: int) -> int:
        """Maior sprite que cabe na casa."""
        cabem = [t for t in self.tamanhos if t <= lado_casa]
        return cabem[-1] if cabem else self.tamanhos[0]

    def imagem(self, simbolo: str, tamanho: int) -> tk.PhotoImage:
        """simbolo no padrão FEN: 'P' é peão branco, 'k' é rei preto."""
        chave = (simbolo, tamanho)
        if chave not in self._cache:
            arquivo = f"{'w' if simbolo.isupper() else 'b'}{simbolo.upper()}.png"
            self._cache[chave] = tk.PhotoImage(
                master=self._raiz, file=os.path.join(_PASTA, str(tamanho), arquivo))
        return self._cache[chave]

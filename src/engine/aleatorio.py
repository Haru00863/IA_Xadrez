"""Motor aleatório: escolhe um lance legal ao acaso. Serve de linha de base nas comparações."""

from __future__ import annotations

import random
from typing import Optional

import chess

from .base import JogadaMotor, MotorDecisao


class MotorAleatorio(MotorDecisao):
    chave = "aleatorio"
    nome = "Aleatório"
    descricao = "Linha de base: escolhe qualquer lance legal ao acaso."

    def __init__(self, semente: Optional[int] = None):
        # com semente fixa os testes ficam reproduzíveis
        self._rng = random.Random(semente)

    def escolher_jogada(self, tabuleiro: chess.Board, tempo_limite: float) -> JogadaMotor:
        lances = list(tabuleiro.legal_moves)
        if not lances:
            raise ValueError("Não há lances legais nesta posição.")
        escolhido = self._rng.choice(lances)
        return JogadaMotor(escolhido, avaliacao=None,
                           detalhes=f"sorteado entre {len(lances)} lances legais")

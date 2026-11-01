"""Interface comum dos motores de decisão (aleatório, Minimax, rede neural)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import chess


@dataclass(frozen=True)
class JogadaMotor:
    """Lance escolhido pelo motor."""
    movimento: chess.Move
    avaliacao: Optional[float] = None  # vai para JOGADA.avaliacao_ia
    detalhes: str = ""


class MotorDecisao(ABC):
    """Base de todos os motores."""

    chave: str = ""
    nome: str = ""  # aparece na interface e em PARTIDA.dificuldade_ia
    descricao: str = ""

    @abstractmethod
    def escolher_jogada(self, tabuleiro: chess.Board, tempo_limite: float) -> JogadaMotor:
        """Recebe uma cópia do tabuleiro e devolve o lance escolhido.

        Roda em uma thread separada da interface, então não pode mexer em widgets.
        """
        raise NotImplementedError

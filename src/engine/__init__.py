"""Motores disponíveis na interface. Para adicionar um novo, basta incluí-lo em MOTORES."""

from __future__ import annotations

from .aleatorio import MotorAleatorio
from .base import TEMPO_LIMITE_PADRAO, JogadaMotor, MotorDecisao
from .minimax import MotorMinimaxDificil, MotorMinimaxFacil, MotorMinimaxMedio

# A ordem é a da lista na interface; o primeiro é o padrão do diálogo de nova partida.
MOTORES: dict[str, type[MotorDecisao]] = {
    MotorMinimaxFacil.chave: MotorMinimaxFacil,
    MotorMinimaxMedio.chave: MotorMinimaxMedio,
    MotorMinimaxDificil.chave: MotorMinimaxDificil,
    MotorAleatorio.chave: MotorAleatorio,
}


def criar_motor(chave: str) -> MotorDecisao:
    return MOTORES[chave]()


def motor_por_nome(nome: str) -> type[MotorDecisao] | None:
    """Encontra a classe pelo nome gravado no banco."""
    for classe in MOTORES.values():
        if classe.nome == nome:
            return classe
    return None


__all__ = ["MOTORES", "TEMPO_LIMITE_PADRAO", "JogadaMotor", "MotorDecisao", "criar_motor",
           "motor_por_nome"]

"""Motores disponíveis na interface. Para adicionar um novo, basta incluí-lo em MOTORES."""

from __future__ import annotations

from .aleatorio import MotorAleatorio
from .base import JogadaMotor, MotorDecisao

MOTORES: dict[str, type[MotorDecisao]] = {
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


__all__ = ["MOTORES", "JogadaMotor", "MotorDecisao", "criar_motor", "motor_por_nome"]

"""Funções de avaliação: dão uma nota a uma posição sem olhar lances à frente.

A busca (Minimax) só precisa de uma função ``tabuleiro -> nota``. Trocar a
avaliação (material, heurísticas posicionais, rede treinada) não muda a busca.

Convenção: a nota é sempre na perspectiva das BRANCAS e em peões.
Positivo = brancas melhor, negativo = pretas melhor, 0 = equilíbrio.
"""

from __future__ import annotations

from typing import Callable

import chess

# Tipo do "plugue" de avaliação que o MotorMinimax recebe.
Avaliador = Callable[[chess.Board], float]

# Valores clássicos em peões. O rei não entra: ele nunca sai do tabuleiro.
VALOR_PECA = {
    chess.PAWN: 1.0,
    chess.KNIGHT: 3.0,
    chess.BISHOP: 3.0,
    chess.ROOK: 5.0,
    chess.QUEEN: 9.0,
}


def avaliar_material(tabuleiro: chess.Board) -> float:
    """Soma do material das brancas menos o das pretas."""
    nota = 0.0
    for tipo, valor in VALOR_PECA.items():
        brancas = len(tabuleiro.pieces(tipo, chess.WHITE))
        pretas = len(tabuleiro.pieces(tipo, chess.BLACK))
        nota += valor * (brancas - pretas)
    return nota


# --------------------------------------------------------------------------
# Tabelas de posição (piece-square tables)
#
# Bônus ou penalidade, em centésimos de peão, por ter a peça em cada casa.
# Valores da "Simplified Evaluation Function" (Tomasz Michniewski), muito usada
# como primeira heurística posicional. Resumo das ideias:
#   - peão: avançar é bom; peões centrais na casa inicial atrapalham o desenvolvimento
#   - cavalo e bispo: melhores no centro, ruins na borda ("cavalo na borda é vergonha")
#   - torre: boa na 7ª fileira
#   - rei: protegido atrás dos peões (roque), ruim no centro
#
# Cada tabela está escrita do ponto de vista das BRANCAS, como o tabuleiro é
# visto na tela: a primeira linha é a 8ª fileira (a8..h8), a última é a 1ª (a1..h1).
# --------------------------------------------------------------------------

TABELA_PEAO = [
     0,   0,   0,   0,   0,   0,   0,   0,
    50,  50,  50,  50,  50,  50,  50,  50,
    10,  10,  20,  30,  30,  20,  10,  10,
     5,   5,  10,  25,  25,  10,   5,   5,
     0,   0,   0,  20,  20,   0,   0,   0,
     5,  -5, -10,   0,   0, -10,  -5,   5,
     5,  10,  10, -20, -20,  10,  10,   5,
     0,   0,   0,   0,   0,   0,   0,   0,
]

TABELA_CAVALO = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20,   0,   0,   0,   0, -20, -40,
    -30,   0,  10,  15,  15,  10,   0, -30,
    -30,   5,  15,  20,  20,  15,   5, -30,
    -30,   0,  15,  20,  20,  15,   0, -30,
    -30,   5,  10,  15,  15,  10,   5, -30,
    -40, -20,   0,   5,   5,   0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]

TABELA_BISPO = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,  10,  10,   5,   0, -10,
    -10,   5,   5,  10,  10,   5,   5, -10,
    -10,   0,  10,  10,  10,  10,   0, -10,
    -10,  10,  10,  10,  10,  10,  10, -10,
    -10,   5,   0,   0,   0,   0,   5, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]

TABELA_TORRE = [
     0,   0,   0,   0,   0,   0,   0,   0,
     5,  10,  10,  10,  10,  10,  10,   5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
     0,   0,   0,   5,   5,   0,   0,   0,
]

TABELA_DAMA = [
    -20, -10, -10,  -5,  -5, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,   5,   5,   5,   0, -10,
     -5,   0,   5,   5,   5,   5,   0,  -5,
      0,   0,   5,   5,   5,   5,   0,  -5,
    -10,   5,   5,   5,   5,   5,   0, -10,
    -10,   0,   5,   0,   0,   0,   0, -10,
    -20, -10, -10,  -5,  -5, -10, -10, -20,
]

# Rei no meio-jogo. Ainda não há tabela de final (em que o rei deve ir ao centro).
TABELA_REI = [
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
     20,  20,   0,   0,   0,   0,  20,  20,
     20,  30,  10,   0,   0,  10,  30,  20,
]

TABELAS = {
    chess.PAWN: TABELA_PEAO,
    chess.KNIGHT: TABELA_CAVALO,
    chess.BISHOP: TABELA_BISPO,
    chess.ROOK: TABELA_TORRE,
    chess.QUEEN: TABELA_DAMA,
    chess.KING: TABELA_REI,
}

# Material em centésimos de peão: a conta inteira evita erro de arredondamento.
CENTESIMOS_PECA = {tipo: int(valor * 100) for tipo, valor in VALOR_PECA.items()}
CENTESIMOS_PECA[chess.KING] = 0


def bonus_casa(tipo: chess.PieceType, cor: chess.Color, casa: chess.Square) -> int:
    """Bônus (em centésimos de peão) da peça ``tipo`` da ``cor`` na ``casa``.

    No python-chess a casa 0 é a1, mas a tabela começa em a8. Para as brancas
    espelhamos a casa na vertical (a1 <-> a8); para as pretas, que veem o
    tabuleiro "de cabeça para baixo", o índice direto já é o certo.
    """
    tabela = TABELAS[tipo]
    indice = chess.square_mirror(casa) if cor == chess.WHITE else casa
    return tabela[indice]


# Material + bônus de casa já somados, por cor, tipo e casa. Calculado uma vez só:
# a avaliação roda dezenas de milhares de vezes por lance, então vale a pena.
VALOR_CASA = {
    cor: {tipo: [CENTESIMOS_PECA[tipo] + bonus_casa(tipo, cor, casa) for casa in chess.SQUARES]
          for tipo in chess.PIECE_TYPES}
    for cor in chess.COLORS
}


def avaliar_posicional(tabuleiro: chess.Board) -> float:
    """Material + tabelas de posição, em peões, na perspectiva das brancas.

    Percorre as peças pelos bitboards do python-chess (um inteiro de 64 bits por
    tipo e cor, com um bit para cada casa ocupada), que é bem mais rápido que
    ``piece_map()``. O resultado é o mesmo da soma peça a peça.
    """
    total = 0  # centésimos de peão
    for tipo in chess.PIECE_TYPES:
        brancas = VALOR_CASA[chess.WHITE][tipo]
        pretas = VALOR_CASA[chess.BLACK][tipo]
        for casa in chess.scan_reversed(tabuleiro.pieces_mask(tipo, chess.WHITE)):
            total += brancas[casa]
        for casa in chess.scan_reversed(tabuleiro.pieces_mask(tipo, chess.BLACK)):
            total -= pretas[casa]
    return total / 100

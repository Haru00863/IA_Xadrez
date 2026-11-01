"""Regras do xadrez e validação dos lances.

Todo lance, do usuário ou da IA, passa por aqui antes de alterar o tabuleiro.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import chess


BRANCAS = "brancas"
PRETAS = "pretas"

_NOME_COR = {chess.WHITE: BRANCAS, chess.BLACK: PRETAS}

# (artigo, nome), para montar frases como "a torre não pode..."
_NOME_PECA = {
    chess.PAWN: ("o", "peão"),
    chess.KNIGHT: ("o", "cavalo"),
    chess.BISHOP: ("o", "bispo"),
    chess.ROOK: ("a", "torre"),
    chess.QUEEN: ("a", "dama"),
    chess.KING: ("o", "rei"),
}

# usado só para mostrar a vantagem de material
_VALOR_PECA = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
               chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}

_MOTIVO_TERMINO = {
    chess.Termination.CHECKMATE: "xeque-mate",
    chess.Termination.STALEMATE: "afogamento",
    chess.Termination.INSUFFICIENT_MATERIAL: "material insuficiente",
    chess.Termination.SEVENTYFIVE_MOVES: "regra dos 75 lances",
    chess.Termination.FIVEFOLD_REPETITION: "repetição quíntupla",
    chess.Termination.FIFTY_MOVES: "regra dos 50 lances",
    chess.Termination.THREEFOLD_REPETITION: "repetição tripla",
}

# letras aceitas para a peça da promoção
_PROMOCAO = {"q": chess.QUEEN, "r": chess.ROOK, "b": chess.BISHOP, "n": chess.KNIGHT}


@dataclass(frozen=True)
class ResultadoJogada:
    """Resposta a uma tentativa de lance."""
    valido: bool
    san: Optional[str] = None
    origem: Optional[str] = None
    destino: Optional[str] = None
    mensagem: str = ""


@dataclass(frozen=True)
class FimDeJogo:
    """Como a partida terminou."""
    vencedor: Optional[str]
    motivo: str

    @property
    def placar(self) -> str:
        """Placar no formato PGN (1-0, 0-1 ou 1/2-1/2)."""
        if self.vencedor == BRANCAS:
            return "1-0"
        if self.vencedor == PRETAS:
            return "0-1"
        return "1/2-1/2"

    @property
    def descricao(self) -> str:
        """Frase exibida na interface."""
        if self.vencedor is None:
            return f"Empate por {self.motivo}."
        if self.motivo == "xeque-mate":
            return f"Xeque-mate. Vitória das {self.vencedor}."
        return f"Vitória das {self.vencedor} por {self.motivo}."

    @property
    def resultado_banco(self) -> str:
        """Texto gravado em PARTIDA.resultado."""
        if self.vencedor is None:
            return f"Empate ({self.motivo})"
        return f"Vitória das {self.vencedor} ({self.motivo})"


class ChessBoardCore:
    def __init__(self):
        self.board = chess.Board()
        self._encerramento_manual: Optional[FimDeJogo] = None  # desistência ou empate reivindicado

    def obter_matriz(self):
        """Matriz 8x8 com os símbolos das peças (linha 0 = fileira 8)."""
        matriz = []
        for i in range(8):
            linha = []
            for j in range(8):
                square = chess.square(j, 7 - i)
                peca = self.board.piece_at(square)
                linha.append(peca.symbol() if peca else ".")
            matriz.append(linha)
        return matriz

    def executar_movimento(self, pgn_move):
        """Executa um movimento e retorna True se for válido."""
        try:
            self.board.push_san(pgn_move)
            return True
        except ValueError:
            return False

    def listar_movimentos_legais(self, coordenada_algebraica):
        """Casas de destino da peça, sem repetir as quatro opções de promoção."""
        return [destino for destino, _ in self.destinos_legais(coordenada_algebraica)]

    def vez(self) -> str:
        return _NOME_COR[self.board.turn]

    def cor_em(self, casa: str) -> Optional[str]:
        """'brancas', 'pretas' ou None se a casa estiver vazia."""
        peca = self.board.piece_at(chess.parse_square(casa))
        return _NOME_COR[peca.color] if peca else None

    def destinos_legais(self, casa: str) -> list[tuple[str, bool]]:
        """Lista de (casa, é_captura) para a peça na casa informada."""
        try:
            origem = chess.parse_square(casa)
        except ValueError:
            return []
        vistos: dict[str, bool] = {}
        for mov in self.board.legal_moves:
            if mov.from_square == origem:
                nome = chess.square_name(mov.to_square)
                vistos.setdefault(nome, self.board.is_capture(mov))
        return list(vistos.items())

    def exige_promocao(self, origem: str, destino: str) -> bool:
        try:
            o, d = chess.parse_square(origem), chess.parse_square(destino)
        except ValueError:
            return False
        return any(m.from_square == o and m.to_square == d and m.promotion
                   for m in self.board.legal_moves)

    def em_xeque(self) -> bool:
        return self.board.is_check()

    def casa_rei_em_xeque(self) -> Optional[str]:
        if not self.board.is_check():
            return None
        rei = self.board.king(self.board.turn)
        return chess.square_name(rei) if rei is not None else None

    def ultimo_lance(self) -> Optional[tuple[str, str]]:
        if not self.board.move_stack:
            return None
        mov = self.board.peek()
        return chess.square_name(mov.from_square), chess.square_name(mov.to_square)

    def total_meios_lances(self) -> int:
        return len(self.board.move_stack)

    def lances_san(self) -> list[str]:
        tabuleiro = self.board.root()
        san = []
        for mov in self.board.move_stack:
            san.append(tabuleiro.san(mov))
            tabuleiro.push(mov)
        return san

    def capturas(self) -> dict[str, list[str]]:
        """Peças capturadas por cada lado, da mais valiosa para a menos valiosa.

        Percorre o histórico em vez de contar as peças, para que promoções não contem como
        captura.
        """
        tabuleiro = self.board.root()
        resultado: dict[str, list[str]] = {BRANCAS: [], PRETAS: []}
        for mov in self.board.move_stack:
            if tabuleiro.is_capture(mov):
                if tabuleiro.is_en_passant(mov):
                    simbolo = "p" if tabuleiro.turn == chess.WHITE else "P"
                else:
                    simbolo = tabuleiro.piece_at(mov.to_square).symbol()
                resultado[_NOME_COR[tabuleiro.turn]].append(simbolo)
            tabuleiro.push(mov)
        for lista in resultado.values():
            lista.sort(key=lambda s: -_VALOR_PECA[chess.Piece.from_symbol(s).piece_type])
        return resultado

    def vantagem_material(self) -> int:
        saldo = 0
        for peca in self.board.piece_map().values():
            valor = _VALOR_PECA[peca.piece_type]
            saldo += valor if peca.color == chess.WHITE else -valor
        return saldo

    def jogar(self, origem: str, destino: str,
              promocao: Optional[str] = None) -> ResultadoJogada:
        """Tenta jogar origem -> destino. promocao: 'q', 'r', 'b' ou 'n'."""
        if self.estado_fim() is not None:
            return ResultadoJogada(False, mensagem="A partida já terminou.")
        try:
            o, d = chess.parse_square(origem), chess.parse_square(destino)
        except ValueError:
            return ResultadoJogada(False, mensagem=f"Coordenada inválida: {origem}{destino}.")

        if self.exige_promocao(origem, destino) and promocao is None:
            return ResultadoJogada(False, origem=origem, destino=destino,
                                   mensagem="Escolha a peça para a promoção do peão.")

        tipo_promocao = _PROMOCAO.get((promocao or "").lower())
        try:
            # find_move também trata o rei solto sobre a torre como roque
            mov = self.board.find_move(o, d, tipo_promocao)
        except chess.IllegalMoveError:
            return ResultadoJogada(False, origem=origem, destino=destino,
                                   mensagem=self.explicar_ilegalidade(origem, destino))
        return self._aplicar(mov)

    def jogar_texto(self, texto: str) -> ResultadoJogada:
        """Aceita notação SAN (e4, Nf3, O-O) ou origem e destino (e2e4)."""
        texto = texto.strip()
        if not texto:
            return ResultadoJogada(False, mensagem="Digite um lance (ex.: e4, Nf3 ou e2e4).")
        if self.estado_fim() is not None:
            return ResultadoJogada(False, mensagem="A partida já terminou.")

        # origem e destino (e2e4) seguem o mesmo caminho dos cliques
        coordenadas = re.fullmatch(r"([a-h][1-8])-?([a-h][1-8])([qrbn])?", texto.lower())
        if coordenadas:
            origem, destino, promocao = coordenadas.groups()
            if promocao is None and self.exige_promocao(origem, destino):
                return ResultadoJogada(False, origem=origem, destino=destino, mensagem=(
                    "Esse lance é uma promoção: acrescente a peça ao final "
                    f"(ex.: {origem}{destino}q para dama)."))
            return self.jogar(origem, destino, promocao)

        try:
            return self._aplicar(self.board.parse_san(texto))
        except chess.AmbiguousMoveError:
            return ResultadoJogada(False, mensagem=(
                f"O lance {texto} é ambíguo: mais de uma peça pode ir para essa casa. "
                "Indique a coluna ou a fileira de origem (ex.: Nbd2, R1e2)."))
        except chess.IllegalMoveError:
            complemento = " O rei está em xeque." if self.board.is_check() else ""
            return ResultadoJogada(False, mensagem=(
                f"O lance {texto} não é legal nesta posição.{complemento}"))
        except ValueError:
            return ResultadoJogada(False, mensagem=(
                f"Não reconheci o lance \"{texto}\". Use notação algébrica em inglês "
                "(e4, Nf3, O-O, e8=Q) ou origem e destino (e2e4)."))

    def aplicar_jogada_motor(self, movimento: chess.Move) -> ResultadoJogada:
        """Valida e aplica o lance escolhido pelo motor de IA."""
        if self.estado_fim() is not None:
            return ResultadoJogada(False, mensagem="A partida já terminou.")
        if movimento not in self.board.legal_moves:
            return ResultadoJogada(False, mensagem=(
                f"O motor de IA propôs um lance ilegal ({movimento.uci()}); "
                "o lance foi recusado pelo árbitro."))
        return self._aplicar(movimento)

    def _aplicar(self, mov: chess.Move) -> ResultadoJogada:
        san = self.board.san(mov)
        self.board.push(mov)
        return ResultadoJogada(True, san=san,
                               origem=chess.square_name(mov.from_square),
                               destino=chess.square_name(mov.to_square))

    def carregar_lances(self, lances_san: list[str]) -> tuple[int, Optional[str]]:
        """Recomeça o tabuleiro e aplica os lances SAN. Retorna (aplicados, erro)."""
        self.board = chess.Board()
        self._encerramento_manual = None
        for indice, san in enumerate(lances_san):
            try:
                self.board.push_san(san)
            except ValueError:
                return indice, (f"O lance {indice + 1} ({san}) não pôde ser reproduzido a "
                                "partir da posição inicial.")
        return len(lances_san), None

    def copia_tabuleiro(self) -> chess.Board:
        """Cópia entregue ao motor de IA, para ele não mexer no tabuleiro oficial."""
        return self.board.copy()

    def explicar_ilegalidade(self, origem: str, destino: str) -> str:
        """Monta a mensagem que explica por que o lance não é permitido."""
        o, d = chess.parse_square(origem), chess.parse_square(destino)
        peca = self.board.piece_at(o)
        vez = _NOME_COR[self.board.turn]

        if peca is None:
            return f"Não há peça em {origem}."
        if peca.color != self.board.turn:
            return f"A peça em {origem} é das {_NOME_COR[peca.color]}; agora é a vez das {vez}."

        artigo, nome = _NOME_PECA[peca.piece_type]
        alvo = self.board.piece_at(d)
        if o == d:
            return "A peça precisa sair da casa de origem."
        if alvo is not None and alvo.color == peca.color:
            return f"A casa {destino} já está ocupada por uma peça das {vez}."

        # rei andando duas colunas: tentativa de roque
        if (peca.piece_type == chess.KING and chess.square_rank(o) == chess.square_rank(d)
                and abs(chess.square_file(o) - chess.square_file(d)) == 2):
            return self._explicar_roque(o, d)

        promocao = chess.QUEEN if (peca.piece_type == chess.PAWN
                                   and chess.square_rank(d) in (0, 7)) else None
        # o movimento é possível, mas deixa o rei em xeque?
        candidato = chess.Move(o, d, promotion=promocao)
        if self.board.is_pseudo_legal(candidato):
            if self.board.is_check():
                return "O rei está em xeque: o lance precisa tirar o rei do xeque."
            return f"Esse lance deixaria o rei das {vez} em xeque."

        if peca.piece_type == chess.PAWN:
            avanco = chess.square_rank(d) - chess.square_rank(o)
            if peca.color == chess.BLACK:
                avanco = -avanco
            if avanco <= 0:
                return "O peão não pode andar para trás nem para os lados."
            if (abs(chess.square_file(d) - chess.square_file(o)) == 1 and avanco == 1
                    and alvo is None):
                return ("O peão só anda na diagonal para capturar. A captura en passant "
                        "só vale no lance imediatamente seguinte ao avanço duplo do adversário.")

        return f"Movimento ilegal: {artigo} {nome} não pode ir de {origem} para {destino}."

    def _explicar_roque(self, o: chess.Square, d: chess.Square) -> str:
        cor = self.board.turn
        lado_rei = chess.square_file(d) > chess.square_file(o)
        tem_direito = (self.board.has_kingside_castling_rights(cor) if lado_rei
                       else self.board.has_queenside_castling_rights(cor))
        if not tem_direito:
            return "O roque não é mais permitido: o rei ou essa torre já se moveram."
        if self.board.is_check():
            return "Não é permitido rocar estando em xeque."
        fileira = chess.square_rank(o)
        colunas_livres = (5, 6) if lado_rei else (1, 2, 3)
        if any(self.board.piece_at(chess.square(c, fileira)) for c in colunas_livres):
            return "Há peças entre o rei e a torre; o caminho precisa estar livre para o roque."
        colunas_rei = (5, 6) if lado_rei else (3, 2)
        if any(self.board.is_attacked_by(not cor, chess.square(c, fileira)) for c in colunas_rei):
            return "O rei não pode passar por uma casa atacada durante o roque."
        return "O roque não é permitido nesta posição."

    def estado_fim(self) -> Optional[FimDeJogo]:
        """None enquanto a partida continua; senão, como ela terminou."""
        if self._encerramento_manual is not None:
            return self._encerramento_manual
        # repetição tripla e regra dos 50 lances precisam ser reivindicadas (FIDE)
        resultado = self.board.outcome(claim_draw=False)
        if resultado is None:
            return None
        vencedor = None if resultado.winner is None else _NOME_COR[resultado.winner]
        return FimDeJogo(vencedor, _MOTIVO_TERMINO.get(resultado.termination, "fim de jogo"))

    def motivo_empate_reivindicavel(self) -> Optional[str]:
        """Motivo de empate que pode ser reivindicado agora, se houver."""
        if self.estado_fim() is not None:
            return None
        if self.board.is_repetition(3):
            return "repetição tripla"
        if self.board.is_fifty_moves():
            return "regra dos 50 lances"
        return None

    def reivindicar_empate(self) -> Optional[FimDeJogo]:
        motivo = self.motivo_empate_reivindicavel()
        if motivo is None:
            return None
        self._encerramento_manual = FimDeJogo(None, motivo)
        return self._encerramento_manual

    def desistir(self, cor: str) -> FimDeJogo:
        vencedor = PRETAS if cor == BRANCAS else BRANCAS
        self._encerramento_manual = FimDeJogo(vencedor, "desistência")
        return self._encerramento_manual

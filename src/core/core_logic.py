import chess

class ChessBoardCore:
    def __init__(self):
        self.board = chess.Board()

    def obter_matriz(self):
        matriz = []
        for i in range(8):
            linha = []
            for j in range(8):
                square = chess.square(j, 7-i)
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
        try:
            square = chess.parse_square(coordenada_algebraica)
            moves = [move.to_square for move in self.board.legal_moves if move.from_square == square]
            return [chess.square_name(m) for m in moves]
        except ValueError:
            return []

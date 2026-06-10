import chess

class ChessBoardCore:
    def __init__(self):
        """
        Inicia o motor de regras conforme descrito na 
        seção 3.6.2 da documentação (Camada de Lógica).
        """
        self.board = chess.Board()

    def obter_matriz(self):
        """
        Mapeamento de Peças (Figura 3 da pág 19).
        Transforma o estado do python-chess em uma matriz 8x8 para a interface.
        """
        matriz = []
        for i in range(8):
            linha = []
            for j in range(8):
                square = chess.square(j, 7-i)
                peca = self.board.piece_at(square)
                linha.append(peca.symbol() if peca else ".")
            matriz.append(linha)
        return matriz

    def listar_movimentos_legais(self, coordenada_algebraica):
        """
        Lógica de movimentos (Requisito REQ 4 da pág 13).
        Ex: 'e2' -> retorna lista de casas para onde o peão pode ir.
        """
        try:
            square = chess.parse_square(coordenada_algebraica)
            moves = [move.to_square for move in self.board.legal_moves if move.from_square == square]
            # Converte índices (0-63) para nomes (e4, e5...)
            return [chess.square_name(m) for m in moves]
        except ValueError:
            return []

# --- Exemplo de Modularidade (Simulando a chamada da Interface) ---
if __name__ == "__main__":
    # Aqui simulamos a 'Camada de Interface' chamando a 'Camada de Lógica'
    meu_jogo = ChessBoardCore()
    
    print("--- CAMADA DE LÓGICA: MATRIZ ATUAL ---")
    for linha in meu_jogo.obter_matriz():
        print(" ".join(linha))
        
    print("\n--- TESTE DE REGRA (REQ 4): Movimentos para e2 ---")
    print(meu_jogo.listar_movimentos_legais("e2"))

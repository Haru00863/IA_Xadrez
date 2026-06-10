from src.core.core_logic import ChessBoardCore
from src.persistence.database_manager import criar_banco, iniciar_nova_partida, salvar_jogada

def demonstrar_projeto():
    print("=== SISTEMA DE XADREZ IA - UNIFASIPE 2026 ===")
    
    criar_banco()
    id_partida = iniciar_nova_partida("Fácil")
    
    core = ChessBoardCore()
    
    print("\nTabuleiro Inicial:")
    for l in core.obter_matriz(): print(" ".join(l))
    
    jogada = "e4"
    if core.executar_movimento(jogada):
        print(f"\nJogada '{jogada}' executada com sucesso!")
        salvar_jogada(id_partida, jogada)
        
        print("\nTabuleiro Após Jogada:")
        for l in core.obter_matriz(): print(" ".join(l))
    
    print("\nProcesso completo: Lógica processada e Banco de Dados atualizado.")

if __name__ == "__main__":
    demonstrar_projeto()

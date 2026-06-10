import sqlite3
import os

# Função 1: Cria o arquivo do banco e as tabelas (A Estrutura)
def criar_banco():
    diretorio_atual = os.path.dirname(__file__)
    caminho_sql = os.path.join(diretorio_atual, 'init_db.sql')
    caminho_db = os.path.join(diretorio_atual, 'xadrez.db')

    conn = sqlite3.connect(caminho_db)
    cursor = conn.cursor()

    with open(caminho_sql, 'r') as f:
        cursor.executescript(f.read())

    conn.commit()
    conn.close()
    print("Banco de dados 'xadrez.db' criado/verificado com sucesso!")

def iniciar_nova_partida(dificuldade):
    caminho_db = os.path.join(os.path.dirname(__file__), 'xadrez.db')
    conn = sqlite3.connect(caminho_db)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO PARTIDA (data_inicio, resultado, dificuldade_ia)
        VALUES (datetime('now'), 'Em andamento', ?)
    """, (dificuldade,))
    
    partida_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return partida_id

def salvar_jogada(partida_id, movimento_pgn, avaliacao="0.0"):
    caminho_db = os.path.join(os.path.dirname(__file__), 'xadrez.db')
    conn = sqlite3.connect(caminho_db)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO JOGADA (partida_id, notation_pgn, timestamp, avaliacao_ia)
        VALUES (?, ?, datetime('now'), ?)
    """, (partida_id, movimento_pgn, avaliacao))
    
    conn.commit()
    conn.close()
    print(f"Movimento '{movimento_pgn}' salvo no banco (Partida ID: {partida_id})")

if __name__ == "__main__":
    criar_banco()
    
    id_atual = iniciar_nova_partida("Fácil")
    print(f"Iniciada nova partida com ID: {id_atual}")
    
    salvar_jogada(id_atual, "e4")
    salvar_jogada(id_atual, "e5")
    
    print("\nTeste de persistência concluído!")

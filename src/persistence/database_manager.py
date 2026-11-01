"""Acesso ao banco SQLite (tabelas PARTIDA e JOGADA).

Cada lance é gravado assim que acontece. As datas ficam em UTC (datetime('now')).
"""

import os
import sqlite3
from contextlib import closing

_DIRETORIO = os.path.dirname(os.path.abspath(__file__))
_CAMINHO_SQL = os.path.join(_DIRETORIO, "init_db.sql")

# XADREZ_DB troca o arquivo (os testes usam um banco temporário)
CAMINHO_DB = os.environ.get("XADREZ_DB") or os.path.join(_DIRETORIO, "xadrez.db")

RESULTADO_EM_ANDAMENTO = "Em andamento"
RESULTADO_ABANDONADA = "Abandonada"


def _conectar():
    conn = sqlite3.connect(CAMINHO_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def criar_banco():
    """Cria as tabelas, se ainda não existirem."""
    with open(_CAMINHO_SQL, "r", encoding="utf-8") as arquivo:
        script = arquivo.read()
    with closing(_conectar()) as conn, conn:
        conn.executescript(script)


def iniciar_nova_partida(dificuldade):
    with closing(_conectar()) as conn, conn:
        cursor = conn.execute(
            "INSERT INTO PARTIDA (data_inicio, resultado, dificuldade_ia) "
            "VALUES (datetime('now'), ?, ?)",
            (RESULTADO_EM_ANDAMENTO, dificuldade),
        )
        return cursor.lastrowid


def salvar_jogada(partida_id, movimento_pgn, avaliacao="0.0"):
    """Grava um lance em SAN. Nos lances humanos, avaliacao fica None."""
    with closing(_conectar()) as conn, conn:
        conn.execute(
            "INSERT INTO JOGADA (partida_id, notation_pgn, timestamp, avaliacao_ia) "
            "VALUES (?, ?, datetime('now'), ?)",
            (partida_id, movimento_pgn, avaliacao),
        )


def finalizar_partida(partida_id, resultado):
    with closing(_conectar()) as conn, conn:
        conn.execute("UPDATE PARTIDA SET resultado = ? WHERE id = ?", (resultado, partida_id))


def atualizar_dificuldade(partida_id, dificuldade):
    with closing(_conectar()) as conn, conn:
        conn.execute("UPDATE PARTIDA SET dificuldade_ia = ? WHERE id = ?",
                     (dificuldade, partida_id))


def obter_jogadas(partida_id):
    with closing(_conectar()) as conn:
        linhas = conn.execute(
            "SELECT notation_pgn FROM JOGADA WHERE partida_id = ? ORDER BY id",
            (partida_id,),
        ).fetchall()
    return [linha["notation_pgn"] for linha in linhas]


def contar_jogadas(partida_id):
    with closing(_conectar()) as conn:
        return conn.execute("SELECT COUNT(*) FROM JOGADA WHERE partida_id = ?",
                            (partida_id,)).fetchone()[0]


_SELECT_PARTIDAS = """
    SELECT p.id, p.data_inicio, p.resultado, p.dificuldade_ia,
           COUNT(j.id) AS total_lances
      FROM PARTIDA p
      LEFT JOIN JOGADA j ON j.partida_id = p.id
"""


def obter_partida(partida_id):
    with closing(_conectar()) as conn:
        linha = conn.execute(_SELECT_PARTIDAS + " WHERE p.id = ? GROUP BY p.id",
                             (partida_id,)).fetchone()
    return dict(linha) if linha else None


def listar_partidas(limite=500):
    """Partidas mais recentes primeiro, com o total de lances."""
    with closing(_conectar()) as conn:
        linhas = conn.execute(_SELECT_PARTIDAS + " GROUP BY p.id ORDER BY p.id DESC LIMIT ?",
                              (limite,)).fetchall()
    return [dict(linha) for linha in linhas]


def buscar_partida_em_andamento():
    """Última partida não finalizada e com lances, para oferecer a retomada."""
    with closing(_conectar()) as conn:
        linha = conn.execute(
            _SELECT_PARTIDAS +
            " WHERE p.resultado = ?"
            " GROUP BY p.id HAVING COUNT(j.id) > 0 ORDER BY p.id DESC LIMIT 1",
            (RESULTADO_EM_ANDAMENTO,),
        ).fetchone()
    return dict(linha) if linha else None

"""Testes do banco (em arquivo temporário) e do registro de motores."""

import os
import tempfile
import unittest

import chess

from src.engine import MOTORES, MotorDecisao, criar_motor, motor_por_nome
from src.engine.aleatorio import MotorAleatorio
from src.persistence import database_manager as banco


class TestPersistencia(unittest.TestCase):
    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        self._caminho_original = banco.CAMINHO_DB
        # banco temporário: o xadrez.db do projeto não é usado
        banco.CAMINHO_DB = os.path.join(self._pasta.name, "teste.db")
        banco.criar_banco()

    def tearDown(self):
        banco.CAMINHO_DB = self._caminho_original
        self._pasta.cleanup()

    def test_ciclo_completo_de_uma_partida(self):
        pid = banco.iniciar_nova_partida("Aleatório (provisório)")
        banco.salvar_jogada(pid, "e4", None)
        banco.salvar_jogada(pid, "e5", "0.35")
        self.assertEqual(banco.obter_jogadas(pid), ["e4", "e5"])
        self.assertEqual(banco.contar_jogadas(pid), 2)

        pendente = banco.buscar_partida_em_andamento()
        self.assertEqual(pendente["id"], pid)
        self.assertEqual(pendente["total_lances"], 2)

        banco.finalizar_partida(pid, "Vitória das brancas (xeque-mate)")
        self.assertIsNone(banco.buscar_partida_em_andamento())
        self.assertEqual(banco.obter_partida(pid)["resultado"], "Vitória das brancas (xeque-mate)")

    def test_partida_sem_lances_nao_e_retomada(self):
        banco.iniciar_nova_partida("Sem IA (dois jogadores)")
        self.assertIsNone(banco.buscar_partida_em_andamento())

    def test_listagem_mais_recente_primeiro(self):
        a = banco.iniciar_nova_partida("Sem IA (dois jogadores)")
        b = banco.iniciar_nova_partida("Sem IA (dois jogadores)")
        self.assertEqual([p["id"] for p in banco.listar_partidas()], [b, a])


class TestMotores(unittest.TestCase):
    def test_registro(self):
        self.assertIn("aleatorio", MOTORES)
        motor = criar_motor("aleatorio")
        self.assertIsInstance(motor, MotorDecisao)
        self.assertIs(motor_por_nome(motor.nome), MotorAleatorio)
        self.assertIsNone(motor_por_nome("inexistente"))

    def test_aleatorio_devolve_lance_legal_sem_alterar_o_tabuleiro(self):
        tabuleiro = chess.Board()
        fen_antes = tabuleiro.fen()
        jogada = MotorAleatorio(semente=42).escolher_jogada(tabuleiro, tempo_limite=1.0)
        self.assertIn(jogada.movimento, tabuleiro.legal_moves)
        self.assertEqual(tabuleiro.fen(), fen_antes)


if __name__ == "__main__":
    unittest.main()

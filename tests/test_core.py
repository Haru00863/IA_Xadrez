"""Testes da lógica do jogo.

Rodar a partir da raiz do projeto: python -m unittest discover -s tests -v
"""

import unittest

import chess

from src.core.core_logic import BRANCAS, PRETAS, ChessBoardCore


class TestCompatibilidade(unittest.TestCase):
    """Métodos da primeira versão do core."""

    def test_matriz_inicial(self):
        matriz = ChessBoardCore().obter_matriz()
        self.assertEqual(matriz[0], list("rnbqkbnr"))
        self.assertEqual(matriz[7], list("RNBQKBNR"))
        self.assertEqual(matriz[4], ["."] * 8)

    def test_executar_movimento_san(self):
        jogo = ChessBoardCore()
        self.assertTrue(jogo.executar_movimento("e4"))
        self.assertFalse(jogo.executar_movimento("e4"))

    def test_listar_movimentos_sem_duplicatas_na_promocao(self):
        jogo = ChessBoardCore()
        jogo.board.set_fen("8/P7/8/8/8/8/8/K6k w - - 0 1")
        self.assertEqual(jogo.listar_movimentos_legais("a7"), ["a8"])


class TestMovimentos(unittest.TestCase):
    def setUp(self):
        self.jogo = ChessBoardCore()

    def test_vez_alterna(self):
        self.assertEqual(self.jogo.vez(), BRANCAS)
        self.assertTrue(self.jogo.jogar("e2", "e4").valido)
        self.assertEqual(self.jogo.vez(), PRETAS)

    def test_destinos_com_captura(self):
        for lance in ("e4", "d5"):
            self.jogo.executar_movimento(lance)
        destinos = dict(self.jogo.destinos_legais("e4"))
        self.assertEqual(destinos, {"e5": False, "d5": True})

    def test_peao_nao_anda_para_tras(self):
        self.jogo.jogar("e2", "e4")
        self.jogo.jogar("a7", "a6")
        resultado = self.jogo.jogar("e4", "e3")
        self.assertFalse(resultado.valido)
        self.assertIn("para trás", resultado.mensagem)

    def test_peca_do_adversario(self):
        resultado = self.jogo.jogar("e7", "e5")
        self.assertFalse(resultado.valido)
        self.assertIn("vez das brancas", resultado.mensagem)

    def test_casa_ocupada_por_peca_propria(self):
        resultado = self.jogo.jogar("d1", "d2")
        self.assertFalse(resultado.valido)
        self.assertIn("ocupada", resultado.mensagem)

    def test_lance_que_expoe_o_rei(self):
        # peão de d2 cravado pelo bispo de b4
        self.jogo.board.set_fen("4k3/8/8/8/1b6/8/3P4/4K3 w - - 0 1")
        resultado = self.jogo.jogar("d2", "d3")
        self.assertFalse(resultado.valido)
        self.assertIn("xeque", resultado.mensagem)

    def test_roque_curto_e_por_arrasto_sobre_a_torre(self):
        for lance in ("e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"):
            self.jogo.executar_movimento(lance)
        # rei solto sobre a torre também faz roque
        resultado = self.jogo.jogar("e1", "h1")
        self.assertTrue(resultado.valido)
        self.assertEqual(resultado.san, "O-O")

    def test_roque_bloqueado_explica_motivo(self):
        self.jogo.jogar("e2", "e4")
        self.jogo.jogar("e7", "e5")
        resultado = self.jogo.jogar("e1", "g1")
        self.assertFalse(resultado.valido)
        self.assertIn("ocupada", resultado.mensagem)

    def test_en_passant_e_janela_fechada(self):
        for lance in ("e4", "a6", "e5", "d5"):
            self.jogo.executar_movimento(lance)
        self.assertTrue(self.jogo.jogar("e5", "d6").valido)
        self.assertEqual(self.jogo.capturas()[BRANCAS], ["p"])

        tardio = ChessBoardCore()
        for lance in ("e4", "a6", "e5", "d5", "Nf3", "a5"):
            tardio.executar_movimento(lance)
        resultado = tardio.jogar("e5", "d6")
        self.assertFalse(resultado.valido)
        self.assertIn("en passant", resultado.mensagem)

    def test_promocao_exige_escolha(self):
        self.jogo.board.set_fen("8/P7/8/8/8/8/8/K6k w - - 0 1")
        self.assertTrue(self.jogo.exige_promocao("a7", "a8"))
        self.assertFalse(self.jogo.jogar("a7", "a8").valido)
        resultado = self.jogo.jogar("a7", "a8", "n")
        self.assertTrue(resultado.valido)
        self.assertEqual(resultado.san, "a8=N")

    def test_jogar_texto_san_e_coordenadas(self):
        self.assertTrue(self.jogo.jogar_texto("e4").valido)
        self.assertTrue(self.jogo.jogar_texto("e7e5").valido)
        self.assertTrue(self.jogo.jogar_texto("Nf3").valido)
        self.assertFalse(self.jogo.jogar_texto("xyz").valido)
        self.assertIn("não é legal", self.jogo.jogar_texto("Ke3").mensagem)

    def test_jogar_texto_ambiguo(self):
        # as duas torres podem ir para d1
        self.jogo.board.set_fen("4k3/8/8/8/8/8/4K3/R6R w - - 0 1")
        resultado = self.jogo.jogar_texto("Rd1")
        self.assertFalse(resultado.valido)
        self.assertIn("ambíguo", resultado.mensagem)

    def test_lance_do_motor_ilegal_e_recusado(self):
        resultado = self.jogo.aplicar_jogada_motor(chess.Move.from_uci("e2e5"))
        self.assertFalse(resultado.valido)
        self.assertEqual(self.jogo.total_meios_lances(), 0)

    def test_historico_e_reproducao(self):
        lances = ["e4", "e5", "Nf3", "Nc6", "Bb5"]
        for lance in lances:
            self.jogo.executar_movimento(lance)
        self.assertEqual(self.jogo.lances_san(), lances)
        outro = ChessBoardCore()
        self.assertEqual(outro.carregar_lances(lances), (5, None))
        self.assertEqual(outro.obter_matriz(), self.jogo.obter_matriz())
        aplicados, erro = outro.carregar_lances(["e4", "e4"])
        self.assertEqual(aplicados, 1)
        self.assertIsNotNone(erro)


class TestFimDeJogo(unittest.TestCase):
    def test_xeque_mate(self):
        jogo = ChessBoardCore()
        for lance in ("f3", "e5", "g4"):
            jogo.executar_movimento(lance)
        self.assertIsNone(jogo.estado_fim())
        jogo.jogar_texto("Qh4#")
        fim = jogo.estado_fim()
        self.assertEqual((fim.vencedor, fim.motivo, fim.placar), (PRETAS, "xeque-mate", "0-1"))
        self.assertEqual(fim.resultado_banco, "Vitória das pretas (xeque-mate)")
        self.assertEqual(jogo.casa_rei_em_xeque(), "e1")
        self.assertFalse(jogo.jogar("a2", "a3").valido)

    def test_afogamento(self):
        jogo = ChessBoardCore()
        jogo.board.set_fen("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
        fim = jogo.estado_fim()
        self.assertIsNone(fim.vencedor)
        self.assertEqual(fim.motivo, "afogamento")

    def test_material_insuficiente(self):
        jogo = ChessBoardCore()
        jogo.board.set_fen("8/8/8/4k3/8/8/8/4K3 w - - 0 1")
        self.assertEqual(jogo.estado_fim().motivo, "material insuficiente")

    def test_repeticao_tripla_precisa_ser_reivindicada(self):
        jogo = ChessBoardCore()
        for _ in range(2):
            for lance in ("Nf3", "Nf6", "Ng1", "Ng8"):
                jogo.executar_movimento(lance)
        self.assertIsNone(jogo.estado_fim())
        self.assertEqual(jogo.motivo_empate_reivindicavel(), "repetição tripla")
        self.assertEqual(jogo.reivindicar_empate().resultado_banco, "Empate (repetição tripla)")

    def test_desistencia(self):
        jogo = ChessBoardCore()
        fim = jogo.desistir(BRANCAS)
        self.assertEqual((fim.vencedor, fim.motivo), (PRETAS, "desistência"))
        self.assertIs(jogo.estado_fim(), fim)


if __name__ == "__main__":
    unittest.main()

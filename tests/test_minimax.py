"""Testes do motor Minimax: avaliação (material e posição), busca Alfa-Beta, quiescência
e aprofundamento iterativo."""

import math
import unittest

import chess

from src.engine import MOTORES, motor_por_nome
from src.engine.avaliacao import avaliar_material, avaliar_posicional, bonus_casa
from src.engine.minimax import (MATE, Busca, MotorMinimax, MotorMinimaxDificil,
                                MotorMinimaxFacil, MotorMinimaxMedio)

# posições usadas em vários testes
MATE_EM_1_BRANCAS = "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1"       # Ra8#
MATE_EM_1_PRETAS = "r5k1/8/8/8/8/8/5PPP/6K1 b - - 0 1"        # Ra1#
DAMA_SOLTA = "4k3/8/8/3q4/8/4N3/8/4K3 w - - 0 1"             # Nxd5
MATE_DO_PASTOR = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
MEIO_JOGO = "r1bq1rk1/pp2bppp/2n1pn2/2pp4/3P4/2PBPN2/PP1N1PPP/R1BQ1RK1 w - - 0 8"
AFOGAMENTO = "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"
ARMADILHA = "4k3/8/4p3/3p4/8/8/8/3QK3 w - - 0 1"            # Qxd5? exd5 perde a dama
PEAO_SOLTO = "4k3/8/8/3p4/8/8/8/3QK3 w - - 0 1"            # Qxd5 ganha um peão
TROCA_CURTA = "4k3/8/2n5/3p4/4P3/2N5/8/4K3 w - - 0 1"
TROCA_COM_TORRES = "4k3/3r4/2n5/3p4/4P3/2N5/3R4/4K3 w - - 0 1"
TROCAS = "r3k2r/ppp2ppp/2n1bn2/3pp3/3PP3/2N1BN2/PPP2PPP/R3K2R w KQkq - 0 1"


def motor(profundidade: int, **opcoes) -> MotorMinimax:
    classe = type("MotorTeste", (MotorMinimax,), {"profundidade": profundidade})
    return classe(**opcoes)


class TestAvaliacaoMaterial(unittest.TestCase):
    def test_posicao_inicial_vale_zero(self):
        self.assertEqual(avaliar_material(chess.Board()), 0.0)

    def test_dama_a_mais_vale_nove(self):
        self.assertEqual(avaliar_material(chess.Board("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")), 9.0)

    def test_espelhar_inverte_o_sinal(self):
        # nota sempre na perspectiva das brancas: trocar as cores troca o sinal
        for fen in (DAMA_SOLTA, MEIO_JOGO, MATE_EM_1_BRANCAS):
            tabuleiro = chess.Board(fen)
            self.assertEqual(avaliar_material(tabuleiro.mirror()), -avaliar_material(tabuleiro))


class TestAvaliacaoPosicional(unittest.TestCase):
    def test_posicao_inicial_vale_zero(self):
        self.assertEqual(avaliar_posicional(chess.Board()), 0.0)

    def test_espelhar_inverte_o_sinal(self):
        for fen in (DAMA_SOLTA, MEIO_JOGO, MATE_DO_PASTOR):
            tabuleiro = chess.Board(fen)
            self.assertEqual(avaliar_posicional(tabuleiro.mirror()), -avaliar_posicional(tabuleiro))

    def test_tabelas_simetricas_para_as_duas_cores(self):
        # a peça preta numa casa vale o mesmo que a branca na casa espelhada
        for tipo in chess.PIECE_TYPES:
            for casa in chess.SQUARES:
                self.assertEqual(bonus_casa(tipo, chess.BLACK, chess.square_mirror(casa)),
                                 bonus_casa(tipo, chess.WHITE, casa))

    def test_leitura_da_tabela_na_casa_certa(self):
        # peão central parado na casa inicial é penalizado (tabela: -20)
        self.assertEqual(bonus_casa(chess.PAWN, chess.WHITE, chess.E2), -20)
        self.assertEqual(bonus_casa(chess.PAWN, chess.BLACK, chess.E7), -20)
        # peão na 7ª fileira, quase promovendo, ganha bônus (tabela: 50)
        self.assertEqual(bonus_casa(chess.PAWN, chess.WHITE, chess.E7), 50)

    def test_cavalo_no_centro_vale_mais_que_na_borda(self):
        self.assertGreater(bonus_casa(chess.KNIGHT, chess.WHITE, chess.D4),
                           bonus_casa(chess.KNIGHT, chess.WHITE, chess.A4))

    def test_rei_rocado_vale_mais_que_no_centro(self):
        self.assertGreater(bonus_casa(chess.KING, chess.WHITE, chess.G1),
                           bonus_casa(chess.KING, chess.WHITE, chess.E2))

    def test_material_continua_dominando(self):
        # nenhum bônus de casa compensa perder uma peça menor
        self.assertGreater(avaliar_posicional(chess.Board(DAMA_SOLTA).mirror()), 5)


class TestFimDeJogo(unittest.TestCase):
    def test_mate_contra_as_brancas_e_negativo(self):
        tabuleiro = chess.Board()
        for san in ("f3", "e5", "g4", "Qh4"):  # mate do louco
            tabuleiro.push_san(san)
        self.assertEqual(Busca().nota_fim_de_jogo(tabuleiro, ply=0), -MATE)

    def test_mate_contra_as_pretas_e_positivo(self):
        tabuleiro = chess.Board(MATE_EM_1_BRANCAS)
        tabuleiro.push_san("Ra8")
        self.assertEqual(Busca().nota_fim_de_jogo(tabuleiro, ply=3), MATE - 3)

    def test_afogamento_vale_zero(self):
        self.assertEqual(Busca().nota_fim_de_jogo(chess.Board(AFOGAMENTO), ply=0), 0.0)

    def test_posicao_repetida_vale_empate(self):
        tabuleiro = chess.Board()
        for san in ("Nf3", "Nf6", "Ng1", "Ng8"):  # volta à posição inicial
            tabuleiro.push_san(san)
        self.assertEqual(Busca().nota_fim_de_jogo(tabuleiro, ply=1), 0.0)
        # na raiz a repetição não conta: o motor precisa jogar a partir dela
        self.assertIsNone(Busca().nota_fim_de_jogo(tabuleiro, ply=0))

    def test_repeticao_dentro_da_busca_vale_zero_mesmo_com_dama_a_mais(self):
        # brancas com dama a mais; a posição depois de Qd1 já apareceu na partida
        tabuleiro = chess.Board("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
        for san in ("Qd2", "Ke7", "Qd1", "Ke8", "Qd2", "Ke7"):
            tabuleiro.push_san(san)
        tabuleiro.push_san("Qd1")
        # sem a regra, a nota seria cerca de +9 (dama a mais)
        self.assertEqual(Busca().alfa_beta(tabuleiro, 2, ply=1), 0.0)

    def test_ganhando_nao_escolhe_o_lance_que_repete(self):
        tabuleiro = chess.Board("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
        for san in ("Qd2", "Ke7", "Qd1", "Ke8", "Qd2", "Ke7"):
            tabuleiro.push_san(san)
        jogada = motor(2).escolher_jogada(tabuleiro, tempo_limite=10)
        self.assertNotEqual(tabuleiro.san(jogada.movimento), "Qd1")
        self.assertGreater(jogada.avaliacao, 5)

    def test_partida_em_andamento_devolve_none(self):
        self.assertIsNone(Busca().nota_fim_de_jogo(chess.Board(), ply=0))


class TestMotorMinimax(unittest.TestCase):
    def test_mate_em_1_das_brancas(self):
        for profundidade in (1, 2, 3):
            tabuleiro = chess.Board(MATE_EM_1_BRANCAS)
            jogada = motor(profundidade).escolher_jogada(tabuleiro, tempo_limite=10)
            tabuleiro.push(jogada.movimento)
            self.assertTrue(tabuleiro.is_checkmate(), f"profundidade {profundidade}")
            self.assertEqual(jogada.avaliacao, MATE - 1)

    def test_mate_em_1_das_pretas(self):
        tabuleiro = chess.Board(MATE_EM_1_PRETAS)
        jogada = motor(2).escolher_jogada(tabuleiro, tempo_limite=10)
        tabuleiro.push(jogada.movimento)
        self.assertTrue(tabuleiro.is_checkmate())
        self.assertEqual(jogada.avaliacao, -(MATE - 1))

    def test_prefere_o_mate_mais_rapido(self):
        # na profundidade 4 existem mates mais longos; o de 1 lance deve vencer
        tabuleiro = chess.Board(MATE_DO_PASTOR)
        jogada = motor(4).escolher_jogada(tabuleiro, tempo_limite=10)
        self.assertEqual(tabuleiro.san(jogada.movimento), "Qxf7#")
        self.assertEqual(jogada.avaliacao, MATE - 1)

    def test_captura_a_dama_solta(self):
        tabuleiro = chess.Board(DAMA_SOLTA)
        jogada = motor(2).escolher_jogada(tabuleiro, tempo_limite=10)
        self.assertEqual(tabuleiro.san(jogada.movimento), "Nxd5")

    def test_devolve_lance_legal_sem_alterar_o_tabuleiro(self):
        for fen in (chess.STARTING_FEN, MEIO_JOGO):
            tabuleiro = chess.Board(fen)
            jogada = MotorMinimaxMedio().escolher_jogada(tabuleiro, tempo_limite=10)
            self.assertIn(jogada.movimento, tabuleiro.legal_moves)
            self.assertEqual(tabuleiro.fen(), fen)

    def test_sem_lances_legais_gera_erro(self):
        with self.assertRaises(ValueError):
            motor(2).escolher_jogada(chess.Board(AFOGAMENTO), tempo_limite=10)


class TestAlfaBeta(unittest.TestCase):
    def test_mesma_nota_que_o_minimax_puro_com_menos_nos(self):
        # sem quiescência: o Minimax puro termina rápido mesmo em posições táticas
        for fen in (chess.STARTING_FEN, DAMA_SOLTA, MATE_DO_PASTOR, MEIO_JOGO):
            for profundidade in (1, 2, 3):
                with self.subTest(fen=fen, profundidade=profundidade):
                    pura, podada = Busca(quiescencia=False), Busca(quiescencia=False)
                    nota_pura = pura.minimax(chess.Board(fen), profundidade)
                    nota_podada = podada.alfa_beta(chess.Board(fen), profundidade)
                    self.assertEqual(nota_podada, nota_pura)
                    self.assertLessEqual(podada.nos, pura.nos)

    def test_mesma_nota_que_o_minimax_puro_com_quiescencia(self):
        # com quiescência o Minimax puro explode em posições muito táticas,
        # por isso aqui só entram posições com poucas capturas possíveis
        for fen in (chess.STARTING_FEN, DAMA_SOLTA, ARMADILHA, PEAO_SOLTO, MATE_EM_1_BRANCAS):
            for profundidade in (1, 2):
                with self.subTest(fen=fen, profundidade=profundidade):
                    pura, podada = Busca(), Busca()
                    self.assertEqual(podada.alfa_beta(chess.Board(fen), profundidade),
                                     pura.minimax(chess.Board(fen), profundidade))
                    self.assertLessEqual(podada.nos, pura.nos)

    def test_poda_reduz_nos_na_profundidade_3(self):
        pura, podada = Busca(quiescencia=False), Busca(quiescencia=False)
        pura.minimax(chess.Board(MEIO_JOGO), 3)
        podada.alfa_beta(chess.Board(MEIO_JOGO), 3)
        self.assertLess(podada.nos, pura.nos)


class TestQuiescencia(unittest.TestCase):
    def test_sem_quiescencia_cai_na_armadilha_e_com_ela_nao(self):
        # efeito horizonte: na profundidade 1 o motor vê "dama come peão" (+1) e
        # para; não vê que o peão de e6 retoma e a dama se perde
        tabuleiro = chess.Board(ARMADILHA)
        sem = motor(1, quiescencia=False).escolher_jogada(tabuleiro, tempo_limite=10)
        com = motor(1).escolher_jogada(tabuleiro, tempo_limite=10)
        self.assertEqual(tabuleiro.san(sem.movimento), "Qxd5")
        self.assertNotEqual(tabuleiro.san(com.movimento), "Qxd5")
        self.assertLess(abs(com.avaliacao - avaliar_posicional(tabuleiro)), 1)

    def test_ficar_parado_quando_capturar_e_ruim(self):
        # stand pat: a única captura perde a dama, então a nota é a da posição parada
        tabuleiro = chess.Board(ARMADILHA)
        self.assertEqual(Busca().quiescencia(tabuleiro), avaliar_posicional(tabuleiro))

    def test_captura_quando_vale_a_pena(self):
        tabuleiro = chess.Board(PEAO_SOLTO)
        nota = Busca().quiescencia(tabuleiro)
        tabuleiro.push_san("Qxd5")
        self.assertEqual(nota, avaliar_posicional(tabuleiro))

    def test_posicao_quieta_vale_a_avaliacao(self):
        tabuleiro = chess.Board()  # nenhuma captura possível
        self.assertEqual(Busca().quiescencia(tabuleiro), avaliar_posicional(tabuleiro))

    def test_mate_continua_valendo_mate(self):
        tabuleiro = chess.Board()
        for san in ("f3", "e5", "g4", "Qh4"):
            tabuleiro.push_san(san)
        self.assertEqual(Busca().quiescencia(tabuleiro), -MATE)

    def test_mesma_nota_que_a_quiescencia_sem_poda(self):
        # a versão sem poda explode em posições com muitas capturas; aqui só trocas curtas
        for fen in (ARMADILHA, PEAO_SOLTO, DAMA_SOLTA, TROCA_CURTA, TROCA_COM_TORRES):
            with self.subTest(fen=fen):
                pura, podada = Busca(), Busca()
                self.assertEqual(podada.quiescencia(chess.Board(fen)),
                                 pura.quiescencia_pura(chess.Board(fen), ply=0))
                self.assertLessEqual(podada.nos, pura.nos)

    def test_nao_altera_o_tabuleiro(self):
        tabuleiro = chess.Board(TROCAS)
        Busca().quiescencia(tabuleiro)
        self.assertEqual(tabuleiro.fen(), TROCAS)


class TestOrdenacao(unittest.TestCase):
    def test_mvv_lva(self):
        # peão e dama podem capturar a torre de d5; a captura com o peão vem primeiro
        tabuleiro = chess.Board("4k3/8/8/3r4/4P3/8/8/3QK3 w - - 0 1")
        primeiros = [tabuleiro.san(m) for m in Busca.ordenar(tabuleiro)[:2]]
        self.assertEqual(primeiros, ["exd5", "Qxd5"])

    def test_capturas_antes_dos_lances_quietos(self):
        tabuleiro = chess.Board(TROCAS)
        lances = Busca.ordenar(tabuleiro)
        capturas = [tabuleiro.is_capture(m) for m in lances]
        self.assertEqual(capturas, sorted(capturas, reverse=True))


class TestAprofundamentoIterativo(unittest.TestCase):
    def test_com_tempo_sobrando_da_a_mesma_nota_da_profundidade_fixa(self):
        # as rodadas menores e a troca de ordem não podem mudar a nota final
        for fen in (chess.STARTING_FEN, DAMA_SOLTA, TROCAS, MEIO_JOGO):
            with self.subTest(fen=fen):
                m = motor(3)
                jogada = m.escolher_jogada(chess.Board(fen), tempo_limite=1000)
                self.assertEqual(m.profundidade_alcancada, 3)
                self.assertFalse(m.parou_por_tempo)
                self.assertEqual(jogada.avaliacao, Busca().alfa_beta(chess.Board(fen), 3))

    def test_sem_tempo_fica_na_profundidade_1(self):
        tabuleiro = chess.Board(MEIO_JOGO)
        m = motor(4)
        jogada = m.escolher_jogada(tabuleiro, tempo_limite=0)
        self.assertEqual(m.profundidade_alcancada, 1)
        self.assertTrue(m.parou_por_tempo)
        self.assertIn(jogada.movimento, tabuleiro.legal_moves)
        self.assertEqual(tabuleiro.fen(), MEIO_JOGO)

    def test_interromper_no_meio_devolve_a_rodada_anterior_e_limpa_o_tabuleiro(self):
        # prazo já vencido, mas sem a regra de "não começar rodada nova":
        # a rodada 2 começa e é interrompida pela exceção TempoEsgotado
        classe = type("MotorApressado", (MotorMinimax,),
                      {"profundidade": 4, "FRACAO_PRAZO": 0.0, "FRACAO_NOVA_RODADA": math.inf})
        m = classe()
        tabuleiro = chess.Board(MEIO_JOGO)
        rodada_1 = motor(1).escolher_jogada(chess.Board(MEIO_JOGO), tempo_limite=1000)
        jogada = m.escolher_jogada(tabuleiro, tempo_limite=1000)
        self.assertEqual(m.profundidade_alcancada, 1)
        self.assertTrue(m.parou_por_tempo)
        self.assertEqual(jogada.movimento, rodada_1.movimento)
        self.assertEqual(tabuleiro.fen(), MEIO_JOGO)
        self.assertEqual(len(tabuleiro.move_stack), 0)

    def test_mate_encontrado_para_a_busca(self):
        m = motor(4)
        tabuleiro = chess.Board(MATE_EM_1_BRANCAS)
        jogada = m.escolher_jogada(tabuleiro, tempo_limite=1000)
        self.assertEqual(m.profundidade_alcancada, 1)
        self.assertFalse(m.parou_por_tempo)  # parou por ter achado mate, não por tempo
        self.assertEqual(tabuleiro.san(jogada.movimento), "Ra8#")


class TestRegistroMinimax(unittest.TestCase):
    def test_niveis_registrados(self):
        for classe, profundidade in ((MotorMinimaxFacil, 2), (MotorMinimaxMedio, 3),
                                     (MotorMinimaxDificil, 4)):
            self.assertIs(MOTORES[classe.chave], classe)
            self.assertIs(motor_por_nome(classe.nome), classe)
            self.assertEqual(classe.profundidade, profundidade)


if __name__ == "__main__":
    unittest.main()

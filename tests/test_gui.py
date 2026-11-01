"""Testes de integração da interface: simulam cliques e arrastos no tabuleiro.

Precisam de uma tela; sem ela, são pulados.
"""

import os
import tempfile
import time
import unittest
from unittest import mock

try:
    import tkinter as tk
    from tkinter import messagebox
except ImportError:
    tk = None

from src.persistence import database_manager as banco


def _criar_raiz():
    if tk is None:
        raise unittest.SkipTest("tkinter não está instalado")
    try:
        return tk.Tk()
    except tk.TclError as erro:
        raise unittest.SkipTest(f"sem tela gráfica disponível: {erro}")


class TestInterface(unittest.TestCase):
    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        self._caminho_original = banco.CAMINHO_DB
        banco.CAMINHO_DB = os.path.join(self._pasta.name, "gui.db")
        self.raiz = _criar_raiz()
        # as confirmações respondem "Sim"
        self._patch = mock.patch.object(messagebox, "askyesno", return_value=True)
        self._patch.start()
        from src.gui.app import AplicacaoXadrez
        self.app = AplicacaoXadrez(self.raiz)
        self._esperar(lambda: self.app.partida_id is not None)

    def tearDown(self):
        self._patch.stop()
        try:
            self.app.sair()
        except tk.TclError:
            pass
        banco.CAMINHO_DB = self._caminho_original
        self._pasta.cleanup()

    def _esperar(self, condicao, limite=5.0):
        fim = time.monotonic() + limite
        while time.monotonic() < fim:
            self.raiz.update()
            if condicao():
                return
            time.sleep(0.02)
        self.fail("condição não atingida a tempo")

    def _centro(self, casa):
        x, y = self.app.tabuleiro._canto(casa)
        meio = self.app.tabuleiro._lado // 2
        return x + meio, y + meio

    def _clicar(self, casa):
        x, y = self._centro(casa)
        self.app.tabuleiro.event_generate("<ButtonPress-1>", x=x, y=y)
        self.app.tabuleiro.event_generate("<ButtonRelease-1>", x=x, y=y)
        self.raiz.update()

    def _arrastar(self, origem, destino):
        x0, y0 = self._centro(origem)
        x1, y1 = self._centro(destino)
        canvas = self.app.tabuleiro
        canvas.event_generate("<ButtonPress-1>", x=x0, y=y0)
        canvas.event_generate("<B1-Motion>", x=(x0 + x1) // 2, y=(y0 + y1) // 2)
        canvas.event_generate("<B1-Motion>", x=x1, y=y1)
        canvas.event_generate("<ButtonRelease-1>", x=x1, y=y1)
        self.raiz.update()

    def test_clique_humano_e_resposta_da_ia_sao_salvos(self):
        self.raiz.update()
        self._clicar("e2")
        self.assertEqual(self.app.selecionada, "e2")
        self._clicar("e4")
        self.assertEqual(self.app.jogo.lances_san()[0], "e4")
        self._esperar(lambda: self.app.jogo.total_meios_lances() == 2)
        self.assertEqual(banco.obter_jogadas(self.app.partida_id), self.app.jogo.lances_san())

    def test_arrastar_peca(self):
        self.raiz.update()
        self._arrastar("g1", "f3")
        self.assertEqual(self.app.jogo.lances_san()[0], "Nf3")

    def test_lance_ilegal_nao_altera_o_tabuleiro(self):
        self.raiz.update()
        matriz = self.app.jogo.obter_matriz()
        self._clicar("d1")
        self._clicar("d4")
        self.assertEqual(self.app.jogo.obter_matriz(), matriz)
        self.assertIn("dama", self.app.lbl_mensagem.cget("text"))

    def test_mate_em_dois_jogadores_grava_resultado(self):
        from src.gui.dialogos import ConfiguracaoPartida
        self.app._iniciar(ConfiguracaoPartida(contra_ia=False))
        self.raiz.update()
        for origem, destino in (("f2", "f3"), ("e7", "e5"), ("g2", "g4"), ("d8", "h4")):
            self._clicar(origem)
            self._clicar(destino)
        self.assertEqual(banco.obter_partida(self.app.partida_id)["resultado"],
                         "Vitória das pretas (xeque-mate)")
        self.assertTrue(self.app.tabuleiro.tem_sobreposicao)

    def test_lance_digitado(self):
        self.raiz.update()
        self.app.campo_lance.insert(0, "Nc3")
        self.app.jogar_digitado()
        self.assertEqual(self.app.jogo.lances_san()[0], "Nc3")

    def test_partida_interrompida_fica_disponivel_para_retomar(self):
        self.raiz.update()
        self._clicar("e2")
        self._clicar("e4")
        self._esperar(lambda: self.app.jogo.total_meios_lances() == 2)
        partida = self.app.partida_id
        self.app.sair()
        pendente = banco.buscar_partida_em_andamento()
        self.assertEqual((pendente["id"], pendente["total_lances"]), (partida, 2))


if __name__ == "__main__":
    unittest.main()

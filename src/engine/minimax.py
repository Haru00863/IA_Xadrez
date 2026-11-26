"""Motor Minimax com poda Alfa-Beta, quiescência e aprofundamento iterativo.

Ideia geral:
- A partir da posição atual, o motor imagina todos os lances, depois todas as
  respostas, e assim por diante até ``profundidade`` meios-lances (plies).
- Nas folhas dessa árvore aplica a função de avaliação (nota das brancas).
  Antes disso, a busca de quiescência continua só com capturas até a posição
  ficar "quieta", para não avaliar no meio de uma troca (efeito horizonte).
- Sobe a árvore escolhendo: nos nós em que as brancas jogam, o MAIOR valor dos
  filhos (MAX); nos nós em que as pretas jogam, o MENOR (MIN).

A busca não sabe nada de "como avaliar": recebe um ``Avaliador`` pronto. É esse
encaixe que permite trocar a heurística (ou uma rede treinada) mais tarde.
"""

from __future__ import annotations

import math
import time

import chess

from .avaliacao import Avaliador, avaliar_posicional
from .base import JogadaMotor, MotorDecisao

# Nota de um xeque-mate. Bem maior que qualquer diferença de material (máx. ~39).
MATE = 1000.0

# A busca olha o relógio só a cada tantos nós: olhar sempre custaria caro.
INTERVALO_RELOGIO = 1024


class TempoEsgotado(Exception):
    """Lançada no meio da busca quando o prazo acaba."""


# Valores usados só para ordenar capturas (MVV-LVA). O rei como atacante vale
# muito para ficar por último: capturar com o rei costuma ser arriscado.
VALOR_ORDEM = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
               chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100}


class Busca:
    """Guarda o avaliador e conta os nós visitados (estatística para comparar podas).

    ``quiescencia=False`` desliga a busca de quiescência: as folhas são avaliadas
    direto, como antes. Serve para comparar e para mostrar o efeito horizonte.
    """

    def __init__(self, avaliador: Avaliador = avaliar_posicional, quiescencia: bool = True,
                 prazo: float | None = None):
        self.avaliador = avaliador
        self.usar_quiescencia = quiescencia
        self.prazo = prazo  # instante (time.perf_counter) em que a busca deve parar; None = sem prazo
        self.nos = 0

    def contar_no(self) -> None:
        """Conta um nó e, de vez em quando, confere se o prazo acabou."""
        self.nos += 1
        if (self.prazo is not None and self.nos % INTERVALO_RELOGIO == 0
                and time.perf_counter() > self.prazo):
            raise TempoEsgotado

    # ------------------------------------------------------------ apoio

    def nota_fim_de_jogo(self, tabuleiro: chess.Board, ply: int) -> float | None:
        """Nota da posição se a partida acabou nela; ``None`` se ela continua.

        ``ply`` é a distância até a raiz. Subtraí-lo da nota de mate faz o motor
        preferir o mate mais rápido e, quando perde, adiar o mate o máximo possível.
        """
        if not any(tabuleiro.legal_moves):  # any() para no primeiro lance: é barato
            if tabuleiro.is_check():
                # quem tem a vez levou mate
                return -(MATE - ply) if tabuleiro.turn == chess.WHITE else (MATE - ply)
            return 0.0  # afogamento
        if tabuleiro.is_insufficient_material() or tabuleiro.is_fifty_moves():
            return 0.0
        # Repetição: se a posição já apareceu antes (na partida ou nesta linha da
        # busca), tratamos como empate. Quem está ganhando passa a evitar o
        # vaivém; quem está perdendo passa a buscá-lo. A raiz (ply 0) fica de fora:
        # ela é a posição atual, e o motor precisa jogar a partir dela.
        if ply > 0 and tabuleiro.is_repetition(2):
            return 0.0
        return None

    @staticmethod
    def chave_ordem(tabuleiro: chess.Board, lance: chess.Move) -> tuple:
        """Capturas primeiro, em ordem MVV-LVA: a vítima mais valiosa antes e,
        entre vítimas iguais, o atacante mais barato antes (PxD antes de DxP).
        """
        if not tabuleiro.is_capture(lance):
            return (1, 0, 0)
        # no en passant a casa de destino está vazia, mas a vítima é um peão
        vitima = tabuleiro.piece_type_at(lance.to_square) or chess.PAWN
        atacante = tabuleiro.piece_type_at(lance.from_square)
        return (0, -VALOR_ORDEM[vitima], VALOR_ORDEM[atacante])

    @classmethod
    def ordenar(cls, tabuleiro: chess.Board) -> list[chess.Move]:
        """Ordena os lances legais. Não muda o resultado; só ajuda a poda a cortar cedo."""
        return sorted(tabuleiro.legal_moves, key=lambda lance: cls.chave_ordem(tabuleiro, lance))

    @classmethod
    def lances_quiescencia(cls, tabuleiro: chess.Board) -> list[chess.Move]:
        """Em xeque: todas as respostas (não dá para "ficar parado"). Fora dele: só capturas."""
        if tabuleiro.is_check():
            return cls.ordenar(tabuleiro)
        return sorted(tabuleiro.generate_legal_captures(),
                      key=lambda lance: cls.chave_ordem(tabuleiro, lance))

    # ------------------------------------------------------- Minimax puro

    def minimax(self, tabuleiro: chess.Board, profundidade: int, ply: int = 0) -> float:
        """Minimax sem poda. Usado como referência nos testes e para explicar o conceito."""
        if profundidade == 0 and self.usar_quiescencia:
            return self.quiescencia_pura(tabuleiro, ply)
        self.contar_no()
        fim = self.nota_fim_de_jogo(tabuleiro, ply)
        if fim is not None:
            return fim
        if profundidade == 0:
            return self.avaliador(tabuleiro)

        if tabuleiro.turn == chess.WHITE:  # MAX
            melhor = -math.inf
            for lance in self.ordenar(tabuleiro):
                tabuleiro.push(lance)
                melhor = max(melhor, self.minimax(tabuleiro, profundidade - 1, ply + 1))
                tabuleiro.pop()
        else:  # MIN
            melhor = math.inf
            for lance in self.ordenar(tabuleiro):
                tabuleiro.push(lance)
                melhor = min(melhor, self.minimax(tabuleiro, profundidade - 1, ply + 1))
                tabuleiro.pop()
        return melhor

    def quiescencia_pura(self, tabuleiro: chess.Board, ply: int) -> float:
        """Quiescência sem poda: referência de teste para ``quiescencia``.

        Fora de xeque, quem joga pode "ficar parado" (stand pat): a nota da
        posição como está já é uma opção, e uma captura só é escolhida se for
        melhor que ela. Em xeque não existe essa opção.
        """
        self.contar_no()
        fim = self.nota_fim_de_jogo(tabuleiro, ply)
        if fim is not None:
            return fim
        brancas = tabuleiro.turn == chess.WHITE
        if tabuleiro.is_check():
            melhor = -math.inf if brancas else math.inf
        else:
            melhor = self.avaliador(tabuleiro)  # stand pat
        for lance in self.lances_quiescencia(tabuleiro):
            tabuleiro.push(lance)
            nota = self.quiescencia_pura(tabuleiro, ply + 1)
            tabuleiro.pop()
            melhor = max(melhor, nota) if brancas else min(melhor, nota)
        return melhor

    # ------------------------------------------------- Minimax + Alfa-Beta

    def alfa_beta(self, tabuleiro: chess.Board, profundidade: int,
                  alfa: float = -math.inf, beta: float = math.inf, ply: int = 0) -> float:
        """Mesmo resultado do ``minimax``, visitando menos nós.

        alfa: a melhor nota que as brancas (MAX) já têm garantida em algum caminho.
        beta: a melhor nota que as pretas (MIN) já têm garantida em algum caminho.
        Quando alfa >= beta, o adversário nunca deixaria o jogo chegar aqui,
        então os lances restantes deste nó podem ser ignorados (poda).
        """
        if profundidade == 0 and self.usar_quiescencia:
            return self.quiescencia(tabuleiro, alfa, beta, ply)
        self.contar_no()
        fim = self.nota_fim_de_jogo(tabuleiro, ply)
        if fim is not None:
            return fim
        if profundidade == 0:
            return self.avaliador(tabuleiro)

        if tabuleiro.turn == chess.WHITE:  # MAX
            melhor = -math.inf
            for lance in self.ordenar(tabuleiro):
                tabuleiro.push(lance)
                nota = self.alfa_beta(tabuleiro, profundidade - 1, alfa, beta, ply + 1)
                tabuleiro.pop()
                melhor = max(melhor, nota)
                alfa = max(alfa, melhor)
                if alfa >= beta:
                    break  # poda beta: as pretas já têm algo melhor em outro ramo
        else:  # MIN
            melhor = math.inf
            for lance in self.ordenar(tabuleiro):
                tabuleiro.push(lance)
                nota = self.alfa_beta(tabuleiro, profundidade - 1, alfa, beta, ply + 1)
                tabuleiro.pop()
                melhor = min(melhor, nota)
                beta = min(beta, melhor)
                if alfa >= beta:
                    break  # poda alfa: as brancas já têm algo melhor em outro ramo
        return melhor

    def quiescencia(self, tabuleiro: chess.Board, alfa: float = -math.inf,
                    beta: float = math.inf, ply: int = 0) -> float:
        """Busca de quiescência com poda Alfa-Beta: mesmo resultado de ``quiescencia_pura``.

        Chamada quando a profundidade acaba. Continua só com capturas (ou com as
        respostas ao xeque) até a posição ficar quieta, e só então confia no
        avaliador. Não tem limite de profundidade: termina porque cada captura
        tira uma peça do tabuleiro.
        """
        self.contar_no()
        fim = self.nota_fim_de_jogo(tabuleiro, ply)
        if fim is not None:
            return fim

        if tabuleiro.turn == chess.WHITE:  # MAX
            if tabuleiro.is_check():
                melhor = -math.inf
            else:
                melhor = self.avaliador(tabuleiro)  # stand pat
                if melhor >= beta:
                    return melhor  # ficar parado já é bom demais para as pretas permitirem
                alfa = max(alfa, melhor)
            for lance in self.lances_quiescencia(tabuleiro):
                tabuleiro.push(lance)
                nota = self.quiescencia(tabuleiro, alfa, beta, ply + 1)
                tabuleiro.pop()
                melhor = max(melhor, nota)
                alfa = max(alfa, melhor)
                if alfa >= beta:
                    break
        else:  # MIN
            if tabuleiro.is_check():
                melhor = math.inf
            else:
                melhor = self.avaliador(tabuleiro)  # stand pat
                if melhor <= alfa:
                    return melhor
                beta = min(beta, melhor)
            for lance in self.lances_quiescencia(tabuleiro):
                tabuleiro.push(lance)
                nota = self.quiescencia(tabuleiro, alfa, beta, ply + 1)
                tabuleiro.pop()
                melhor = min(melhor, nota)
                beta = min(beta, melhor)
                if alfa >= beta:
                    break
        return melhor


class MotorMinimax(MotorDecisao):
    """Escolhe o lance com Alfa-Beta, aprofundando aos poucos até a profundidade ou o tempo acabar.

    Aprofundamento iterativo: busca com profundidade 1, depois 2, 3... até
    ``profundidade``. Se o tempo acabar no meio de uma rodada, usa o melhor lance
    da última rodada completa. Assim o motor respeita o ``tempo_limite`` com
    qualquer avaliador, rápido ou lento.
    """

    chave = "minimax"
    nome = "Minimax"
    descricao = "Busca Minimax com poda Alfa-Beta, quiescência e avaliação por material e posição."
    profundidade = 3  # profundidade máxima

    # fração do tempo_limite usada como prazo final (sobra margem para a interface)
    FRACAO_PRAZO = 0.9
    # se já gastou esta fração, não começa outra rodada: a próxima custa várias vezes mais
    FRACAO_NOVA_RODADA = 0.5

    def __init__(self, avaliador: Avaliador = avaliar_posicional, quiescencia: bool = True):
        self.avaliador = avaliador
        self.quiescencia = quiescencia
        # da última jogada; úteis para testes e estatísticas
        self.profundidade_alcancada = 0
        self.parou_por_tempo = False  # True se o tempo impediu chegar à profundidade máxima

    def buscar_raiz(self, tabuleiro: chess.Board, busca: Busca, profundidade: int,
                    lances: list[chess.Move]) -> tuple[chess.Move, float]:
        """Uma rodada completa: o melhor lance da raiz nesta profundidade."""
        brancas = tabuleiro.turn == chess.WHITE
        alfa, beta = -math.inf, math.inf
        melhor_lance, melhor_nota = None, None
        for lance in lances:
            tabuleiro.push(lance)  # pode alterar: é uma cópia, e o pop desfaz
            nota = busca.alfa_beta(tabuleiro, profundidade - 1, alfa, beta, ply=1)
            tabuleiro.pop()
            # comparação estrita: em notas iguais fica o primeiro (resultado reproduzível)
            if melhor_nota is None or (nota > melhor_nota if brancas else nota < melhor_nota):
                melhor_lance, melhor_nota = lance, nota
                if brancas:
                    alfa = nota
                else:
                    beta = nota
        return melhor_lance, melhor_nota

    def escolher_jogada(self, tabuleiro: chess.Board, tempo_limite: float) -> JogadaMotor:
        lances = Busca.ordenar(tabuleiro)
        if not lances:
            raise ValueError("Não há lances legais nesta posição.")

        inicio = time.perf_counter()
        busca = Busca(self.avaliador, self.quiescencia)
        tamanho_pilha = len(tabuleiro.move_stack)
        melhor_lance, melhor_nota, alcancada = None, None, 0
        parou_por_tempo = False

        for profundidade in range(1, self.profundidade + 1):
            if profundidade > 1:
                gasto = time.perf_counter() - inicio
                if gasto > tempo_limite * self.FRACAO_NOVA_RODADA:
                    parou_por_tempo = True
                    break
                # a profundidade 1 sempre termina; daqui em diante vale o prazo
                busca.prazo = inicio + tempo_limite * self.FRACAO_PRAZO
                # o melhor lance da rodada anterior vai primeiro: ele costuma
                # continuar sendo o melhor, e isso faz a poda cortar mais cedo
                lances.remove(melhor_lance)
                lances.insert(0, melhor_lance)
            try:
                melhor_lance, melhor_nota = self.buscar_raiz(tabuleiro, busca, profundidade, lances)
            except TempoEsgotado:
                # a busca parou no meio: desfaz os lances que ficaram no tabuleiro
                # e fica com o resultado da última rodada completa
                while len(tabuleiro.move_stack) > tamanho_pilha:
                    tabuleiro.pop()
                parou_por_tempo = True
                break
            alcancada = profundidade
            # Mate a até `profundidade` meios-lances: a busca completa já viu todas
            # as alternativas, então ir mais fundo não acha um mate mais curto (nem
            # escapa de um mate contra nós). Um mate achado só na quiescência pode
            # estar mais longe que isso, e aí a busca continua.
            meios_lances_ate_mate = MATE - abs(melhor_nota)
            if meios_lances_ate_mate <= profundidade:
                break

        self.profundidade_alcancada = alcancada
        self.parou_por_tempo = parou_por_tempo
        segundos = time.perf_counter() - inicio
        return JogadaMotor(melhor_lance, avaliacao=melhor_nota,
                           detalhes=f"profundidade {alcancada}/{self.profundidade}"
                                    f"{' + quiescência' if self.quiescencia else ''}, "
                                    f"{busca.nos} nós, {segundos:.2f} s")


# Níveis de dificuldade: só muda a profundidade. O registro cria motores sem
# argumentos, por isso cada nível é uma classe.

class MotorMinimaxFacil(MotorMinimax):
    chave = "minimax_facil"
    nome = "Minimax (fácil)"
    descricao = "Minimax com Alfa-Beta, olhando até 2 meios-lances à frente e depois as capturas."
    profundidade = 2


class MotorMinimaxMedio(MotorMinimax):
    chave = "minimax_medio"
    nome = "Minimax (médio)"
    descricao = "Minimax com Alfa-Beta, olhando até 3 meios-lances à frente e depois as capturas."
    profundidade = 3


class MotorMinimaxDificil(MotorMinimax):
    chave = "minimax_dificil"
    nome = "Minimax (difícil)"
    descricao = "Minimax com Alfa-Beta, olhando até 4 meios-lances à frente e depois as capturas."
    profundidade = 4

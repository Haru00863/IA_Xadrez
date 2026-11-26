"""
Torneio entre os motores do projeto, com o Stockfish como adversário e como juiz.

O que o script mede:
- Confrontos: todos contra todos. Cada partida começa de uma abertura curta
  (os motores Minimax são determinísticos e repetiriam sempre a mesma partida),
  e cada abertura é jogada duas vezes, trocando as cores. As aberturas são
  sorteadas (padrão) ou tiradas de um livro de aberturas reais (--livro).
- Pontuação: vitória = 1, empate = 0,5, derrota = 0.
- Tempo médio por lance de cada motor.
- Com o Stockfish instalado, ele também analisa cada lance dos nossos motores:
    concordância: % de lances iguais ao melhor lance do Stockfish;
    ACPL (average centipawn loss): quanto, em média, o lance escolhido piora a
    posição em relação ao melhor lance, em centésimos de peão. Quanto menor,
    mais forte. As notas são limitadas a ±1000, como no Lichess.

Uso (a partir da raiz do projeto):
    .venv/bin/python scripts/torneio.py
    .venv/bin/python scripts/torneio.py --aberturas 4 --pgn partidas.pgn
    .venv/bin/python scripts/torneio.py --motores minimax_facil minimax_dificil --sem-stockfish
    .venv/bin/python scripts/torneio.py --stockfish /caminho/stockfish --sf-niveis 0 5
    .venv/bin/python scripts/torneio.py --ao-vivo 1      # assiste, 1 s entre lances
    .venv/bin/python scripts/torneio.py --processos 6    # 6 partidas ao mesmo tempo
    .venv/bin/python scripts/torneio.py --livro          # 50 aberturas reais

O Stockfish é procurado no PATH (no Arch/CachyOS: sudo pacman -S stockfish).
Sem ele, o torneio roda só entre os motores do projeto e sem análise.
"""

from __future__ import annotations

import argparse
import multiprocessing
import os
import random
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import chess
import chess.engine
import chess.pgn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.engine import MOTORES, TEMPO_LIMITE_PADRAO, criar_motor  # noqa: E402

from livro_aberturas import LIVRO  # noqa: E402  (mesma pasta deste script)

LIMITE_NOTA = 1000  # centipeões; notas maiores (e mates) são cortadas aqui


# ---------------------------------------------------------------- jogadores

class Jogador:
    nome: str
    analisar: bool = False  # True = o juiz analisa os lances deste jogador

    def escolher(self, tabuleiro: chess.Board) -> chess.Move:
        raise NotImplementedError


class JogadorMotor(Jogador):
    """Um motor do projeto (src/engine)."""

    def __init__(self, chave: str):
        self.motor = criar_motor(chave)
        self.nome = self.motor.nome
        self.analisar = chave != "aleatorio"

    def escolher(self, tabuleiro: chess.Board) -> chess.Move:
        return self.motor.escolher_jogada(tabuleiro.copy(), TEMPO_LIMITE_PADRAO).movimento

    def ultima_busca_incompleta(self) -> bool:
        """True se o tempo cortou a última busca antes da profundidade máxima do nível.

        Parar mais cedo por ter achado mate não conta. Só os motores Minimax têm
        esse atributo; os outros nunca ficam incompletos.
        """
        return getattr(self.motor, "parou_por_tempo", False)


class JogadorStockfish(Jogador):
    """Stockfish enfraquecido pelo "Skill Level" (0 = mais fraco, 20 = máximo)."""

    def __init__(self, caminho: str, nivel: int, tempo: float):
        self.engine = chess.engine.SimpleEngine.popen_uci(caminho)
        self.engine.configure({"Skill Level": nivel, "Threads": 1})
        self.limite = chess.engine.Limit(time=tempo)
        self.nome = f"Stockfish (nível {nivel})"

    def escolher(self, tabuleiro: chess.Board) -> chess.Move:
        return self.engine.play(tabuleiro, self.limite).move

    def fechar(self) -> None:
        self.engine.quit()


# ------------------------------------------------------------------- juiz

class Juiz:
    """Stockfish em força máxima, usado só para avaliar posições."""

    def __init__(self, caminho: str, profundidade: int):
        self.engine = chess.engine.SimpleEngine.popen_uci(caminho)
        self.engine.configure({"Threads": 1})  # resultado igual com 1 ou vários processos
        self.limite = chess.engine.Limit(depth=profundidade)

    def analisar(self, tabuleiro: chess.Board) -> tuple[int, Optional[chess.Move]]:
        """Nota (centipeões, perspectiva das brancas, cortada em ±1000) e melhor lance."""
        if tabuleiro.is_game_over(claim_draw=True):
            resultado = tabuleiro.outcome(claim_draw=True)
            if resultado.winner is None:
                return 0, None
            return (LIMITE_NOTA if resultado.winner == chess.WHITE else -LIMITE_NOTA), None
        info = self.engine.analyse(tabuleiro, self.limite)
        nota = info["score"].white().score(mate_score=100_000)
        melhor = info["pv"][0] if info.get("pv") else None
        return max(-LIMITE_NOTA, min(LIMITE_NOTA, nota)), melhor

    def fechar(self) -> None:
        self.engine.quit()


def perda_do_lance(nota_antes: int, nota_depois: int, cor: chess.Color) -> int:
    """Quanto o lance piorou a posição para quem jogou (nunca negativo)."""
    sinal = 1 if cor == chess.WHITE else -1
    return max(0, sinal * (nota_antes - nota_depois))


# ---------------------------------------------------------- estatísticas

@dataclass
class Estatisticas:
    pontos: float = 0.0
    partidas: int = 0
    vitorias: int = 0
    empates: int = 0
    derrotas: int = 0
    lances: int = 0
    tempo_total: float = 0.0
    analisados: int = 0
    iguais_ao_melhor: int = 0
    perda_total: int = 0
    prof_incompleta: int = 0  # lances em que o tempo cortou a busca antes da profundidade máxima
    contra: dict[str, float] = field(default_factory=dict)  # pontos por adversário

    def somar(self, outra: "Estatisticas") -> None:
        for nome in ("pontos", "partidas", "vitorias", "empates", "derrotas", "lances",
                     "tempo_total", "analisados", "iguais_ao_melhor", "perda_total",
                     "prof_incompleta"):
            setattr(self, nome, getattr(self, nome) + getattr(outra, nome))
        for adversario, pontos in outra.contra.items():
            self.contra[adversario] = self.contra.get(adversario, 0.0) + pontos


# --------------------------------------------------------------- ao vivo

FUNDO_CLARO, FUNDO_ESCURO, FUNDO_LANCE = "\033[48;5;180m", "\033[48;5;137m", "\033[48;5;143m"
PECA_BRANCA, PECA_PRETA, RESET = "\033[1;38;5;231m", "\033[1;38;5;16m", "\033[0m"


def desenhar(tabuleiro: chess.Board, titulo: str, brancas: Jogador, pretas: Jogador,
             ultimo_san: str, nota: Optional[int]) -> None:
    """Limpa o terminal e desenha o tabuleiro colorido, com o último lance destacado."""
    ultimo = tabuleiro.peek() if tabuleiro.move_stack else None
    destaque = {ultimo.from_square, ultimo.to_square} if ultimo else set()
    linhas = ["\033[2J\033[H" + titulo, f"  Brancas: {brancas.nome}    Pretas: {pretas.nome}", ""]
    for fileira in range(7, -1, -1):
        linha = f" {fileira + 1} "
        for coluna in range(8):
            casa = chess.square(coluna, fileira)
            if casa in destaque:
                fundo = FUNDO_LANCE
            else:
                fundo = FUNDO_CLARO if (fileira + coluna) % 2 else FUNDO_ESCURO
            peca = tabuleiro.piece_at(casa)
            if peca:
                # glifo "cheio" para as duas cores; a cor vem do texto
                glifo = chess.UNICODE_PIECE_SYMBOLS[peca.symbol().lower()]
                cor = PECA_BRANCA if peca.color == chess.WHITE else PECA_PRETA
                linha += f"{fundo}{cor} {glifo} {RESET}"
            else:
                linha += f"{fundo}   {RESET}"
        linhas.append(linha)
    linhas.append("    " + "  ".join("abcdefgh"))
    linhas.append("")
    lance_num = (len(tabuleiro.move_stack) + 1) // 2
    linhas.append(f"  Lance {lance_num}: {ultimo_san or '-'}")
    if nota is not None:
        quem = "brancas melhor" if nota > 0 else "pretas melhor" if nota < 0 else "igual"
        linhas.append(f"  Juiz (Stockfish): {nota / 100:+.2f}  ({quem})")
    print("\n".join(linhas), flush=True)


# ---------------------------------------------------------------- partida

def sortear_abertura(rng: random.Random, meios_lances: int) -> list[chess.Move]:
    while True:
        tabuleiro = chess.Board()
        lances = []
        for _ in range(meios_lances):
            lance = rng.choice(list(tabuleiro.legal_moves))
            tabuleiro.push(lance)
            lances.append(lance)
        if not tabuleiro.is_game_over():
            return lances


def jogar_partida(brancas: Jogador, pretas: Jogador, abertura: list[chess.Move],
                  max_meios_lances: int, juiz: Optional[Juiz],
                  stats: dict[str, Estatisticas], ao_vivo: Optional[float] = None,
                  titulo: str = "") -> chess.pgn.Game:
    tabuleiro = chess.Board()
    for lance in abertura:
        tabuleiro.push(lance)

    nota, melhor = juiz.analisar(tabuleiro) if juiz else (0, None)
    while not tabuleiro.is_game_over(claim_draw=True) and len(tabuleiro.move_stack) < max_meios_lances:
        jogador = brancas if tabuleiro.turn == chess.WHITE else pretas
        cor = tabuleiro.turn
        inicio = time.perf_counter()
        lance = jogador.escolher(tabuleiro)
        decorrido = time.perf_counter() - inicio
        if lance not in tabuleiro.legal_moves:
            raise RuntimeError(f"{jogador.nome} propôs lance ilegal: {lance}")
        san = tabuleiro.san(lance)
        tabuleiro.push(lance)

        s = stats[jogador.nome]
        s.lances += 1
        s.tempo_total += decorrido
        if isinstance(jogador, JogadorMotor) and jogador.ultima_busca_incompleta():
            s.prof_incompleta += 1
        if juiz:
            nota_depois, melhor_depois = juiz.analisar(tabuleiro)
            if jogador.analisar:
                s.analisados += 1
                s.iguais_ao_melhor += lance == melhor
                s.perda_total += perda_do_lance(nota, nota_depois, cor)
            nota, melhor = nota_depois, melhor_depois
        if ao_vivo is not None:
            desenhar(tabuleiro, titulo, brancas, pretas, san, nota if juiz else None)
            time.sleep(ao_vivo)

    resultado = tabuleiro.outcome(claim_draw=True)
    if resultado is None:
        texto, motivo = "1/2-1/2", f"limite de {max_meios_lances} meios-lances"
    else:
        texto, motivo = resultado.result(), resultado.termination.name.lower()

    pontos_brancas = {"1-0": 1.0, "0-1": 0.0}.get(texto, 0.5)
    for jogador, outro, pontos in ((brancas, pretas, pontos_brancas), (pretas, brancas, 1 - pontos_brancas)):
        s = stats[jogador.nome]
        s.partidas += 1
        s.pontos += pontos
        s.vitorias += pontos == 1.0
        s.empates += pontos == 0.5
        s.derrotas += pontos == 0.0
        s.contra[outro.nome] = s.contra.get(outro.nome, 0.0) + pontos

    jogo = chess.pgn.Game.from_board(tabuleiro)
    jogo.headers.update({"Event": "Torneio IA Xadrez", "White": brancas.nome,
                         "Black": pretas.nome, "Result": texto, "Termination": motivo})
    return jogo


# -------------------------------------------------------------- processos
#
# Cada partida é independente, então várias rodam ao mesmo tempo em processos
# separados (o Python só usa um núcleo por processo). Um jogador é identificado
# por uma "ficha" simples, que pode ser enviada entre processos:
# ("motor", chave) ou ("sf", nível).
#
# Os motores do projeto são criados uma vez por processo e reaproveitados. Já os
# Stockfish (juiz e adversários) são abertos no início de cada partida e fechados
# no fim: o python-chess mantém uma thread para cada Stockfish aberto, e ela
# impediria o processo filho de terminar. Abrir um Stockfish leva ~50 ms.

_config: dict = {}
_motores: dict[str, JogadorMotor] = {}


def nome_jogador(ficha: tuple) -> str:
    tipo, valor = ficha
    return MOTORES[valor].nome if tipo == "motor" else f"Stockfish (nível {valor})"


def iniciar_processo(config: dict) -> None:
    global _config
    _config = config
    _motores.clear()


def rodar_partida(n: int, ficha_brancas: tuple, ficha_pretas: tuple, abertura_uci: list[str],
                  nome_abertura: str) -> tuple[int, str, dict[str, Estatisticas], str]:
    """Joga uma partida e devolve (número, PGN em texto, estatísticas dela, resumo em texto)."""
    abertos: list = []  # Stockfish abertos nesta partida, fechados no finally

    def criar(ficha: tuple) -> Jogador:
        tipo, valor = ficha
        if tipo == "motor":
            if valor not in _motores:
                _motores[valor] = JogadorMotor(valor)
            return _motores[valor]
        sf = JogadorStockfish(_config["stockfish"], valor, _config["sf_tempo"])
        abertos.append(sf)
        return sf

    try:
        brancas, pretas = criar(ficha_brancas), criar(ficha_pretas)
        juiz = None
        if _config["stockfish"]:
            juiz = Juiz(_config["stockfish"], _config["profundidade_analise"])
            abertos.append(juiz)
        stats = {brancas.nome: Estatisticas(), pretas.nome: Estatisticas()}
        abertura = [chess.Move.from_uci(u) for u in abertura_uci]
        inicio = time.perf_counter()
        jogo = jogar_partida(brancas, pretas, abertura, _config["max_meios_lances"], juiz, stats,
                             _config["ao_vivo"], f"  Partida {n}/{_config['total']}")
    finally:
        for engine in abertos:
            engine.fechar()

    jogo.headers["Round"] = str(n)
    if nome_abertura:
        jogo.headers["Opening"] = nome_abertura
    h = jogo.headers
    abertura = f" [{nome_abertura}]" if nome_abertura else ""
    resumo = (f"partida {n}{abertura}: {h['White']} x {h['Black']}: {h['Result']} ({h['Termination']}, "
              f"{jogo.end().ply()} meios-lances, {time.perf_counter() - inicio:.0f} s)")
    return n, str(jogo), stats, resumo


def rodar_tarefa(tarefa: tuple) -> tuple:
    return rodar_partida(*tarefa)


# ------------------------------------------------------------- relatório

def imprimir_relatorio(nomes: list[str], stats: dict[str, Estatisticas], com_juiz: bool) -> None:
    ordem = sorted(nomes, key=lambda nome: -stats[nome].pontos / max(1, stats[nome].partidas))

    print("\n## Classificação\n")
    cab = "| Jogador | Partidas | V | E | D | Pontos | % | Tempo/lance | Prof. incompleta |"
    if com_juiz:
        cab += " Concordância | ACPL |"
    print(cab)
    print("|" + " --- |" * (cab.count("|") - 1))
    for nome in ordem:
        s = stats[nome]
        linha = (f"| {nome} | {s.partidas} | {s.vitorias} | {s.empates} | {s.derrotas} | "
                 f"{s.pontos:g} | {100 * s.pontos / max(1, s.partidas):.0f}% | "
                 f"{s.tempo_total / max(1, s.lances):.2f} s | {s.prof_incompleta} |")
        if com_juiz:
            if s.analisados:
                linha += (f" {100 * s.iguais_ao_melhor / s.analisados:.0f}% | "
                          f"{s.perda_total / s.analisados:.0f} |")
            else:
                linha += " - | - |"
        print(linha)

    print("\nProf. incompleta: lances em que o limite de tempo cortou a busca antes da "
          "profundidade máxima do nível. Com 0, o resultado não dependeu da velocidade da máquina.")

    print("\n## Confrontos (pontos da linha contra a coluna)\n")
    print("| | " + " | ".join(ordem) + " |")
    print("|" + " --- |" * (len(ordem) + 1))
    for a in ordem:
        celulas = ["-" if a == b else f"{stats[a].contra.get(b, 0):g}" for b in ordem]
        print(f"| {a} | " + " | ".join(celulas) + " |")


# ------------------------------------------------------------------ main

def versao_do_codigo() -> str:
    """Commit atual do repositório, para o relatório dizer qual código gerou o resultado."""
    raiz = Path(__file__).resolve().parent.parent
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=raiz,
                                capture_output=True, text=True, check=True).stdout.strip()
        sujo = subprocess.run(["git", "status", "--porcelain"], cwd=raiz,
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "desconhecido (fora de um repositório git)"
    return f"commit {commit}" + (" (com alterações não commitadas)" if sujo else "")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--motores", nargs="+", default=list(MOTORES),
                        help=f"chaves dos motores (padrão: todos: {' '.join(MOTORES)})")
    parser.add_argument("--aberturas", type=int, default=None,
                        help="aberturas por confronto; cada uma é jogada com as duas cores "
                             f"(padrão: 2 sorteadas, ou as {len(LIVRO)} do livro com --livro)")
    parser.add_argument("--livro", action="store_true",
                        help=f"usa o livro de {len(LIVRO)} aberturas reais (scripts/livro_aberturas.py) "
                             "em vez de sortear os primeiros lances")
    parser.add_argument("--meios-lances-abertura", type=int, default=4)
    parser.add_argument("--max-meios-lances", type=int, default=200,
                        help="partida mais longa que isso conta como empate (padrão: 200)")
    parser.add_argument("--semente", type=int, default=2026)
    parser.add_argument("--stockfish", default=shutil.which("stockfish"),
                        help="caminho do executável (padrão: procura no PATH)")
    parser.add_argument("--sem-stockfish", action="store_true", help="não usa o Stockfish")
    parser.add_argument("--sf-niveis", type=int, nargs="*", default=[0],
                        help="Skill Level dos Stockfish adversários (padrão: 0; vazio = nenhum)")
    parser.add_argument("--sf-tempo", type=float, default=0.05, help="segundos por lance do Stockfish adversário")
    parser.add_argument("--profundidade-analise", type=int, default=12)
    parser.add_argument("--pgn", help="salva todas as partidas neste arquivo PGN")
    parser.add_argument("--processos", type=int, default=1,
                        help=f"partidas jogadas ao mesmo tempo (padrão: 1; este PC tem {os.cpu_count()} "
                             "threads). Com --ao-vivo é sempre 1.")
    parser.add_argument("--ao-vivo", type=float, nargs="?", const=0.5, metavar="PAUSA",
                        help="desenha o tabuleiro no terminal a cada lance, com PAUSA segundos "
                             "entre os lances (padrão: 0.5)")
    args = parser.parse_args()

    for chave in args.motores:
        if chave not in MOTORES:
            parser.error(f"motor desconhecido: {chave} (opções: {' '.join(MOTORES)})")

    caminho_sf = None if args.sem_stockfish else args.stockfish
    if not args.sem_stockfish and not caminho_sf:
        print("Stockfish não encontrado: o torneio roda sem ele e sem análise. "
              "Instale (sudo pacman -S stockfish) ou use --stockfish CAMINHO.\n")
    processos = 1 if args.ao_vivo is not None else max(1, args.processos)

    fichas = [("motor", c) for c in args.motores]
    if caminho_sf:
        fichas += [("sf", n) for n in args.sf_niveis]
    nomes = [nome_jogador(f) for f in fichas]

    # aberturas: lista de (nome, lances em UCI); no sorteio o nome fica vazio
    if args.livro:
        livro = LIVRO[:args.aberturas] if args.aberturas else LIVRO
        aberturas = []
        for nome, lances_san in livro:
            tabuleiro = chess.Board()
            aberturas.append((nome, [tabuleiro.push_san(san).uci() for san in lances_san.split()]))
        descricao_aberturas = (f"{len(aberturas)} do livro de aberturas reais "
                               "(scripts/livro_aberturas.py)")
    else:
        rng = random.Random(args.semente)
        quantidade = args.aberturas or 2
        aberturas = [("", [m.uci() for m in sortear_abertura(rng, args.meios_lances_abertura)])
                     for _ in range(quantidade)]
        descricao_aberturas = (f"{quantidade} sorteadas com {args.meios_lances_abertura} "
                               f"meios-lances (semente {args.semente})")
    confrontos = [(a, b) for i, a in enumerate(fichas) for b in fichas[i + 1:]]
    tarefas = []
    for a, b in confrontos:
        for nome, abertura in aberturas:
            for brancas, pretas in ((a, b), (b, a)):
                tarefas.append((len(tarefas) + 1, brancas, pretas, abertura, nome))

    config = {"stockfish": caminho_sf, "profundidade_analise": args.profundidade_analise,
              "sf_tempo": args.sf_tempo, "max_meios_lances": args.max_meios_lances,
              "ao_vivo": args.ao_vivo, "total": len(tarefas)}

    # registra a configuração, para o resultado poder ser reproduzido e citado depois
    print("## Configuração\n")
    print(f"- Data: {datetime.now():%Y-%m-%d %H:%M}")
    print(f"- Jogadores: {', '.join(nomes)}")
    print(f"- Código: {versao_do_codigo()}")
    print(f"- Aberturas: {descricao_aberturas}, cada uma jogada com as duas cores")
    print(f"- Limite: {args.max_meios_lances} meios-lances por partida (acima disso, empate)")
    if caminho_sf:
        sf = chess.engine.SimpleEngine.popen_uci(caminho_sf)
        print(f"- Juiz: {sf.id.get('name', 'Stockfish')}, profundidade {args.profundidade_analise}, 1 thread")
        sf.quit()
    else:
        print("- Juiz: nenhum (sem análise de concordância e ACPL)")
    print(f"- Processos em paralelo: {processos}")
    print(f"- Comando: {' '.join(sys.argv)}\n", flush=True)

    stats = {nome: Estatisticas() for nome in nomes}
    arquivo_pgn = open(args.pgn, "w", encoding="utf-8") if args.pgn else None
    inicio_torneio = time.perf_counter()
    feitas = 0

    def registrar(resultado: tuple) -> None:
        nonlocal feitas
        _, pgn, stats_partida, resumo = resultado
        feitas += 1
        for nome, s in stats_partida.items():
            stats[nome].somar(s)
        if args.ao_vivo is None:
            print(f"[{feitas}/{len(tarefas)}] {resumo}", flush=True)
        if arquivo_pgn:
            print(pgn, file=arquivo_pgn, end="\n\n", flush=True)

    try:
        if processos == 1:
            iniciar_processo(config)
            for tarefa in tarefas:
                registrar(rodar_tarefa(tarefa))
        else:
            with multiprocessing.Pool(processos, initializer=iniciar_processo,
                                      initargs=(config,)) as pool:
                # imap_unordered entrega cada partida assim que ela termina
                for resultado in pool.imap_unordered(rodar_tarefa, tarefas):
                    registrar(resultado)
                pool.close()
                pool.join()
    finally:
        if arquivo_pgn:
            arquivo_pgn.close()

    minutos = (time.perf_counter() - inicio_torneio) / 60
    print(f"\nDuração total: {minutos:.1f} min")
    imprimir_relatorio(nomes, stats, com_juiz=caminho_sf is not None)


if __name__ == "__main__":
    main()

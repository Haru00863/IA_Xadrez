# IA em Xadrez

Projeto Interdisciplinar III do curso de Análise e Desenvolvimento de Sistemas (UNIFASIPE, 2026).
Jogo de xadrez contra uma inteligência artificial, com as regras validadas pela biblioteca
python-chess, interface gráfica em Tkinter e histórico de partidas em SQLite.

## Situação atual

- Interface gráfica funcional: partidas contra o computador ou entre duas pessoas, histórico,
  revisão lance a lance e retomada de partidas interrompidas.
- Regras completas (roque, en passant, promoção, xeque-mate, afogamento, empates).
- Motor Minimax com poda Alfa-Beta, busca de quiescência e aprofundamento iterativo (respeita
  o limite de 10 s por lance), em três níveis (fácil, médio e difícil), avaliando material e
  posição das peças. Um motor aleatório fica disponível como linha de base para comparação.

## Requisitos

- Python 3.10 ou superior
- Tkinter
- Pacotes do `requirements.txt`

O Tkinter já vem com o Python no Windows. No Linux pode ser um pacote separado:

| Distribuição | Comando |
| --- | --- |
| Arch / CachyOS | `sudo pacman -S tk` |
| Debian / Ubuntu | `sudo apt install python3-tk` |
| Fedora | `sudo dnf install python3-tkinter` |

## Instalação

Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Se o PowerShell bloquear o `Activate.ps1`, rode antes
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` (vale só para a janela aberta).

## Como executar

A partir da pasta raiz do projeto, com o ambiente virtual ativo:

| | Comando |
| --- | --- |
| Interface gráfica | `python main.py` |
| Testes | `python -m unittest discover -s tests -v` |
| Torneio entre os motores | `python scripts/torneio.py` |

Os testes da interface precisam de uma tela; sem ela, são pulados.

## Como jogar

- Clique na peça e depois no destino, ou arraste a peça. Os pontos marcam casas livres e os
  anéis marcam capturas.
- Pelo teclado: clique no tabuleiro, mova o cursor com as setas e use Enter para selecionar e
  jogar.
- Também é possível digitar o lance no campo ao lado do tabuleiro (`e4`, `Nf3`, `O-O` ou `e2e4`).
- Repetição tripla e regra dos 50 lances não encerram a partida sozinhas: pela regra da FIDE o
  empate precisa ser reivindicado pelo botão "Reivindicar empate".

| Atalho | Ação |
| --- | --- |
| Ctrl+N | Nova partida |
| Ctrl+H | Histórico de partidas |
| Ctrl+I | Inverter tabuleiro |
| Ctrl+L | Campo de lance |
| Ctrl+Q | Sair |
| F1 | Lista de atalhos |

Cada lance é salvo no banco assim que é feito. Se o programa for fechado no meio de uma
partida, ele oferece continuar de onde parou na próxima vez que abrir.

## Torneio entre os motores

`scripts/torneio.py` faz os motores jogarem todos contra todos. Cada partida começa de uma
abertura curta, jogada duas vezes com as cores trocadas: por padrão os primeiros lances são
sorteados (com semente fixa, para o resultado ser reproduzível); com `--livro`, vêm de 50
aberturas reais (`scripts/livro_aberturas.py`). O relatório sai em tabelas Markdown, com a
configuração usada (inclusive o commit do código), vitórias, empates, derrotas e tempo médio por
lance.

Com o [Stockfish](https://stockfishchess.org/) instalado (no Arch/CachyOS:
`sudo pacman -S stockfish`), ele entra no torneio de duas formas:

- como adversário, com força reduzida (`--sf-niveis 0 5`: Skill Level de 0 a 20);
- como juiz: analisa cada lance dos motores e mede a **concordância** (% de lances iguais ao
  melhor lance do Stockfish) e o **ACPL** (perda média em centipeões por lance; quanto menor,
  melhor).

| Opção | Para quê |
| --- | --- |
| `--aberturas N` | aberturas por confronto (padrão 2 sorteadas; cada uma vira 2 partidas) |
| `--livro` | usa as 50 aberturas reais do livro (com `--aberturas N`, só as N primeiras) |
| `--semente N` | muda o sorteio das aberturas (padrão 2026) |
| `--motores CHAVE ...` | escolhe os motores (ex.: `minimax_facil minimax_dificil`) |
| `--pgn arquivo.pgn` | salva as partidas; dá para abrir no Lichess |
| `--processos N` | joga N partidas ao mesmo tempo (ex.: 6, um por núcleo físico) |
| `--ao-vivo [PAUSA]` | desenha o tabuleiro no terminal a cada lance (sempre 1 partida por vez) |
| `--sf-niveis` (vazio) | sem Stockfish adversário; ele continua só como juiz |
| `--sem-stockfish` | ignora o Stockfish mesmo se estiver instalado |
| `--stockfish CAMINHO` | executável fora do PATH |

## Estrutura

```
main.py              inicia a interface gráfica
src/core/            regras e validação dos lances
src/engine/          motores de IA
src/persistence/     banco de dados SQLite
src/gui/             interface gráfica
tests/               testes automatizados
scripts/             torneio entre motores e gerador das imagens das peças
docs/                documentação técnica
```

A organização dos módulos e a comunicação entre eles estão descritas em
[docs/ARQUITETURA.md](docs/ARQUITETURA.md).

## Observações

- O banco (`src/persistence/xadrez.db`) é criado automaticamente na primeira execução e não é
  versionado.
- As datas ficam gravadas em UTC e aparecem no fuso do computador.
- As imagens das peças foram geradas a partir dos glifos da fonte DejaVu Sans (licença livre).
  Para gerá-las de novo: `pip install pillow` e `python scripts/gerar_sprites_pecas.py`.

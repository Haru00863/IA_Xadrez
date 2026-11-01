# IA em Xadrez

Projeto Interdisciplinar III do curso de Análise e Desenvolvimento de Sistemas (UNIFASIPE, 2026).
Jogo de xadrez contra uma inteligência artificial, com as regras validadas pela biblioteca
python-chess, interface gráfica em Tkinter e histórico de partidas em SQLite.

## Situação atual

- Interface gráfica funcional: partidas contra o computador ou entre duas pessoas, histórico,
  revisão lance a lance e retomada de partidas interrompidas.
- Regras completas (roque, en passant, promoção, xeque-mate, afogamento, empates).
- O motor de IA atual é provisório e escolhe lances aleatórios. O Minimax com poda Alfa-Beta
  está em desenvolvimento e vai substituí-lo sem mudanças na interface.

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

## Estrutura

```
main.py              inicia a interface gráfica
src/core/            regras e validação dos lances
src/engine/          motores de IA
src/persistence/     banco de dados SQLite
src/gui/             interface gráfica
tests/               testes automatizados
scripts/             gerador das imagens das peças
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

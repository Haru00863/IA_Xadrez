"""Livro de aberturas reais usado pelo torneio (opção --livro).

Cada abertura tem um nome e os primeiros lances em notação SAN (4 a 8 meios-lances).
O torneio joga cada uma duas vezes, trocando as cores, e os motores pensam a partir
do lance seguinte. A lista mistura aberturas de peão do rei, peão da dama e de flanco,
para não favorecer um tipo de posição.
"""

LIVRO = [
    # 1.e4 e5
    ("Partida Italiana", "e4 e5 Nf3 Nc6 Bc4 Bc5"),
    ("Dois Cavalos", "e4 e5 Nf3 Nc6 Bc4 Nf6"),
    ("Ruy López, Defesa Morphy", "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6"),
    ("Ruy López, Defesa Berlinense", "e4 e5 Nf3 Nc6 Bb5 Nf6"),
    ("Partida Escocesa", "e4 e5 Nf3 Nc6 d4 exd4 Nxd4"),
    ("Quatro Cavalos", "e4 e5 Nf3 Nc6 Nc3 Nf6"),
    ("Defesa Petrov", "e4 e5 Nf3 Nf6 Nxe5 d6 Nf3 Nxe4"),
    ("Defesa Philidor", "e4 e5 Nf3 d6 d4 Nf6"),
    ("Gambito do Rei Aceito", "e4 e5 f4 exf4 Nf3"),
    ("Partida Vienense", "e4 e5 Nc3 Nf6 f4"),
    ("Gambito Escocês", "e4 e5 Nf3 Nc6 d4 exd4 Bc4"),
    ("Abertura Ponziani", "e4 e5 Nf3 Nc6 c3 Nf6"),
    # 1.e4, outras defesas
    ("Siciliana, Najdorf", "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6"),
    ("Siciliana, Dragão", "e4 c5 Nf3 d6 d4 cxd4 Nxd4 g6"),
    ("Siciliana, Variante Clássica", "e4 c5 Nf3 Nc6 d4 cxd4 Nxd4 Nf6"),
    ("Siciliana, Taimanov", "e4 c5 Nf3 e6 d4 cxd4 Nxd4 Nc6"),
    ("Siciliana, Alapin", "e4 c5 c3 Nf6 e5 Nd5"),
    ("Siciliana Fechada", "e4 c5 Nc3 Nc6 g3 g6"),
    ("Defesa Francesa, Variante do Avanço", "e4 e6 d4 d5 e5 c5"),
    ("Defesa Francesa, Winawer", "e4 e6 d4 d5 Nc3 Bb4"),
    ("Defesa Francesa, Tarrasch", "e4 e6 d4 d5 Nd2 Nf6"),
    ("Caro-Kann, Variante Clássica", "e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5"),
    ("Caro-Kann, Variante do Avanço", "e4 c6 d4 d5 e5 Bf5"),
    ("Defesa Escandinava", "e4 d5 exd5 Qxd5 Nc3 Qa5"),
    ("Defesa Pirc", "e4 d6 d4 Nf6 Nc3 g6"),
    ("Defesa Moderna", "e4 g6 d4 Bg7 Nc3 d6"),
    ("Defesa Alekhine", "e4 Nf6 e5 Nd5 d4 d6"),
    # 1.d4
    ("Gambito da Dama Recusado", "d4 d5 c4 e6 Nc3 Nf6"),
    ("Gambito da Dama Aceito", "d4 d5 c4 dxc4 Nf3 Nf6"),
    ("Defesa Eslava", "d4 d5 c4 c6 Nf3 Nf6"),
    ("Defesa Semi-Eslava", "d4 d5 c4 c6 Nf3 Nf6 Nc3 e6"),
    ("Defesa Tarrasch", "d4 d5 c4 e6 Nc3 c5"),
    ("Sistema Londres", "d4 d5 Bf4 Nf6 e3 e6"),
    ("Índia do Rei", "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6"),
    ("Defesa Grünfeld", "d4 Nf6 c4 g6 Nc3 d5"),
    ("Nimzo-Índia", "d4 Nf6 c4 e6 Nc3 Bb4"),
    ("Índia da Dama", "d4 Nf6 c4 e6 Nf3 b6"),
    ("Defesa Catalã", "d4 Nf6 c4 e6 g3 d5"),
    ("Bogo-Índia", "d4 Nf6 c4 e6 Nf3 Bb4+"),
    ("Benoni Moderna", "d4 Nf6 c4 c5 d5 e6"),
    ("Gambito Benko", "d4 Nf6 c4 c5 d5 b5"),
    ("Defesa Holandesa", "d4 f5 c4 Nf6 g3 e6"),
    ("Índia Antiga", "d4 Nf6 c4 d6 Nc3 e5"),
    ("Ataque Torre", "d4 Nf6 Nf3 e6 Bg5 c5"),
    # flanco
    ("Abertura Inglesa, Simétrica", "c4 c5 Nc3 Nc6 g3 g6"),
    ("Abertura Inglesa, Siciliana Invertida", "c4 e5 Nc3 Nf6 Nf3 Nc6"),
    ("Abertura Réti", "Nf3 d5 c4 e6 g3 Nf6"),
    ("Índia do Rei Invertida", "Nf3 d5 g3 Nf6 Bg2 c6 O-O Bg4"),
    ("Abertura Larsen", "b3 e5 Bb2 Nc6 e3 Nf6"),
    ("Abertura Bird", "f4 d5 Nf3 Nf6 e3 g6"),
]

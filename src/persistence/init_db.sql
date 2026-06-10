CREATE TABLE IF NOT EXISTS PARTIDA (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_inicio TEXT,
    resultado TEXT,
    dificuldade_ia TEXT
);

CREATE TABLE IF NOT EXISTS JOGADA (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    partida_id INTEGER,
    notation_pgn TEXT,
    timestamp TEXT,
    avaliacao_ia TEXT,
    FOREIGN KEY (partida_id) REFERENCES PARTIDA(id)
);

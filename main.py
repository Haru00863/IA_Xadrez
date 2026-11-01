"""Inicia a interface gráfica do IA em Xadrez."""

import os
import sys

# permite rodar o main.py a partir de outra pasta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.gui.app import executar  # noqa: E402

if __name__ == "__main__":
    executar()

"""
Gera as imagens PNG das peças usadas pela interface.

As peças são desenhadas a partir dos glifos de xadrez da fonte DejaVu Sans (licença livre).
Com imagens prontas, a aparência fica igual no Windows e no Linux, sem depender das fontes
instaladas.

Uso (precisa do Pillow só para gerar as imagens):
    python3 scripts/gerar_sprites_pecas.py
    python3 scripts/gerar_sprites_pecas.py --fonte caminho/DejaVuSans.ttf

"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

# tamanhos gerados (px); a interface usa o maior que cabe na casa
TAMANHOS = [24, 32, 40, 48, 56, 64, 72, 80, 88, 96, 104, 112, 120, 128]

# desenha 4x maior e reduz, para suavizar as bordas
SUPERSAMPLE = 4

TIPOS = "KQRBNP"

# o peão da DejaVu é quase do tamanho do bispo, então é reduzido
ESCALA = {"P": 0.84}

# cores das peças
TINTA = (38, 35, 47, 255)
CORPO_BRANCO = (251, 250, 247, 255)
HALO_PRETO = (236, 232, 224, 255)

CAMINHOS_FONTE = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    os.path.expandvars(r"%WINDIR%\Fonts\DejaVuSans.ttf"),
]


def localizar_fonte(caminho_cli: str | None) -> str:
    """Caminho da DejaVu Sans (o argumento --fonte tem prioridade)."""
    candidatos = [caminho_cli] if caminho_cli else CAMINHOS_FONTE
    for caminho in candidatos:
        if caminho and Path(caminho).is_file():
            return caminho
    sys.exit("DejaVuSans.ttf não encontrada. Informe o caminho com --fonte.")


def mascara_glifo(fonte: ImageFont.FreeTypeFont, glifo: str, lado: int,
                  base_y: float) -> Image.Image:
    """Desenha o glifo centralizado, com a base em base_y."""
    mascara = Image.new("L", (lado, lado), 0)
    desenho = ImageDraw.Draw(mascara)
    x0, y0, x1, y1 = desenho.textbbox((0, 0), glifo, font=fonte)
    x = (lado - (x1 - x0)) / 2 - x0
    y = base_y - y1
    desenho.text((x, y), glifo, font=fonte, fill=255)
    return mascara


def silhueta(mascara: Image.Image) -> Image.Image:
    """Silhueta da peça sem os furos internos do glifo (flood fill a partir do canto)."""
    binaria = mascara.point(lambda v: 255 if v > 40 else 0)
    ImageDraw.floodfill(binaria, (0, 0), 128)
    forma = binaria.point(lambda v: 0 if v == 128 else 255)
    return forma.filter(ImageFilter.GaussianBlur(1))


def camada(cor: tuple[int, int, int, int], mascara: Image.Image) -> Image.Image:
    """Camada de cor sólida usando a máscara como alfa."""
    img = Image.new("RGBA", mascara.size, cor[:3] + (0,))
    alfa = ImageChops.multiply(mascara, Image.new("L", mascara.size, cor[3]))
    img.putalpha(alfa)
    return img


def renderizar_peca(fonte: ImageFont.FreeTypeFont, tipo: str, branca: bool,
                    lado: int) -> Image.Image:
    """Renderiza uma peça em alta resolução."""
    indice = TIPOS.index(tipo)
    glifo_contorno = chr(0x2654 + indice)
    glifo_cheio = chr(0x265A + indice)
    base_y = lado * 0.90

    m_cheio = mascara_glifo(fonte, glifo_cheio, lado, base_y)
    m_contorno = mascara_glifo(fonte, glifo_contorno, lado, base_y)
    m_silhueta = silhueta(m_cheio)

    resultado = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))

    sombra = m_silhueta.filter(ImageFilter.GaussianBlur(lado * 0.025))
    sombra = ImageChops.offset(sombra, 0, int(lado * 0.02))
    resultado.alpha_composite(camada((0, 0, 0, 70), sombra))

    if branca:
        resultado.alpha_composite(camada(CORPO_BRANCO, m_silhueta))
        resultado.alpha_composite(camada(TINTA, m_contorno))
    else:
        # borda clara: separa a peça preta da casa escura e forma os detalhes
        halo = m_silhueta.filter(ImageFilter.MaxFilter(5))
        resultado.alpha_composite(camada(HALO_PRETO, halo))
        resultado.alpha_composite(camada(TINTA, m_cheio))
    return resultado


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--fonte", help="caminho para DejaVuSans.ttf")
    parser.add_argument(
        "--saida",
        default=str(Path(__file__).resolve().parent.parent / "src" / "gui" / "assets" / "pecas"),
        help="diretório de saída (padrão: src/gui/assets/pecas)",
    )
    args = parser.parse_args()

    caminho_fonte = localizar_fonte(args.fonte)
    saida = Path(args.saida)

    # fonte calibrada para o rei ocupar 76% da casa
    ALTURA_REI = 0.76
    referencia = ImageFont.truetype(caminho_fonte, 1000)
    _, topo, _, base = referencia.getbbox(chr(0x265A))
    altura_por_ponto = (base - topo) / 1000

    for tamanho in TAMANHOS:
        lado = tamanho * SUPERSAMPLE
        pontos = lado * ALTURA_REI / altura_por_ponto
        pasta = saida / str(tamanho)
        pasta.mkdir(parents=True, exist_ok=True)
        for tipo in TIPOS:
            fonte = ImageFont.truetype(caminho_fonte, int(pontos * ESCALA.get(tipo, 1.0)))
            for branca in (True, False):
                grande = renderizar_peca(fonte, tipo, branca, lado)
                final = grande.resize((tamanho, tamanho), Image.LANCZOS)
                nome = f"{'w' if branca else 'b'}{tipo}.png"
                final.save(pasta / nome, optimize=True)
        print(f"tamanho {tamanho:>3} px: ok")

    print(f"Sprites gravados em: {saida}")


if __name__ == "__main__":
    main()

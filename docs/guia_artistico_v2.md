# Guia Artístico — THE IRON ARCHIVE V2 (CINEMATIC 2D)

## Identidade Visual

**Nome:** THE IRON ARCHIVE — CINEMATIC 2D  
**Modelo-base:** SDXL 1.0 (`sd_xl_base_1.0.safetensors`)  
**Versão do guia:** 1.0 (aprovado)  
**Referência visual principal:** `00_Reference/IronArchive_V2_Test_00001_.png`

## Características Obrigatórias

- Ilustração 2D cinematográfica de fantasia medieval
- Cenários monumentais e arquiteturas detalhadas (salões, torres, arcos góticos, pilares)
- Paleta cromática base: vermelho profundo, vinho, preto, marfim, dourado envelhecido
- Variações de paleta permitidas conforme região e narrativa de Westeros, mantendo o mesmo tratamento artístico
- Traços gráficos marcantes, sombras contrastantes, silhuetas nítidas
- Personagens estilizados, mas reconhecíveis (não fotorrealista, não anime, não 3D)
- Composições dramáticas com camadas de profundidade (planos geométricos sobrepostos)
- Consistência visual entre cenas e episódios

## Parâmetros de Referência (Geração Aprovada)

| Parâmetro | Valor |
|-----------|-------|
| Checkpoint | `sd_xl_base_1.0.safetensors` |
| Resolução | 768 × 1344 (9:16) |
| Batch | 1 |
| Steps | 30 |
| CFG | 6 |
| Sampler | dpmpp_2m (DPM++ 2M) |
| Scheduler | karras |
| Seed | 54321 |
| Modo ComfyUI | `--lowvram --cpu-vae` |
| ComfyUI versão | 0.45.0 |
| PyTorch | 2.11.0+cu128 |
| CUDA | 12.8 |
| GPU | NVIDIA GeForce RTX 5060 (8 GB VRAM) |

## Prompts de Referência

**Positivo (aprovado):**
> Jaime Lannister standing inside the Red Keep throne room in King's Landing, moments before confronting the Mad King Aerys II, a single recognizable handsome young adult knight with shoulder-length golden blond hair, clean-shaven angular face, proud expression, wearing simplified polished golden Lannister armor and a deep crimson cape, full body, standing in the foreground. Visual art direction inspired by Reigns: Game of Thrones, minimalist medieval fantasy narrative card game illustration, sophisticated 2D geometric vector-style artwork, distinctive angular character silhouettes, simplified polygonal facial features, carefully constructed flat shapes, bold graphic design, solid color blocks, limited harmonious palette of burgundy, antique gold, charcoal black and muted ivory, clean hard-edged shadows, sharp silhouettes, no outlines or very subtle outlines. A magnificent stylized medieval throne hall in the background, the Iron Throne clearly visible behind Jaime, towering gothic stone arches, monumental pillars, large stained glass windows, red royal banners, dramatic symmetrical architecture, layered environmental depth using flat geometric planes, elegant cinematic composition, atmospheric light represented by simple geometric shapes, richly designed environment but visually consistent with minimalist flat illustration. Vertical cinematic composition, 9:16 framing, highly polished 2D game artwork, strong focal point, coherent visual storytelling, no photorealism.

**Negativo (aprovado):**
> photorealistic, 3D, CGI, anime, manga, watercolor, oil painting, engraving, etching, crosshatching, detailed textures, gradients, airbrush, hyperrealism, overly detailed armor, generic fantasy illustration, multiple characters, duplicate faces, floating heads, collage, text, watermark, deformed hands, extra limbs

## Organização de Assets (dentro de `output/`)

```
output/
├── 00_Reference/
│   └── IronArchive_V2_Test_00001_.png   # referência principal aprovada (mestre, cópia)
├── assets/
│   ├── episodes/
│   │   ├── E01_<nome-do-episodio>/
│   │   │   ├── cena01/
│   │   │   └── ...
│   │   └── E02_<nome-do-episodio>/
│   ├── characters/
│   │   ├── Jaime_Lannister/
│   │   └── ...
│   └── scenarios/
│       ├── Red_Keep_Throne_Room/
│       └── ...
```

**Nomenclatura sugerida:** `E##_Cena##_<Personagem>_V##.png` (ex: `E01_C01_Jaime_Lannister_V01.png`)

## Padrão de Metadados (sidecar `.json`)

Cada imagem gerada deve ser acompanhada de um arquivo JSON sidecar com mesmo nome-base, contendo:

| Campo | Descrição |
|-------|-----------|
| `imagem` | Nome do arquivo PNG |
| `prompt_positivo` | Texto completo utilizado |
| `prompt_negativo` | Texto completo utilizado |
| `checkpoint` | Nome do arquivo .safetensors |
| `resolucao` | Largura × Altura |
| `batch` | Tamanho do lote |
| `steps` | Quantidade de passos |
| `cfg` | Valor de CFG |
| `sampler` | Nome do sampler |
| `scheduler` | Nome do scheduler |
| `seed` | Semente utilizada |
| `tempo_geracao_seg` | Tempo total de geração |
| `vram_pico_mib` | Pico de VRAM observado (se disponível) |
| `guia_artistico_versao` | Versão deste guia aplicada |
| `referencia_visual` | Caminho da imagem mestre usada |

## Regras de Uso

1. Sempre partir da referência em `00_Reference/` como base de cor e estilo.
2. Não usar fotorrealismo, 3D, CGI, anime, manga, aquarela, óleo, crosshatching, gradientes ou texturas excessivas.
3. Manter a paleta restrita conforme região/narrativa, com tratamento artístico consistente.
4. Um personagem reconhecível por cena, composição vertical 9:16, foco forte.
5. Não gerar imagens sem aprovação prévia do Artist.
6. Não alterar este guia sem novo ciclo de aprovação.

## Restrições Operacionais (V2)

- Trabalhar exclusivamente em `D:\TheIronArchive_V2`.
- Não acessar nem modificar `D:\TheIronArchive`.
- Não modificar SQLite, Git, jobs ou approvals.
- Manter o Artist pausado até nova autorização.

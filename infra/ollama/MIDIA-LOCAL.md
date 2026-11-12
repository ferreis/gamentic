# Imagens e narração locais em máquinas com pouca VRAM

O complemento `docker-compose.local-media.yml` usa SD-Turbo e Kokoro na CPU.
A GPU fica disponível para o modelo de texto no Ollama. A configuração AMD
original continua em `docker-compose.yml`.

## Instalação

Execute na raiz do projeto:

```sh
mkdir -p models/comfyui/checkpoints
curl -fL --retry 3 -o models/comfyui/checkpoints/sd_turbo.safetensors.part \
  https://huggingface.co/stabilityai/sd-turbo/resolve/main/sd_turbo.safetensors
mv models/comfyui/checkpoints/sd_turbo.safetensors.part \
  models/comfyui/checkpoints/sd_turbo.safetensors
```

No `.env`, selecione os arquivos e habilite a mídia:

```dotenv
COMPOSE_PROFILES=harness
COMPOSE_FILE=docker-compose.yml:docker-compose.ollama.yml:docker-compose.local-media.yml
IMAGE_ENABLED=true
VOICE_ENABLED=true
AUDIO_PROVIDER=openai
AUDIO_BASE_URL=http://gamentic-kokoro:8880
AUDIO_MODEL=kokoro
```

`openai` é o formato da API. A síntese ocorre no container local Kokoro,
sem chave e sem envio à OpenAI. O complemento define o modelo, as dimensões
das imagens e a rota de áudio do frontend.

```sh
docker compose build image image-api
docker compose up -d image image-api kokoro orchestrator frontend ollama-proxy
```

O serviço Maya original usa o perfil `maya` neste complemento e fica desativado.
O SD-Turbo usa resolução próxima de 512 pixels e um passo.
Os prompts internos de imagem são preparados em inglês. No complemento local,
`IMAGE_PROMPT_WORDS=36` separa estilo, aparência, roupa e iluminação para que o
estilo não ocupe todo o contexto curto do encoder. O enquadramento de cada vista
também é compacto (`IMAGE_COMPACT_PROMPTS=true`). Textos, legendas e narração
continuam em português. A aparência sem detalhes físicos exige inferência visual
do diretor de arte; o modelo leve não garante identidade entre vistas.
Ele não recebe as referências de identidade do workflow FLUX original;
a aparência entre imagens pode variar. Imagens na CPU levam mais tempo.

## Checkpoint e LoRAs pela interface

Abra uma aventura e acesse **Configurações → Arte da aventura**.
Selecione o checkpoint, ative as LoRAs desejadas, ajuste a intensidade de cada
uma e clique em **Salvar configuração de arte**. A alteração vale para as próximas
imagens de todas as aventuras deste servidor. Para atualizar imagens antigas,
use **Regenerar todas as imagens** depois de salvar.

Os controles mostram os modelos conhecidos que estiverem instalados:

| Checkpoint | Família | Geração |
| --- | --- | --- |
| `sd_turbo.safetensors` | SD 2.1 | 1 passo |
| `LCM_AAM_AnyLoRA_AnimeMix.safetensors` | SD 1.5 | Anime leve, LCM, 4 passos |
| `animagine-xl-4.0-opt.safetensors` | SDXL | Anime, Euler a, CFG 5, 28 passos |

Animagine usa a configuração de amostragem recomendada pelo autor, sem a LoRA
de aceleração Lightning, que produziu distorções no teste local. As LoRAs de estilo são:

- [Pixel Art XL](https://huggingface.co/nerijs/pixel-art-xl): `pixel-art-xl.safetensors`.
- [Papercut SDXL](https://huggingface.co/TheLastBen/Papercut_SDXL): `papercut.safetensors`.

As duas são SDXL. A interface oculta opções incompatíveis e o servidor também
valida a combinação. A intensidade inicial é 0,7; zero desativa o efeito.
O catálogo fica em `infra/image-api/app/art_settings.py`; novos modelos precisam
de uma entrada com família e workflow compatíveis.

A seleção persiste em `infra/image-api/settings/art.json`, montado no container.
**Padrão do servidor** volta ao workflow e às LoRAs definidos pelo ambiente.
Nesse modo, `COMFY_CHECKPOINT_NAME` troca o checkpoint do workflow e
`COMFY_LORAS='[{"name":"estilo.safetensors","strength":0.7}]'` combina LoRAs.
As configurações pelo ambiente exigem recriar `image-api`.

Na CPU, Animagine é mais pesado; o complemento local permite até 600 segundos
por imagem e 1800 segundos na chamada do orquestrador que gera três vistas de
personagem. Ao salvar uma alteração, o cache de modelos do ComfyUI é liberado
assim que a fila permitir, para reduzir o consumo de memória ao trocar LoRAs.
No perfil SDXL, imagens pequenas são ampliadas para o lado menor de 512 pixels,
preservando a proporção com arredondamento a múltiplos de 16 e teto de 1024 pixels.
Os workflows de checkpoint não usam referências
de identidade; personagens podem variar entre imagens.

## Aventura criada com mídia desativada

Habilitar os serviços não gera retroativamente as imagens. Para recuperar uma
aventura, use as funções existentes `integrate.assign_voices_for_game`,
`integrate.reresolve_voices`, `integrate.generate_scene_image` e
`integrate.generate_images_for_game`, informando o ID correto e preservando
o banco. Elas reaproveitam imagens existentes e preenchem as ausentes.

Na interface, abra a engrenagem e ative **Áudio → Voz**. Para ouvir a história
automaticamente, ative também **Voz do narrador**. O botão de reprodução
ao lado de cada trecho permite ouvir manualmente.

## Fontes

- https://github.com/remsky/Kokoro-FastAPI
- https://huggingface.co/stabilityai/sd-turbo
- https://comfyanonymous.github.io/ComfyUI_examples/sdturbo/
- https://huggingface.co/cagliostrolab/animagine-xl-4.0

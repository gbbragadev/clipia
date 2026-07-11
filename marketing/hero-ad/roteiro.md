# 🎬 Conceito: "Este vídeo foi feito por IA" — TOFU (prospecção)

**Data:** 2026-07-04 · **Diretor:** Claude Fable 5 (Estúdio de Marketing ClipIA)
**Lição-mãe (handoff Traço Urbano 6/10):** narração CONTÍNUA em take único; cortes no beat;
SFX/música reais; overlays com easing; grading por cena.

## 🎯 Estratégia

- **Hipótese:** hook meta auto-referencial ("este vídeo foi feito por IA") para o scroll porque a prova É o próprio criativo.
- **Plataforma-alvo:** Reels/TikTok/Shorts 9:16 (orgânico primeiro; asset serve a Meta Ads depois).
- **Ângulo:** prova (com dor embutida no segundo ato).
- **Audiência:** creators e pequenos negócios pt-BR que precisam de volume de vídeo curto sem gravar nem editar.
- **KPI primário:** 3s view-rate ≥ 25%.
- **Kill criterion:** < 15% de 3s view-rate ou CTR < 0,8% após ~2k impressões → arquivar e testar hook 2.

## 🪝 Hooks (3 alternativas, ≤3s)

1. **[Prova]** "Este vídeo que você está assistindo foi escrito, narrado e legendado por uma IA." — visual: partículas roxo/azul formando uma tela 9:16. **← ESCOLHIDA**
2. **[Dor]** "Três horas editando pra um vídeo de trinta segundos. De novo." — visual: timeline caótica de editor, macro.
3. **[Curiosidade]** "O assunto que tá bombando agora já virou vídeo — e não foi você que fez." — visual: feed rolando rápido.

## 📝 Narração contínua (take único, ~100 palavras, alvo ≤40s falados)

> Este vídeo que você está assistindo… foi escrito, narrado e legendado por inteligência artificial.
>
> Nenhuma câmera. Nenhum microfone. Nenhuma madrugada perdida em timeline.
>
> Funciona assim: você escolhe um tema — o ClipIA vê o que está bombando agora, escreve o roteiro, narra em português natural… e legenda palavra por palavra, no ritmo exato da voz.
>
> Quer ajustar? O editor mostra na tela exatamente o que sai no arquivo final. O que você vê… é o que você publica.
>
> Enquanto você lê esta legenda, tem gente publicando o terceiro vídeo do dia.
>
> Crie o seu. Clipia ponto com ponto bê érre.

**Pronúncia TTS:** "ClipIA" → grafar "Clip-I-A" se sair errado no take; URL falada "Clipia ponto com ponto bê érre".

## 🎬 Beats visuais (9:16, ~42s + vinheta)

| Beat | Janela | Fala | Visual | Fonte |
|---|---|---|---|---|
| b1 hook | 0–5 | "Este vídeo… inteligência artificial." | Partículas roxo→azul formando tela de celular, dark premium | Seedance 9:16 |
| b2 negação | 5–11 | "Nenhuma câmera… timeline." | Câmera/microfone/mesa de edição dissolvendo em partículas | Seedance 9:16 |
| b3 demo | 11–24 | "Funciona assim… ritmo exato da voz." | Produto REAL: painel Em alta → tema → roteiro → narração → legendas word-level | Captura Playwright |
| b4 editor | 24–31 | "Quer ajustar?… o que você publica." | Editor real (preview 9:16, abas), zoom com easing | Captura Playwright |
| b5 ritmo | 31–37 | "Enquanto você lê… terceiro vídeo do dia." | Grid de feeds/celulares rolando, energia urbana BR | Seedance 9:16 |
| b6 CTA | 37–42 | "Crie o seu. Clipia ponto com ponto bê érre." | Arte de marca: gradiente #7c3aed→#3b82f6, logo, URL | FFmpeg/asset |
| vinheta | +1.5s | (whisper) | Outro sting oficial do produto (`append_outro`) | app/assets/outro |

## 🎨 Direção de arte

- Fundo `#050509`, gradiente `#7c3aed→#3b82f6`, Inter. Clips Seedance com paleta enforced no prompt (deep purple/electric blue on near-black, no warm tones).
- Legendas word-level queimadas (estilo: Inter bold, branco, contorno escuro, palavra ativa em gradiente) — o diferencial do produto DENTRO do ad.
- Cortes sincronizados ao beat da trilha (~124 BPM → beat 0,484s; cortes em múltiplos de 4 beats).
- Overlays com fade+slide easing (não enable seco).

## 🔊 Áudio

- VO: ElevenLabs `eleven_multilingual_v2`, casting A/B Carla `7eUAxNOneHxqfyRS77mW` vs Daiane `nHNZWlqUWtEKPr3hhFQP`; stability 0.65, similarity 0.80, style 0.10, speaker_boost, speed 0.95; `<break time>` entre blocos.
- Música: ElevenLabs music — eletrônica dark premium 124 BPM, drop em ~11s (virada pra demo), rise final no CTA.
- SFX: ElevenLabs SFX — whoosh (transições), UI clicks (demo), riser (pré-CTA). Mix 3-bus com ducking da música sob a VO (sidechain simulado por volume automation).

## 📊 Variante A/B

- **Variável:** só a voz (Carla vs Daiane) no mesmo take. Depois: só a hook (1 vs 2).
- **Custo estimado:** 3 clips Seedance ≈ $1,80 (+$0,60 já gasto no probe) + ElevenLabs (grátis) → ~$2,40 do teto de $5.

## ✅ Gates

- [x] G1 Hook: 3 opções com psicologia nomeada
- [x] G2 Promessa comprovável: roteiro/narração/legendas por IA = literalmente como este ad é feito; features citadas (Em alta, word-level, editor fiel) existem no produto
- [x] G3 Retenção: virada aos 11s (demo), segunda virada aos 31s (urgência social), payoff contínuo
- [x] G4 CTA único: "Crie o seu" + URL
- [x] G5 Nativo 9:16, legendas burned p/ feed mudo
- [x] G6 Marca: gradiente/nome ClipIA/vinheta oficial
- [x] G7 Unit economics: ~$2,40 de $5; kill criterion declarado

## 🚦 Verdict: GO

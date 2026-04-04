import { Composition } from 'remotion'
import { ShortVideoComposition } from './compositions/ShortVideoComposition'
import { DEFAULT_SUBTITLE_STYLE, DEFAULT_VOICE_CONFIG } from './types'
import type { CompositionData } from './types'

const calculateMetadata = ({ props }: { props: Record<string, unknown> }) => {
  const p = props as unknown as CompositionData
  const lastWord = p.words[p.words.length - 1]
  const durationSeconds = lastWord ? lastWord.end + 0.5 : 30
  return {
    durationInFrames: Math.round(durationSeconds * p.fps),
    fps: p.fps,
    width: p.width,
    height: p.height,
  }
}

const defaultProps: CompositionData = {
  title: '5 curiosidades sobre o oceano',
  scenes: [
    { text: 'Voce sabia que conhecemos menos de 5% dos oceanos?', keywords_en: ['deep ocean'], duration_hint: 6 },
    { text: 'Mais pessoas ja foram ao espaco do que ao fundo do mar.', keywords_en: ['astronaut'], duration_hint: 5 },
    { text: 'Existe uma cachoeira subaquatica quatro vezes maior que Niagara.', keywords_en: ['underwater'], duration_hint: 6 },
    { text: 'O oceano produz 70% do oxigenio que respiramos.', keywords_en: ['ocean waves'], duration_hint: 5 },
    { text: 'Incrivel como sabemos tao pouco sobre nosso planeta.', keywords_en: ['earth space'], duration_hint: 8 },
  ],
  words: [
    { word: 'Voce', start: 0.0, end: 0.3 },
    { word: 'sabia', start: 0.3, end: 0.78 },
    { word: 'que', start: 0.78, end: 1.14 },
    { word: 'conhecemos', start: 1.14, end: 1.66 },
    { word: 'menos', start: 1.66, end: 2.12 },
    { word: 'de', start: 2.12, end: 2.36 },
    { word: '5%', start: 2.36, end: 3.08 },
    { word: 'dos', start: 3.08, end: 3.44 },
    { word: 'oceanos?', start: 3.44, end: 4.52 },
  ],
  audioUrl: '',
  mediaUrls: [],
  subtitleStyle: DEFAULT_SUBTITLE_STYLE,
  voiceConfig: DEFAULT_VOICE_CONFIG,
  fps: 30,
  width: 1080,
  height: 1920,
  overlays: [],
  musicUrl: null,
  musicVolume: 0.15,
}

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="ShortVideo"
      component={ShortVideoComposition as unknown as React.FC<Record<string, unknown>>}
      calculateMetadata={calculateMetadata}
      defaultProps={defaultProps}
    />
  )
}

export interface Word {
  word: string
  start: number
  end: number
}

export type TransitionType = 'none' | 'fade' | 'slide' | 'wipe'

export interface Scene {
  text: string
  keywords_en: string[]
  duration_hint: number
  transition?: TransitionType
  /** Templates de IA (ai_video/novelinha) trazem visual_hint em vez de keywords_en. */
  visual_hint?: string
}

export type CaptionStylePreset = 'tiktok' | 'impact' | 'minimal' | 'karaoke' | 'boxed' | 'pop' | 'neon'

export interface SubtitleStyle {
  fontFamily: string
  fontSize: number
  color: string
  outlineColor: string
  backgroundColor: string
  position: 'bottom' | 'center'
  marginBottom: number
  maxWordsPerChunk: number
  preset: CaptionStylePreset
  accentColor: string
  strokeWidth: number
  animationStyle: 'pop' | 'fade' | 'slideUp' | 'none'
}

export interface VideoOverlay {
  type: 'questionBox' | 'followCTA' | 'endScreen' | 'progressBar'
  startFrame: number
  endFrame: number
  config: Record<string, unknown>
}

export interface VoiceConfig {
  voiceId: string
  voiceProvider: 'edge' | 'elevenlabs' | 'custom'
  rate: number
  pitch: number
}

export const DEFAULT_VOICE_CONFIG: VoiceConfig = {
  voiceId: 'pt-BR-AntonioNeural',
  voiceProvider: 'edge',
  rate: -10,
  pitch: 5,
}

export type LayoutType = 'fullscreen' | 'split_horizontal' | 'character_overlay'

export interface CompositionData {
  scenes: Scene[]
  /** Current position -> original server-owned media index. */
  sceneOrder: number[]
  narrationStale: boolean
  words: Word[]
  audioUrl: string
  mediaUrls: string[]
  subtitleStyle: SubtitleStyle
  voiceConfig: VoiceConfig
  fps: number
  width: number
  height: number
  title: string
  overlays: VideoOverlay[]
  musicAssetId: import('./music-assets').MusicAssetId | null
  musicVolume: number
  isRendering?: boolean
  templateId?: string
  layoutType?: LayoutType
  pendingCredits?: number
  watermark?: string
}

export const DEFAULT_SUBTITLE_STYLE: SubtitleStyle = {
  fontFamily: 'Montserrat, sans-serif',
  fontSize: 52,
  color: '#FFFFFF',
  outlineColor: '#000000',
  backgroundColor: 'rgba(0, 0, 0, 0.6)',
  position: 'bottom',
  marginBottom: 180,
  maxWordsPerChunk: 3,
  preset: 'minimal',
  accentColor: '#FFFC00',
  strokeWidth: 0,
  animationStyle: 'pop',
}

'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

interface AudioRecorderProps {
  onRecordingComplete: (blob: Blob) => void
  maxDuration?: number // seconds
  disabled?: boolean
}

type RecordingState = 'idle' | 'recording' | 'paused' | 'done'

export default function AudioRecorder({ onRecordingComplete, maxDuration = 180, disabled }: AudioRecorderProps) {
  const [state, setState] = useState<RecordingState>('idle')
  const [elapsed, setElapsed] = useState(0)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const animRef = useRef<number>(0)
  const streamRef = useRef<MediaStream | null>(null)

  const cleanup = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current)
    if (animRef.current) cancelAnimationFrame(animRef.current)
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }
  }, [])

  useEffect(() => () => cleanup(), [cleanup])

  const drawWaveform = useCallback(() => {
    const canvas = canvasRef.current
    const analyser = analyserRef.current
    if (!canvas || !analyser) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const bufferLength = analyser.frequencyBinCount
    const dataArray = new Uint8Array(bufferLength)

    const draw = () => {
      animRef.current = requestAnimationFrame(draw)
      analyser.getByteTimeDomainData(dataArray)

      ctx.fillStyle = 'rgba(0, 0, 0, 0.1)'
      ctx.fillRect(0, 0, canvas.width, canvas.height)

      ctx.lineWidth = 2
      ctx.strokeStyle = '#ff5638'
      ctx.beginPath()

      const sliceWidth = canvas.width / bufferLength
      let x = 0
      for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0
        const y = (v * canvas.height) / 2
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
        x += sliceWidth
      }

      ctx.lineTo(canvas.width, canvas.height / 2)
      ctx.stroke()
    }

    draw()
  }, [])

  const startRecording = async () => {
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      // Setup analyser for waveform
      const audioCtx = new AudioContext()
      const source = audioCtx.createMediaStreamSource(stream)
      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = 2048
      source.connect(analyser)
      analyserRef.current = analyser

      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      mediaRecorderRef.current = recorder
      chunksRef.current = []

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        const url = URL.createObjectURL(blob)
        setAudioUrl(url)
        setState('done')
        onRecordingComplete(blob)
        cleanup()
      }

      recorder.start(100)
      setState('recording')
      setElapsed(0)

      timerRef.current = setInterval(() => {
        setElapsed(prev => {
          if (prev + 1 >= maxDuration) {
            recorder.stop()
            return maxDuration
          }
          return prev + 1
        })
      }, 1000)

      drawWaveform()
    } catch {
      setError('Não foi possível acessar o microfone. Verifique as permissões.')
    }
  }

  const pauseRecording = () => {
    const recorder = mediaRecorderRef.current
    if (recorder && recorder.state === 'recording') {
      recorder.pause()
      setState('paused')
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }

  const resumeRecording = () => {
    const recorder = mediaRecorderRef.current
    if (recorder && recorder.state === 'paused') {
      recorder.resume()
      setState('recording')
      timerRef.current = setInterval(() => {
        setElapsed(prev => {
          if (prev + 1 >= maxDuration) {
            recorder.stop()
            return maxDuration
          }
          return prev + 1
        })
      }, 1000)
    }
  }

  const stopRecording = () => {
    const recorder = mediaRecorderRef.current
    if (recorder && (recorder.state === 'recording' || recorder.state === 'paused')) {
      recorder.stop()
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }

  const reset = () => {
    cleanup()
    if (audioUrl) URL.revokeObjectURL(audioUrl)
    setAudioUrl(null)
    setState('idle')
    setElapsed(0)
    setError(null)
    chunksRef.current = []
  }

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 12,
      padding: 16, borderRadius: 12,
      background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.7)' }}>
          Gravador de áudio
        </span>
        <span style={{ fontSize: 11, fontFamily: 'monospace', color: state === 'recording' ? '#f87171' : 'rgba(255,255,255,0.3)' }}>
          {state === 'recording' && '● '}{formatTime(elapsed)} / {formatTime(maxDuration)}
        </span>
      </div>

      {/* Waveform */}
      {(state === 'recording' || state === 'paused') && (
        <canvas
          ref={canvasRef}
          width={280}
          height={48}
          style={{ width: '100%', height: 48, borderRadius: 6, background: 'rgba(0,0,0,0.3)' }}
        />
      )}

      {/* Preview */}
      {state === 'done' && audioUrl && (
        <audio
          src={audioUrl}
          controls
          style={{ width: '100%', height: 36, borderRadius: 8 }}
        />
      )}

      {/* Error */}
      {error && (
        <div style={{ fontSize: 10, color: '#f87171', padding: '4px 0' }}>{error}</div>
      )}

      {/* Controls */}
      <div style={{ display: 'flex', gap: 6 }}>
        {state === 'idle' && (
          <button
            type="button"
            onClick={startRecording}
            disabled={disabled}
            style={{
              flex: 1, padding: '8px 0', border: 'none', borderRadius: 8,
              background: 'linear-gradient(135deg, #ef4444, #dc2626)',
              color: 'white', fontSize: 11, fontWeight: 600, cursor: disabled ? 'not-allowed' : 'pointer',
              opacity: disabled ? 0.5 : 1,
            }}
          >
            Gravar
          </button>
        )}

        {state === 'recording' && (
          <>
            <button
              type="button"
              onClick={pauseRecording}
              style={{
                flex: 1, padding: '8px 0', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8,
                background: 'rgba(255,255,255,0.05)', color: 'white', fontSize: 11, fontWeight: 600, cursor: 'pointer',
              }}
            >
              Pausar
            </button>
            <button
              type="button"
              onClick={stopRecording}
              style={{
                flex: 1, padding: '8px 0', border: 'none', borderRadius: 8,
                background: '#ef4444', color: 'white', fontSize: 11, fontWeight: 600, cursor: 'pointer',
              }}
            >
              Parar
            </button>
          </>
        )}

        {state === 'paused' && (
          <>
            <button
              type="button"
              onClick={resumeRecording}
              style={{
                flex: 1, padding: '8px 0', border: 'none', borderRadius: 8,
                background: 'linear-gradient(135deg, #ef4444, #dc2626)',
                color: 'white', fontSize: 11, fontWeight: 600, cursor: 'pointer',
              }}
            >
              Continuar
            </button>
            <button
              type="button"
              onClick={stopRecording}
              style={{
                flex: 1, padding: '8px 0', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8,
                background: 'rgba(255,255,255,0.05)', color: 'white', fontSize: 11, fontWeight: 600, cursor: 'pointer',
              }}
            >
              Parar
            </button>
          </>
        )}

        {state === 'done' && (
          <button
            type="button"
            onClick={reset}
            style={{
              flex: 1, padding: '8px 0', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8,
              background: 'rgba(255,255,255,0.05)', color: 'white', fontSize: 11, fontWeight: 600, cursor: 'pointer',
            }}
          >
            Gravar novamente
          </button>
        )}
      </div>
    </div>
  )
}

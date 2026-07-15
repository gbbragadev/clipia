'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

type WaveformState = 'loading' | 'ready' | 'unavailable'

const waveformCache = new Map<string, number[]>()

function reduceToRmsPeaks(buffer: AudioBuffer, maxBars = 180): number[] {
  const barCount = Math.max(1, Math.min(maxBars, buffer.length))
  const samplesPerBar = Math.max(1, Math.floor(buffer.length / barCount))
  const peaks: number[] = []

  for (let bar = 0; bar < barCount; bar += 1) {
    const start = bar * samplesPerBar
    const end = Math.min(buffer.length, start + samplesPerBar)
    let squareSum = 0
    let sampleCount = 0
    for (let channel = 0; channel < buffer.numberOfChannels; channel += 1) {
      const data = buffer.getChannelData(channel)
      for (let sample = start; sample < end; sample += 1) {
        squareSum += data[sample] * data[sample]
        sampleCount += 1
      }
    }
    peaks.push(sampleCount ? Math.sqrt(squareSum / sampleCount) : 0)
  }

  const maxPeak = Math.max(...peaks, 0.01)
  return peaks.map((peak) => peak / maxPeak)
}

export function NarrationWaveform({
  audioUrl,
  label = 'Narração',
}: {
  audioUrl?: string
  label?: string
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [peaks, setPeaks] = useState<number[]>(
    () => audioUrl ? (waveformCache.get(audioUrl) ?? []) : [],
  )
  const [state, setState] = useState<WaveformState>(
    audioUrl && waveformCache.has(audioUrl) ? 'ready' : 'loading',
  )

  useEffect(() => {
    if (!audioUrl) {
      setState('unavailable')
      return
    }
    const sourceUrl = audioUrl
    const cached = waveformCache.get(audioUrl)
    if (cached) {
      setPeaks(cached)
      setState('ready')
      return
    }

    const controller = new AbortController()
    let active = true
    let context: AudioContext | null = null

    async function decode() {
      try {
        const response = await fetch(sourceUrl, { signal: controller.signal })
        if (!response.ok) throw new Error('waveform fetch failed')
        const encoded = await response.arrayBuffer()
        context = new AudioContext()
        const buffer = await context.decodeAudioData(encoded)
        const nextPeaks = reduceToRmsPeaks(buffer)
        waveformCache.set(sourceUrl, nextPeaks)
        if (active) {
          setPeaks(nextPeaks)
          setState('ready')
        }
      } catch (error) {
        if (active && !(error instanceof DOMException && error.name === 'AbortError')) {
          setState('unavailable')
        }
      } finally {
        if (context && context.state !== 'closed') void context.close()
      }
    }

    void decode()
    return () => {
      active = false
      controller.abort()
      if (context && context.state !== 'closed') void context.close()
    }
  }, [audioUrl])

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const dpr = window.devicePixelRatio || 1
    canvas.width = Math.max(1, Math.round(rect.width * dpr))
    canvas.height = Math.max(1, Math.round(rect.height * dpr))
    const context = canvas.getContext('2d')
    if (!context) return
    context.setTransform(dpr, 0, 0, dpr, 0, 0)
    context.clearRect(0, 0, rect.width, rect.height)
    context.fillStyle = 'rgba(62, 155, 255, 0.08)'
    context.fillRect(0, 0, rect.width, rect.height)

    const values = state === 'ready' && peaks.length ? peaks : Array.from({ length: 48 }, () => 0.08)
    const gap = 1
    const barWidth = Math.max(1, (rect.width - gap * (values.length - 1)) / values.length)
    context.fillStyle = state === 'ready'
      ? 'rgba(62, 155, 255, 0.72)'
      : 'rgba(255, 255, 255, 0.14)'
    values.forEach((peak, index) => {
      const height = Math.max(2, peak * (rect.height - 4))
      const x = index * (barWidth + gap)
      context.fillRect(x, (rect.height - height) / 2, barWidth, height)
    })
  }, [peaks, state])

  useEffect(() => {
    draw()
    const canvas = canvasRef.current
    if (!canvas) return
    const observer = new ResizeObserver(draw)
    observer.observe(canvas)
    return () => observer.disconnect()
  }, [draw])

  return (
    <canvas
      ref={canvasRef}
      role="img"
      aria-label={`Waveform da ${label.toLocaleLowerCase('pt-BR')}`}
      className="editor-timeline__waveform"
      data-waveform-state={state}
    />
  )
}

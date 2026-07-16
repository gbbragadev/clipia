'use client'

import { ImageIcon } from 'lucide-react'
import { useEffect, useState } from 'react'

type ThumbnailSize = 'grid' | 'timeline'

const IMAGE_RE = /\.(png|jpe?g|webp|gif|svg)(\?|$)/i
const thumbnailCache = new Map<string, string>()

export function SceneThumbnail({
  mediaUrl,
  sceneNumber,
  size = 'grid',
}: {
  mediaUrl?: string
  sceneNumber: number
  size?: ThumbnailSize
}) {
  const cacheKey = `${size}:${mediaUrl ?? ''}`
  const [thumbnail, setThumbnail] = useState<string | null>(
    () => thumbnailCache.get(cacheKey) ?? null,
  )
  const [unavailable, setUnavailable] = useState(false)
  const isImage = Boolean(mediaUrl && IMAGE_RE.test(mediaUrl))

  useEffect(() => {
    if (!mediaUrl || isImage) return
    const cached = thumbnailCache.get(cacheKey)
    if (cached) {
      setThumbnail(cached)
      return
    }

    let active = true
    const video = document.createElement('video')
    video.crossOrigin = 'anonymous'
    video.muted = true
    video.playsInline = true
    video.preload = 'metadata'

    const fail = () => {
      if (active) setUnavailable(true)
    }
    const capture = () => {
      try {
        const canvas = document.createElement('canvas')
        canvas.width = size === 'grid' ? 120 : 160
        canvas.height = size === 'grid' ? 213 : 90
        const context = canvas.getContext('2d')
        if (!context) return fail()
        context.drawImage(video, 0, 0, canvas.width, canvas.height)
        const dataUrl = canvas.toDataURL('image/jpeg', 0.65)
        thumbnailCache.set(cacheKey, dataUrl)
        if (active) setThumbnail(dataUrl)
      } catch {
        fail()
      }
    }
    const seek = () => {
      const target = Number.isFinite(video.duration)
        ? Math.min(0.5, Math.max(0, video.duration / 2))
        : 0.5
      if (target === 0) capture()
      else video.currentTime = target
    }

    video.addEventListener('loadedmetadata', seek, { once: true })
    video.addEventListener('seeked', capture, { once: true })
    video.addEventListener('error', fail, { once: true })
    video.src = mediaUrl
    video.load()

    return () => {
      active = false
      video.pause()
      video.removeAttribute('src')
      video.load()
    }
  }, [cacheKey, isImage, mediaUrl, size])

  const state = isImage || thumbnail ? 'ready' : unavailable ? 'unavailable' : 'loading'
  return (
    <div
      role="img"
      aria-label={`Filmstrip da cena ${sceneNumber}`}
      className={`scene-thumbnail scene-thumbnail--${size}`}
      data-thumbnail-state={state}
    >
      {isImage && mediaUrl ? (
        <img src={mediaUrl} alt="" draggable={false} />
      ) : thumbnail ? (
        <img src={thumbnail} alt="" draggable={false} />
      ) : (
        <ImageIcon aria-hidden="true" />
      )}
    </div>
  )
}

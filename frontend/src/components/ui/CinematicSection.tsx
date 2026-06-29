'use client'
import React, { useEffect, useRef, useState } from 'react'

interface CinematicSectionProps {
  children: React.ReactNode
  background?: 'grain' | 'gradient' | 'mesh' | 'none'
  reveal?: 'fade-up' | 'slide-left' | 'blur-in' | 'none'
  spacing?: 'md' | 'lg' | 'xl'
  className?: string
}

export function CinematicSection({
  children,
  background = 'none',
  reveal = 'fade-up',
  spacing = 'lg',
  className = '',
}: CinematicSectionProps) {
  const sectionRef = useRef<HTMLDivElement>(null)
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    if (reveal === 'none') {
      setIsVisible(true)
      return
    }
    // reduced-motion: mostra imediatamente, sem esperar o IntersectionObserver.
    if (typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setIsVisible(true)
      return
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true)
          observer.unobserve(entry.target)
        }
      },
      { threshold: 0.1, rootMargin: '0px 0px -50px 0px' }
    )
    if (sectionRef.current) {
      observer.observe(sectionRef.current)
    }
    return () => observer.disconnect()
  }, [reveal])

  const spacingClasses = {
    md: 'py-10 sm:py-12 md:py-24',
    lg: 'py-14 sm:py-20 md:py-32',
    xl: 'py-16 sm:py-24 md:py-48',
  }

  const backgroundClasses = {
    none: '',
    grain: 'relative before:absolute before:inset-0 before:z-[-1] before:bg-[url(/noise.svg)] before:opacity-10',
    gradient: 'relative before:absolute before:inset-0 before:z-[-1] before:bg-gradient-to-b before:from-transparent before:to-purple-900/10',
    mesh: 'relative before:absolute before:inset-0 before:z-[-1] before:bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] before:from-purple-900/20 before:via-[#0f0b1a] before:to-[#0f0b1a]',
  }

  const revealClasses = {
    none: 'opacity-100',
    'fade-up': `transition-all duration-1000 ease-out ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-12'}`,
    'slide-left': `transition-all duration-1000 ease-out ${isVisible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-12'}`,
    'blur-in': `transition-all duration-1000 ease-out ${isVisible ? 'opacity-100 blur-none' : 'opacity-0 blur-md'}`,
  }

  return (
    <section
      ref={sectionRef}
      className={`w-full overflow-hidden ${spacingClasses[spacing]} ${backgroundClasses[background]} ${className}`}
    >
      <div className={`w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 ${revealClasses[reveal]}`}>
        {children}
      </div>
    </section>
  )
}

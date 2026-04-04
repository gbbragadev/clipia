'use client'

interface CreditsBadgeProps {
  credits: number
}

export default function CreditsBadge({ credits }: CreditsBadgeProps) {
  const isEmpty = credits <= 0

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${
        isEmpty
          ? 'bg-red-500/15 text-red-400'
          : 'bg-purple-500/15 text-purple-300'
      }`}
    >
      <span className={`font-semibold ${isEmpty ? 'text-red-300' : 'text-purple-200'}`}>
        {credits}
      </span>
      créditos
    </span>
  )
}

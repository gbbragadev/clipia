export function SkeletonBlock({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-[var(--bg-surface-hover)] ${className}`} />
}

export function AuthLoadingSkeleton() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="card w-full max-w-md p-8 space-y-5">
        <div className="flex justify-center">
          <SkeletonBlock className="h-12 w-36 rounded-full" />
        </div>
        <div className="space-y-3">
          <SkeletonBlock className="h-6 w-2/3 mx-auto" />
          <SkeletonBlock className="h-4 w-4/5 mx-auto" />
        </div>
        <div className="space-y-4">
          <SkeletonBlock className="h-11 w-full" />
          <SkeletonBlock className="h-11 w-full" />
          <SkeletonBlock className="h-11 w-full" />
        </div>
      </div>
    </div>
  )
}

export function DashboardLoadingSkeleton() {
  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">
      <div className="card p-5 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="space-y-3">
          <SkeletonBlock className="h-5 w-52" />
          <SkeletonBlock className="h-4 w-72" />
        </div>
        <SkeletonBlock className="h-11 w-36 rounded-xl" />
      </div>

      <div className="card p-6 space-y-5">
        <SkeletonBlock className="h-6 w-40" />
        <div className="grid gap-4 md:grid-cols-3">
          <SkeletonBlock className="h-56" />
          <SkeletonBlock className="h-56" />
          <SkeletonBlock className="h-56" />
        </div>
      </div>

      <div className="space-y-4">
        <SkeletonBlock className="h-5 w-36" />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <SkeletonBlock className="h-52" />
          <SkeletonBlock className="h-52" />
          <SkeletonBlock className="h-52" />
        </div>
      </div>
    </div>
  )
}

export function CreditsLoadingSkeleton() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-8">
      <div className="text-center space-y-3">
        <SkeletonBlock className="h-7 w-44 mx-auto" />
        <SkeletonBlock className="h-10 w-56 mx-auto rounded-full" />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <SkeletonBlock className="h-64" />
        <SkeletonBlock className="h-64" />
        <SkeletonBlock className="h-64" />
      </div>
      <div className="space-y-4">
        <SkeletonBlock className="h-5 w-48" />
        <SkeletonBlock className="h-36 w-full" />
      </div>
    </div>
  )
}

export function EditorLoadingSkeleton() {
  return (
    <div className="min-h-screen px-4 py-6">
      <div className="mx-auto max-w-7xl space-y-4">
        <div className="card p-4 flex items-center justify-between">
          <SkeletonBlock className="h-6 w-40" />
          <SkeletonBlock className="h-10 w-32 rounded-xl" />
        </div>
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_380px]">
          <SkeletonBlock className="h-[32rem] w-full" />
          <div className="space-y-4">
            <SkeletonBlock className="h-12 w-full" />
            <SkeletonBlock className="h-32 w-full" />
            <SkeletonBlock className="h-40 w-full" />
            <SkeletonBlock className="h-24 w-full" />
          </div>
        </div>
        <SkeletonBlock className="h-40 w-full" />
      </div>
    </div>
  )
}

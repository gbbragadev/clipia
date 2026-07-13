export const SELECTED_PACKAGES = ['starter', 'popular', 'professional'] as const

export type SelectedPackage = (typeof SELECTED_PACKAGES)[number]

export function parseSelectedPackage(value: string | null | undefined): SelectedPackage | null {
  return SELECTED_PACKAGES.includes(value as SelectedPackage) ? (value as SelectedPackage) : null
}

export function apiIdToSelectedPackage(packageId: string): SelectedPackage | null {
  if (packageId === 'pro') return 'professional'
  return parseSelectedPackage(packageId)
}

export function selectedPackageLabel(selectedPackage: SelectedPackage): string {
  if (selectedPackage === 'starter') return 'Starter'
  if (selectedPackage === 'popular') return 'Popular'
  return 'Profissional'
}

export function withCacheBuster(url: string, timestamp = Date.now()): string {
  const hashIndex = url.indexOf('#')
  const resource = hashIndex === -1 ? url : url.slice(0, hashIndex)
  const hash = hashIndex === -1 ? '' : url.slice(hashIndex)
  const separator = resource.includes('?') ? '&' : '?'

  return `${resource}${separator}t=${timestamp}${hash}`
}

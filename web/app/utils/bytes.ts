/** Sizes the way download pages show them: decimal units, one decimal for GB. 7_400_000_000 -> "7.4 GB" */
export function formatBytes(bytes: number): string {
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`
  if (bytes >= 1e6) return `${Math.round(bytes / 1e6)} MB`
  if (bytes >= 1e3) return `${Math.round(bytes / 1e3)} KB`
  return `${Math.max(0, Math.round(bytes))} B`
}

/** "2.1 GB of 7.4 GB" */
export function formatProgress(completed: number, total: number): string {
  return total > 0 ? `${formatBytes(completed)} of ${formatBytes(total)}` : formatBytes(completed)
}

/** 35_200_000 -> "35 MB/s". Null while the speed is not known yet. */
export function formatSpeed(bytesPerSecond: number | null): string {
  if (bytesPerSecond === null) return ''
  if (bytesPerSecond <= 0) return 'waiting for data…'
  return `${formatBytes(bytesPerSecond)}/s`
}

/** 40 -> "less than a minute left", 130 -> "about 2 min left", 5400 -> "about 1 h 30 min left" */
export function formatEta(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) return ''
  if (seconds < 60) return 'less than a minute left'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `about ${minutes} min left`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest ? `about ${hours} h ${rest} min left` : `about ${hours} h left`
}

export function percent(completed: number, total: number): number {
  return total > 0 ? Math.min(100, Math.floor((completed / total) * 100)) : 0
}

/** Memory sizes of a computer: 17_179_869_184 -> "16 GB" (binary, as the Mac reports it). */
export function formatMemory(bytes: number): string {
  return `${Math.round(bytes / 2 ** 30)} GB`
}

/**
 * Instant client-side file checks (format and size) using the same limits as the server.
 * The server validates every file again; this only gives the recruiter immediate feedback.
 */
export function checkFile(file, { allowedExtensions, maxFileSizeMb }) {
  const extension = `.${file.name.split('.').pop()?.toLowerCase()}`
  if (!file.name.includes('.') || !allowedExtensions.includes(extension)) {
    return extension === '.doc'
      ? 'Old Word (.doc) files are not supported. Save as .docx or PDF.'
      : `Unsupported format. Only ${allowedExtensions.join(', ')} files are accepted.`
  }
  if (file.size === 0) return 'The file is empty.'
  if (file.size > maxFileSizeMb * 1024 * 1024) return `Larger than ${maxFileSizeMb} MB.`
  return null
}

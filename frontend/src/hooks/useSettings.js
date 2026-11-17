import { systemApi } from '../services/api'
import { useApi } from './useApi'

/** Upload limits and scoring weights from the backend, with safe defaults while loading. */
export const DEFAULT_LIMITS = { allowedExtensions: ['.pdf', '.docx'], maxFileSizeMb: 5, maxFilesPerBatch: 50 }

export function useSettings() {
  const { data, loading, error } = useApi(() => systemApi.settings(), [])
  const limits = data
    ? {
        allowedExtensions: data.allowed_extensions,
        maxFileSizeMb: data.max_file_size_mb,
        maxFilesPerBatch: data.max_files_per_batch,
      }
    : DEFAULT_LIMITS
  return { settings: data, limits, loading, error }
}

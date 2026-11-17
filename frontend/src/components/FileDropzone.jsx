/**
 * Drag-and-drop / browse file picker with instant client-side checks
 * (format and size, using the same limits as the server). The server validates again.
 */
import { FileText, UploadCloud, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { checkFile } from '../utils/files'
import { formatFileSize } from '../utils/format'

export default function FileDropzone({ files, onChange, limits, multiple = true, disabled = false, label }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  const addFiles = (fileList) => {
    const incoming = Array.from(fileList)
    const key = (f) => `${f.name}-${f.size}-${f.lastModified}`
    const existing = new Set(files.map((entry) => key(entry.file)))
    const additions = incoming
      .filter((file) => !existing.has(key(file)))
      .map((file) => ({ id: crypto.randomUUID(), file, error: checkFile(file, limits) }))
    onChange(multiple ? [...files, ...additions] : additions.slice(0, 1))
  }

  return (
    <div>
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(event) => !disabled && (event.key === 'Enter' || event.key === ' ') && inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault()
          if (!disabled) setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          if (!disabled) addFiles(event.dataTransfer.files)
        }}
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition focus-visible:outline-2 focus-visible:outline-brand-500 ${
          dragging ? 'border-brand-500 bg-brand-50' : 'border-slate-300 bg-slate-50 hover:border-brand-500 hover:bg-brand-50/50'
        } ${disabled ? 'pointer-events-none opacity-60' : ''}`}
      >
        <div className="flex size-12 items-center justify-center rounded-full bg-white text-brand-600 shadow-sm">
          <UploadCloud className="size-6" aria-hidden="true" />
        </div>
        <p className="text-sm font-medium text-slate-900">
          {label || 'Drag and drop resumes here, or'} <span className="text-brand-700 underline">browse files</span>
        </p>
        <p className="text-xs text-slate-500">
          {limits.allowedExtensions.join(', ').toUpperCase().replaceAll('.', '')} · up to {limits.maxFileSizeMb} MB each
          {multiple && ` · up to ${limits.maxFilesPerBatch} files`}
        </p>
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          multiple={multiple}
          accept={limits.allowedExtensions.join(',')}
          onChange={(event) => {
            addFiles(event.target.files)
            event.target.value = ''
          }}
        />
      </div>

      {files.length > 0 && (
        <ul className="mt-4 divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
          {files.map(({ id, file, error }) => (
            <li key={id} className="flex items-center gap-3 px-4 py-2.5">
              <FileText className={`size-5 shrink-0 ${error ? 'text-red-500' : 'text-slate-400'}`} aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-slate-900">{file.name}</p>
                <p className={`text-xs ${error ? 'text-red-600' : 'text-slate-500'}`}>
                  {formatFileSize(file.size)}
                  {error && ` · ${error}`}
                </p>
              </div>
              {!disabled && (
                <button
                  type="button"
                  onClick={() => onChange(files.filter((entry) => entry.id !== id))}
                  className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                  aria-label={`Remove ${file.name}`}
                >
                  <X className="size-4" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

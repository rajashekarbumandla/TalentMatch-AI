/**
 * Form for reviewing and editing job requirements (used after JD analysis and on "Edit job").
 * The backend normalises everything again on save (e.g. "postgres" -> PostgreSQL).
 */
import { Field, inputClass } from './ui'
import { LinesInput, SkillInput } from './Skills'

export default function RequirementsEditor({ form, onChange, errors = {}, showDescription = false }) {
  const set = (key) => (value) => onChange({ ...form, [key]: value })
  return (
    <div className="grid gap-5 md:grid-cols-2">
      <Field label="Job title" required error={errors.job_title}>
        {(id) => <input id={id} className={inputClass} value={form.job_title} onChange={(e) => set('job_title')(e.target.value)} />}
      </Field>
      <Field
        label="Minimum experience (years)"
        hint="Leave empty if the job has no experience requirement."
        error={errors.minimum_experience}
      >
        {(id) => (
          <input
            id={id}
            type="number"
            min="0"
            max="50"
            step="0.5"
            className={inputClass}
            value={form.minimum_experience}
            onChange={(e) => set('minimum_experience')(e.target.value)}
            placeholder="No requirement"
          />
        )}
      </Field>
      <div className="md:col-span-2">
        <Field label="Required skills" hint='Count double in the skills score. Use "or" for alternatives, e.g. "FastAPI or Django".'>
          {(id) => <SkillInput id={id} value={form.required_skills} onChange={set('required_skills')} tone="required" />}
        </Field>
      </div>
      <div className="md:col-span-2">
        <Field label="Preferred skills" hint="Nice to have: they add to the score but count half as much.">
          {(id) => <SkillInput id={id} value={form.preferred_skills} onChange={set('preferred_skills')} tone="preferred" />}
        </Field>
      </div>
      <div className="md:col-span-2">
        <Field label="Education requirements">
          {(id) => (
            <input
              id={id}
              className={inputClass}
              value={form.education_requirements}
              onChange={(e) => set('education_requirements')(e.target.value)}
              placeholder="e.g. Bachelor's degree in Computer Science or equivalent"
            />
          )}
        </Field>
      </div>
      <div className="md:col-span-2">
        <Field label="Responsibilities" hint="One per line.">
          {(id) => <LinesInput id={id} value={form.responsibilities} onChange={set('responsibilities')} />}
        </Field>
      </div>
      {showDescription && (
        <div className="md:col-span-2">
          <Field label="Full job description" required error={errors.description} hint="Used for semantic (meaning-based) matching.">
            {(id) => (
              <textarea id={id} rows={8} className={inputClass} value={form.description} onChange={(e) => set('description')(e.target.value)} />
            )}
          </Field>
        </div>
      )}
    </div>
  )
}

/** Helpers for the job-requirements form (conversion to/from the API and validation). */

export function emptyRequirements() {
  return {
    job_title: '',
    description: '',
    required_skills: [],
    preferred_skills: [],
    minimum_experience: '',
    education_requirements: '',
    responsibilities: [],
    keywords: [],
  }
}

/** Convert form state to the API payload (empty experience = no requirement). */
export function toJobPayload(form) {
  return {
    job_title: form.job_title.trim(),
    description: form.description.trim(),
    required_skills: form.required_skills,
    preferred_skills: form.preferred_skills,
    minimum_experience: form.minimum_experience === '' ? null : Number(form.minimum_experience),
    education_requirements: form.education_requirements.trim() || null,
    responsibilities: form.responsibilities.map((r) => r.trim()).filter(Boolean),
    keywords: form.keywords,
  }
}

export function fromJob(job) {
  return {
    job_title: job.job_title || '',
    description: job.description || '',
    required_skills: job.required_skills || [],
    preferred_skills: job.preferred_skills || [],
    minimum_experience: job.minimum_experience ?? '',
    education_requirements: job.education_requirements || '',
    responsibilities: job.responsibilities || [],
    keywords: job.keywords || [],
  }
}

/** Same rules as the backend's JobCreate schema, checked before sending. */
export function validateRequirements(form) {
  const errors = {}
  if (form.job_title.trim().length < 2) errors.job_title = 'Enter the job title.'
  if (form.description.trim().length < 30) errors.description = 'The job description must be at least 30 characters.'
  const years = form.minimum_experience
  if (years !== '' && (Number.isNaN(Number(years)) || Number(years) < 0 || Number(years) > 50)) {
    errors.minimum_experience = 'Enter a number between 0 and 50, or leave empty for no requirement.'
  }
  return errors
}

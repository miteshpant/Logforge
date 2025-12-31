'use client'

import { useState } from 'react'
import { apiClient } from '@/lib/api'

interface AnomalyFeedbackProps {
  anomalyId: string
  onSubmitSuccess?: () => void
}

type FeedbackType = 'true_positive' | 'false_positive' | 'severity_wrong' | 'duplicate'

export default function AnomalyFeedback({ anomalyId, onSubmitSuccess }: AnomalyFeedbackProps) {
  const [feedbackType, setFeedbackType] = useState<FeedbackType | null>(null)
  const [correctSeverity, setCorrectSeverity] = useState('')
  const [notes, setNotes] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  const handleSubmit = async () => {
    if (!feedbackType) return

    setIsSubmitting(true)
    try {
      // Map feedbackType to the expected format for /v1/ai/feedback endpoint
      const feedbackMapping: Record<string, 'accurate' | 'inaccurate' | 'helpful' | 'not_helpful'> = {
        'true_positive': 'accurate',
        'false_positive': 'inaccurate',
        'severity_wrong': 'helpful',
        'duplicate': 'not_helpful'
      }

      const response = await apiClient.post(`/v1/ai/feedback`, {
        analysis_id: anomalyId,
        feedback_type: feedbackMapping[feedbackType] || 'helpful',
        rating: feedbackType === 'true_positive' ? 5 : feedbackType === 'false_positive' ? 1 : 3,
        comments: notes.trim() || `Feedback on anomaly: ${feedbackType}${correctSeverity ? `. Correct severity: ${correctSeverity}` : ''}`,
        specific_issues: feedbackType === 'severity_wrong' && correctSeverity ? [`Severity should be ${correctSeverity}`] : []
      })

      if (response.success) {
        setSubmitted(true)
        onSubmitSuccess?.()

        // Reset form after 2 seconds
        setTimeout(() => {
          setFeedbackType(null)
          setCorrectSeverity('')
          setNotes('')
          setSubmitted(false)
        }, 2000)
      }
    } catch (error) {
      console.error('Failed to submit feedback:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  if (submitted) {
    return (
      <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4 text-center">
        <p className="text-green-400">✓ Thank you for your feedback! This helps improve detection accuracy.</p>
      </div>
    )
  }

  return (
    <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 space-y-4">
      <div>
        <h3 className="text-sm font-medium text-gray-300 mb-3">Was this detection accurate?</h3>

        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => setFeedbackType('true_positive')}
            className={`px-4 py-2 rounded-lg border transition-colors ${
              feedbackType === 'true_positive'
                ? 'bg-green-500/20 border-green-500/50 text-green-400'
                : 'bg-gray-700/50 border-gray-600 text-gray-400 hover:bg-gray-700'
            }`}
          >
            ✓ Accurate
          </button>

          <button
            onClick={() => setFeedbackType('false_positive')}
            className={`px-4 py-2 rounded-lg border transition-colors ${
              feedbackType === 'false_positive'
                ? 'bg-red-500/20 border-red-500/50 text-red-400'
                : 'bg-gray-700/50 border-gray-600 text-gray-400 hover:bg-gray-700'
            }`}
          >
            ✗ False Alarm
          </button>

          <button
            onClick={() => setFeedbackType('severity_wrong')}
            className={`px-4 py-2 rounded-lg border transition-colors ${
              feedbackType === 'severity_wrong'
                ? 'bg-yellow-500/20 border-yellow-500/50 text-yellow-400'
                : 'bg-gray-700/50 border-gray-600 text-gray-400 hover:bg-gray-700'
            }`}
          >
            ⚠ Wrong Severity
          </button>

          <button
            onClick={() => setFeedbackType('duplicate')}
            className={`px-4 py-2 rounded-lg border transition-colors ${
              feedbackType === 'duplicate'
                ? 'bg-blue-500/20 border-blue-500/50 text-blue-400'
                : 'bg-gray-700/50 border-gray-600 text-gray-400 hover:bg-gray-700'
            }`}
          >
            ⊕ Duplicate
          </button>
        </div>
      </div>

      {feedbackType === 'severity_wrong' && (
        <div>
          <label className="block text-sm text-gray-400 mb-2">Correct Severity:</label>
          <select
            value={correctSeverity}
            onChange={(e) => setCorrectSeverity(e.target.value)}
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-gray-200"
          >
            <option value="">Select severity...</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </div>
      )}

      <div>
        <label className="block text-sm text-gray-400 mb-2">Additional Notes (optional):</label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Why was this detection inaccurate? What should we look for instead?"
          className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-gray-200 placeholder-gray-500 text-sm"
          rows={3}
        />
      </div>

      <button
        onClick={handleSubmit}
        disabled={!feedbackType || isSubmitting}
        className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg transition-colors"
      >
        {isSubmitting ? 'Submitting...' : 'Submit Feedback'}
      </button>

      <p className="text-xs text-gray-500 text-center">
        Your feedback helps our ML models learn and improve detection accuracy over time.
      </p>
    </div>
  )
}
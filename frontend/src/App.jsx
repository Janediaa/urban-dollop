
import { useEffect, useState } from 'react'
import './App.css'
import AppLayout from './components/layout/AppLayout'

import './styles/medical-page.css'
import ReactMarkdown from 'react-markdown'
import './styles/doctors-page.css'
import './styles/appointments-page.css'

function App() {
  const [activePage, setActivePage] = useState('overview')
  const [authMode, setAuthMode] = useState('login')
  const [authUser, setAuthUser] = useState(null)
  const [showLogoutModal, setShowLogoutModal] = useState(false)
  const [authToken, setAuthToken] = useState('')
  const [authChecking, setAuthChecking] = useState(
    () => Boolean(localStorage.getItem('healthcare_auth_token'))
  )

  useEffect(() => {
    const savedToken = localStorage.getItem('healthcare_auth_token')

    if (!savedToken) return

    async function restoreSession() {
      try {
        const response = await fetch('/auth/me', {
          headers: {
            Authorization: `Bearer ${savedToken}`,
          },
        })

        if (!response.ok) {
          localStorage.removeItem('healthcare_auth_token')
          setAuthToken('')
          setAuthUser(null)
          return
        }

        const user = await response.json()
        setAuthToken(savedToken)
        setAuthUser(user)
      } catch {
        // Keep the saved token if the server is temporarily unavailable.
      } finally {
        setAuthChecking(false)
      }
    }

    restoreSession()
  }, [])
  const [authName, setAuthName] = useState('')
  const [authEmail, setAuthEmail] = useState('')
  const [authPassword, setAuthPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [authError, setAuthError] = useState('')
  const [authMessage, setAuthMessage] = useState('')
  const [authLoading, setAuthLoading] = useState(false)


  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState(null)
  const [asking, setAsking] = useState(false)
  const [medicalError, setMedicalError] = useState('')

  const [triageAnswers, setTriageAnswers] = useState({
    duration: '',
    severity: '',
    progression: '',
  })
  const [triageQuestion, setTriageQuestion] = useState('')


  const [city, setCity] = useState('')
  const [specialty, setSpecialty] = useState('')
  const [sortBy, setSortBy] = useState('name')
  const [doctors, setDoctors] = useState([])
  const [doctorCount, setDoctorCount] = useState(null)
  const [doctorError, setDoctorError] = useState('')
  const [searchingDoctors, setSearchingDoctors] = useState(false)

  const [doctorId, setDoctorId] = useState('')
  const [appointmentDate, setAppointmentDate] = useState('')
  const [appointmentTime, setAppointmentTime] = useState('10:00')
  const [slots, setSlots] = useState([])
  const [slotError, setSlotError] = useState('')
  const [selectedSlot, setSelectedSlot] = useState('')
  const [patientName, setPatientName] = useState('')
  const [patientContact, setPatientContact] = useState('')
  const [booking, setBooking] = useState(null)
  const [bookingError, setBookingError] = useState('')
  const [bookingReference, setBookingReference] = useState('')
  const [lookupResult, setLookupResult] = useState(null)


  async function submitAuth(event) {
    event.preventDefault()
    setAuthError('')
    setAuthMessage('')
    setAuthLoading(true)

    const isRegistering = authMode === 'register'

    try {
      if (isRegistering) {
        const registerResponse = await fetch('/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            full_name: authName.trim(),
            email: authEmail.trim(),
            password: authPassword,
          }),
        })



        const registerData = await registerResponse.json()

        if (!registerResponse.ok) {
          throw new Error(
            typeof registerData.detail === 'string'
              ? registerData.detail
              : 'Unable to create your account.'
          )
        }

        setAuthMessage('Account created successfully. Please sign in.')
        setAuthError('')
        setAuthMode('login')
        setAuthPassword('')
        setShowPassword(false)
        return
      }



      const response = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: authEmail.trim(),
          password: authPassword,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : 'Unable to sign in.'
        )
      }

      localStorage.setItem('healthcare_auth_token', data.access_token)
      setAuthToken(data.access_token)
      setAuthUser(data.user)
      setActivePage('overview')
      setAuthPassword('')
      setAuthMessage(
        isRegistering ? 'Account created successfully.' : 'Signed in successfully.'
      )
    } catch (error) {
      setAuthError(error.message)
    } finally {
      setAuthLoading(false)
    }
  }



  function logOut() {
    setShowLogoutModal(true)
  }

  function confirmLogout() {
    localStorage.removeItem('healthcare_auth_token')
    setAuthToken('')
    setAuthUser(null)
    setAuthPassword('')
    setAuthMessage('')
    setAuthError('')
    setBooking(null)
    setLookupResult(null)
    setBookingReference('')
    setShowLogoutModal(false)
  }


  function authHeaders() {
    return authToken
      ? { Authorization: `Bearer ${authToken}` }
      : {}
  }



  async function askMedicalQuestion(event) {
    event.preventDefault()

    const submittedQuestion = question.trim()
    if (submittedQuestion.length < 3) return

    setAsking(true)
    setAnswer(null)
    setMedicalError('')
    setTriageQuestion('')
    setTriageAnswers({
      duration: '',
      severity: '',
      progression: '',
    })

    try {
      const response = await fetch('/medical/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
        body: JSON.stringify({
          question: submittedQuestion,
          top_k: 3,
          triage_answers: {},
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : 'Unable to answer your question.'
        )
      }

      setAnswer(data)

      if (data.intent === 'triage') {
        setTriageQuestion(submittedQuestion)
      }
    } catch (error) {
      setMedicalError(error.message || 'Something went wrong.')
    } finally {
      setAsking(false)
    }
  }


  async function submitTriageAnswers(event) {
    event.preventDefault()

    if (!triageQuestion || !answer || answer.intent !== 'triage') {
      setMedicalError('Please submit your symptoms first.')
      return
    }

    setAsking(true)
    setMedicalError('')

    try {
      const response = await fetch('/medical/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
        body: JSON.stringify({
          question: triageQuestion,
          top_k: 3,
          triage_answers: triageAnswers,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : 'Unable to update the triage summary.'
        )
      }

      setAnswer(data)
    } catch (error) {
      setMedicalError(
        error.message || 'Unable to submit your answers.'
      )
    } finally {
      setAsking(false)
    }
  }


  async function searchDoctors(event) {
    event?.preventDefault()
    setSearchingDoctors(true)
    setDoctorError('')

    const params = new URLSearchParams()
    if (city.trim()) params.set('city', city.trim())
    if (specialty.trim()) params.set('doctor_type', specialty.trim())
    params.set('sort_by', sortBy)

    try {
      const response = await fetch(`/doctors?${params}`)
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Unable to find doctors.')
      setDoctors(data.doctors || [])
      setDoctorCount(data.count ?? 0)
    } catch (error) {
      setDoctorError(error.message)
    } finally {
      setSearchingDoctors(false)
    }
  }

  async function loadSlots(event) {
    event.preventDefault()
    setSlotError('')
    setSlots([])
    setSelectedSlot('')

    if (!doctorId.trim() || !appointmentDate) {
      setSlotError('Enter a doctor ID and appointment date.')
      return
    }

    try {
      const params = new URLSearchParams({
        doctor_id: doctorId,
        appointment_date: appointmentDate,
      })
      const response = await fetch(`/appointments/slots?${params}`)
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Unable to load slots.')
      setSlots(data.slots || [])
      if (!data.slots?.length) {
        setSlotError('No available slots for this doctor on this date. Create a development slot below first.')
      }
    } catch (error) {
      setSlotError(error.message)
    }
  }

  async function createSlot(event) {
    event.preventDefault()
    setSlotError('')

    try {
      const response = await fetch('/appointments/slots', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          doctor_id: Number(doctorId),
          appointment_date: appointmentDate,
          appointment_time: appointmentTime,
        }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Unable to create slot.')
      await loadSlotsForCurrentDate()
      setSelectedSlot(String(data.slot_id ?? data.id ?? ''))
      setSlotError('Slot created. Select it below if it appears in the available list.')
    } catch (error) {
      setSlotError(error.message)
    }
  }

  async function loadSlotsForCurrentDate() {
    const params = new URLSearchParams({
      doctor_id: doctorId,
      appointment_date: appointmentDate,
    })
    const response = await fetch(`/appointments/slots?${params}`)
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || 'Unable to reload slots.')
    setSlots(data.slots || [])
  }


  async function bookAppointment(event) {
    event.preventDefault()
    setBooking(null)
    setBookingError('')

    if (!authToken || !authUser) {
      setBookingError('Please sign in before booking an appointment.')
      setAuthMode('login')
      setActivePage('auth')
      return
    }

    if (!selectedSlot || !patientName.trim() || !patientContact.trim()) {
      setBookingError('Please complete all appointment details.')
      return
    }

    try {
      const response = await fetch('/appointments/proposals', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
        body: JSON.stringify({
          slot_id: Number(selectedSlot),
          patient_name: patientName.trim(),
          patient_contact: patientContact.trim(),
        }),
      })

      const proposal = await response.json()

      if (!response.ok) {
        throw new Error(
          typeof proposal.detail === 'string'
            ? proposal.detail
            : 'Unable to create booking proposal.'
        )
      }

      setBooking({
        ...proposal,
        status: 'proposal_created',
        message: 'Review the proposal and explicitly confirm to complete your booking.',
      })
    } catch (error) {
      setBookingError(error.message)
    }
  }


  async function confirmBookingProposal() {
    if (!authToken || !authUser) {
      setBookingError('Please sign in before confirming a booking.')
      setAuthMode('login')
      setActivePage('auth')
      return
    }

    const proposalId = booking?.proposal_id

    if (!proposalId) {
      setBookingError('No valid booking proposal is available to confirm.')
      return
    }

    setBookingError('')

    try {
      const response = await fetch('/appointments/proposals/confirm', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
        body: JSON.stringify({ proposal_id: proposalId }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : 'Unable to confirm the booking.'
        )
      }

      setBooking({
        ...data,
        status: 'confirmed',
        message: 'Your appointment has been confirmed.',
      })

      const reference = data.booking_reference || data.reference

      if (reference) {
        setBookingReference(reference)
      }

      await loadSlotsForCurrentDate()
    } catch (error) {
      setBookingError(error.message)
    }
  }


  async function lookUpAppointment(event) {
    event.preventDefault()
    setLookupResult(null)
    setBookingError('')

    if (!authToken || !authUser) {
      setBookingError('Please sign in to look up your appointments.')
      setAuthMode('login')
      setActivePage('auth')
      return
    }

    if (!bookingReference.trim()) {
      setBookingError('Enter a booking reference.')
      return
    }

    try {
      const response = await fetch(
        `/appointments/${encodeURIComponent(bookingReference.trim())}`,
        {
          headers: { ...authHeaders() },
        }
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : 'Appointment not found.'
        )
      }

      setLookupResult(data)
    } catch (error) {
      setBookingError(error.message)
    }
  }



  async function cancelExistingAppointment() {
    if (!authToken || !authUser) {
      setBookingError('Please sign in to cancel an appointment.')
      setAuthMode('login')
      setActivePage('auth')
      return
    }

    if (!bookingReference.trim()) return

    const confirmed = window.confirm(
      'Are you sure you want to cancel this appointment?'
    )

    if (!confirmed) return

    setBookingError('')

    try {
      const response = await fetch(
        `/appointments/${encodeURIComponent(bookingReference.trim())}/cancel`,
        {
          method: 'POST',
          headers: { ...authHeaders() },
        }
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : 'Unable to cancel appointment.'
        )
      }

      setLookupResult(data)
    } catch (error) {
      setBookingError(error.message)
    }
  }


  function renderAuthPage() {
    return (
      <div className="two-column">
        <section className="panel triage-summary">
          <span className="eyebrow">PATIENT ACCOUNT</span>
          <h2>{authMode === 'register' ? 'Create your account' : 'Welcome back'}</h2>
          <p>
            {authMode === 'register'
              ? 'Register to manage your appointments securely.'
              : 'Sign in to book and manage your appointments.'}
          </p>

          <form className="stack-form" onSubmit={submitAuth}>
            {authMode === 'register' && (
              <div className="field">
                <label htmlFor="authName">Full name</label>
                <input
                  id="authName"
                  value={authName}
                  onChange={(event) => setAuthName(event.target.value)}
                  maxLength={100}
                  required
                />
              </div>
            )}

            <div className="field">
              <label htmlFor="authEmail">Email address</label>
              <input
                id="authEmail"
                type="email"
                value={authEmail}
                onChange={(event) => setAuthEmail(event.target.value)}
                maxLength={254}
                required
              />
            </div>


            <div className="field">
              <label htmlFor="authPassword">Password</label>

              <div className="password-input-wrapper">
                <input
                  id="authPassword"
                  type={showPassword ? 'text' : 'password'}
                  value={authPassword}
                  onChange={(event) => setAuthPassword(event.target.value)}
                  minLength={authMode === 'register' ? 8 : 1}
                  maxLength={128}
                  required
                />

                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowPassword((previous) => !previous)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>


            {authError && <div className="error-box">{authError}</div>}
            {authMessage && <div className="inline-message">{authMessage}</div>}

            <button type="submit" disabled={authLoading}>
              {authLoading
                ? 'Please wait...'
                : authMode === 'register'
                  ? 'Create account'
                  : 'Sign in'}
            </button>
          </form>

          <div className="form-footer">
            {authMode === 'register'
              ? 'Already have an account?'
              : 'New to Healthcare Navigator?'}
            {' '}
            <button
              type="button"
              className="secondary-button"
              onClick={() => {
                setAuthMode(authMode === 'register' ? 'login' : 'register')
                setAuthError('')
                setAuthMessage('')
              }}
            >
              {authMode === 'register' ? 'Sign in' : 'Create an account'}
            </button>
          </div>
        </section>

        <section className="panel">
          <h3>Why sign in?</h3>
          <p>Your account lets you:</p>
          <ul>
            <li>Create and confirm appointment bookings.</li>
            <li>Look up your own bookings.</li>
            <li>Cancel your confirmed appointments.</li>
          </ul>
          <p>Medical questions and doctor discovery remain available without signing in.</p>
        </section>
      </div>
    )
  }

  function renderMedicalAnswer() {
  if (!answer) return null

  // The triage workflow has its own UI.
  if (answer.intent === 'triage') return null

  // Handle ambiguous questions explicitly.
  if (answer.intent === 'needs_clarification') {
    return (
      <section className="answer-card clarification-card">
        <div className="clarification-heading">
          <span className="clarification-icon">?</span>
          <div>
            <h3>Let's clarify your question</h3>
            <p>{answer.message}</p>
          </div>
        </div>

        <div className="clarification-question">
          <strong>{answer.clarification_question}</strong>
        </div>

        {answer.requires_human_review && (
          <p className="clarification-note">
            If you're describing current symptoms, please provide more
            context so we can guide you appropriately. Seek professional
            medical care when needed.
          </p>
        )}
      </section>
    )
  }

  const sources = Array.isArray(answer.sources) ? answer.sources : []

  return (
    <section className="answer-card">
      <h3>Answer</h3>

      <p className="answer-text">
        {answer.answer || answer.message || 'No answer was returned.'}
      </p>

      {sources.length > 0 && (
        <div className="sources">
          <h4>Sources</h4>

          {sources.map((source, index) => (
            <div
              className="source-item"
              key={source.source || source.filename || index}
            >
              <span className="source-number">[{index + 1}]</span>
              <span>
                {source.title || source.source || source.filename || 'Medical reference'}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}


  function renderOverview() {
  const firstName = authUser?.full_name?.split(' ')[0] || 'there'

  const suggestedQuestions = [
    'What are the common symptoms of diabetes?',
    'How can I manage high blood pressure?',
    'What causes frequent headaches?',
  ]

  return (
    <div className="overview-page">
      <section className="overview-welcome">
        <div className="overview-welcome-copy">
          <span className="eyebrow">YOUR HEALTH, ONE PLACE</span>
          <h2>Good to see you, {firstName}.</h2>
          <p>
            Your healthcare journey, made simpler.
            Explore medical information, find doctors and manage appointments
            all in one place.
          </p>
        </div>

        <div className="welcome-decoration" aria-hidden="true">
          <div className="welcome-decoration-icon">H+</div>
          <span>Healthcare<br />Navigator</span>
        </div>
      </section>

      <section className="ai-assistant-card">
        <div className="ai-assistant-heading">
          <div className="ai-assistant-icon">✳</div>
          <div>
            <span className="eyebrow">YOUR HEALTH ASSISTANT</span>
            <h3>What would you like to know?</h3>
            <p>
              Ask a health-related question and explore information
              from our medical knowledge base.
            </p>
          </div>
        </div>

        <form
          className="quick-question"
          onSubmit={(event) => {
            setActivePage('medical')
            askMedicalQuestion(event)
          }}
        >
          <span className="question-icon" aria-hidden="true">✳</span>

          <input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Describe your health-related question..."
            minLength={3}
            maxLength={2000}
            required
            aria-label="Ask a health-related question"
          />

          <button type="submit" disabled={asking || question.trim().length < 3}>
            {asking ? 'Please wait...' : 'Ask Medical AI ↗'}
          </button>
        </form>

        <div className="suggested-questions">
          <span>TRY ASKING</span>
          <div className="suggested-question-list">
            {suggestedQuestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => setQuestion(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="overview-services">
        <div className="section-heading">
          <div>
            <span className="eyebrow">YOUR WORKSPACE</span>
            <h3>Explore your healthcare services</h3>
          </div>
          <span className="section-caption">Everything you need, in one place</span>
        </div>

        <div className="feature-grid">
          <button
            type="button"
            className="feature-card service-card medical-service"
            onClick={() => setActivePage('medical')}
          >
            <div className="service-card-top">
              <span className="feature-icon mint">✳</span>
              <span className="service-arrow">↗</span>
            </div>

            <span className="feature-title">Medical AI</span>

            <span className="feature-description">
              Explore evidence-informed medical information and get answers
              to your health-related questions.
            </span>

            <span className="feature-link">Ask a question <span>→</span></span>
          </button>

          <button
            type="button"
            className="feature-card service-card doctor-service"
            onClick={() => {
              setActivePage('doctors')
              searchDoctors()
            }}
          >
            <div className="service-card-top">
              <span className="feature-icon blue">⚕</span>
              <span className="service-arrow">↗</span>
            </div>

            <span className="feature-title">Find a doctor</span>

            <span className="feature-description">
              Discover doctors by location and specialty. Compare their
              experience and consultation fees.
            </span>

            <span className="feature-link">Explore doctors <span>→</span></span>
          </button>

          <button
            type="button"
            className="feature-card service-card appointment-service"
            onClick={() => setActivePage('appointments')}
          >
            <div className="service-card-top">
              <span className="feature-icon peach">▦</span>
              <span className="service-arrow">↗</span>
            </div>

            <span className="feature-title">Appointments</span>

            <span className="feature-description">
              Browse available appointment slots, create booking proposals
              and manage your bookings.
            </span>

            <span className="feature-link">Manage appointments <span>→</span></span>
          </button>
        </div>
      </section>

      <div className="notice overview-notice">
        <span className="notice-icon">i</span>
        <div>
          <strong>Important health information</strong>
          <p>
            Medical AI provides general health information, not a medical
            diagnosis. It does not replace consultation with a qualified
            healthcare professional. For emergencies, seek immediate medical
            attention.
          </p>
        </div>
      </div>
    </div>
  )
}

  function renderMedicalPage() {
    return (
      <div className="medical-page">
        <div className="page-intro">
          <span className="eyebrow">MEDICAL KNOWLEDGE ASSISTANT</span>
          <h2>Ask Medical AI</h2>
          <p>Ask a health-information question. Answers are generated using your medical knowledge base and may not replace professional advice.</p>
        </div>
        
        <section className="emergency-help medical-emergency" aria-labelledby="emergency-help-title">
          <div className="emergency-help-icon" aria-hidden="true">
            <span>!</span>
          </div>

          <div className="emergency-help-copy">
            <h3 id="emergency-help-title">Need emergency medical help?</h3>
            <p>
              Do not wait for an AI response if you may be experiencing a
              medical emergency. Seek immediate medical attention.
            </p>
            <span className="emergency-help-note">
              In India, call 112 for emergency assistance.
            </span>
          </div>

          <a
            className="emergency-help-button"
            href="tel:112"
            aria-label="Call India's emergency number 112"
          >
            Call 112
            <span aria-hidden="true">↗</span>
          </a>
        </section>

        <form className="panel question-form medical-composer" onSubmit={askMedicalQuestion}>
          <label htmlFor="question">What would you like to know?</label>
          <textarea
            id="question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="For example: What are common risk factors for hypertension?"
            rows={4}
            minLength={3}
            maxLength={2000}
            required
          />
          <div className="form-footer">
            <span className="muted">{question.length}/2000 characters</span>
            <button type="submit" disabled={asking || question.trim().length < 3}>
              {asking ? 'Finding an answer…' : 'Get answer ↗'}
            </button>
          </div>
        </form>
        {medicalError && <div className="error-box">{medicalError}</div>}
        {asking && <div className="loading-box">Searching the medical knowledge base and preparing an answer…</div>}

        {renderMedicalAnswer()}

        {answer?.intent === 'triage' && answer?.summary && (
          <section className="panel medical-summary-card">
            <h3>Pre-consultation summary</h3>

            {answer.requires_emergency_care ? (
              <div className="error-box" role="alert">
                <strong>Emergency guidance</strong>
                <p>{answer.message}</p>
              </div>
            ) : (
              <>
                <p>
                  <strong>Possible specialty:</strong>{' '}
                  {answer.possible_specialty || 'Not determined'}
                </p>

                <p>
                  <strong>Reported symptoms:</strong>{' '}
                  {answer.summary.reported_symptoms?.join(', ') || 'Not specified'}
                </p>

                <p>
                  <strong>Duration:</strong>{' '}
                  {answer.summary.duration || 'Not provided'}
                </p>

                <p>
                  <strong>Severity:</strong>{' '}
                  {answer.summary.severity || 'Not provided'}
                </p>

                <p>
                  <strong>Progression:</strong>{' '}
                  {answer.summary.progression || 'Not provided'}
                </p>


                {triageQuestion && (
                  <form
                    className="question-form triage-followup-form"
                    onSubmit={submitTriageAnswers}
                  >
                    <h4>Tell us a little more</h4>
                    <p className="muted">
                      These details help prepare your summary for a healthcare professional.
                    </p>

                    <label htmlFor="triage-duration">How long have you had these symptoms?</label>
                    <input
                      id="triage-duration"
                      value={triageAnswers.duration}
                      onChange={(event) =>
                        setTriageAnswers((previous) => ({
                          ...previous,
                          duration: event.target.value,
                        }))
                      }
                      placeholder="e.g. Since yesterday, about 3 days"
                      maxLength={200}
                    />

                    <label htmlFor="triage-severity">How severe are the symptoms?</label>
                    <select
                      id="triage-severity"
                      value={triageAnswers.severity}
                      onChange={(event) =>
                        setTriageAnswers((previous) => ({
                          ...previous,
                          severity: event.target.value,
                        }))
                      }
                    >
                      <option value="">Choose an option</option>
                      <option value="mild">Mild</option>
                      <option value="moderate">Moderate</option>
                      <option value="severe">Severe</option>
                    </select>

                    <label htmlFor="triage-progression">
                      How are the symptoms changing?
                    </label>
                    <select
                      id="triage-progression"
                      value={triageAnswers.progression}
                      onChange={(event) =>
                        setTriageAnswers((previous) => ({
                          ...previous,
                          progression: event.target.value,
                        }))
                      }
                    >
                      <option value="">Choose an option</option>
                      <option value="improving">Getting better</option>
                      <option value="unchanged">Staying the same</option>
                      <option value="worsening">Getting worse</option>
                    </select>

                    <div className="form-footer">
                      <button type="submit" disabled={asking}>
                        {asking ? 'Updating summary…' : 'Submit follow-up answers'}
                      </button>
                    </div>
                  </form>
                )}


                {answer.summary.unanswered_questions?.length > 0 && (
                  <>
                    <h4>Questions still to answer</h4>
                    <ul>
                      {answer.summary.unanswered_questions.map((item, index) => (
                        <li key={`${item}-${index}`}>{item}</li>
                      ))}
                    </ul>
                  </>
                )}

                {answer.recommended_doctors?.length > 0 && (
                  <>
                    <h4>Suggested doctors</h4>
                    <ul>
                      {answer.recommended_doctors.map((doctor, index) => (
                        <li key={doctor.doctor_id || doctor.composite_doctor_id || index}>
                          {doctor.doctor_name || 'Doctor'}
                          {doctor.doctor_type ? ` — ${doctor.doctor_type}` : ''}
                          {doctor.city ? `, ${doctor.city}` : ''}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </>
            )}

            <p className="muted">
              This is preliminary guidance, not a diagnosis. A qualified healthcare
              professional should assess your symptoms.
            </p>
          </section>
        )}

      </div>
    )
  }

  
function renderDoctorsPage() {
  return (
    <div className="doctors-page">
      <section className="doctors-intro">
        <span className="eyebrow">HEALTHCARE DIRECTORY</span>
        <h2>Find the right doctor</h2>
        <p>
          Discover healthcare professionals by location and specialty.
          Compare experience and consultation fees to make an informed choice.
        </p>
      </section>

      <section className="doctor-search-panel">
        <div className="doctor-search-heading">
          <div className="doctor-search-icon">⌕</div>
          <div>
            <h3>Find a healthcare professional</h3>
            <p>Refine your search using the filters below.</p>
          </div>
        </div>

        <form className="doctor-search-form" onSubmit={searchDoctors}>
          <div className="doctor-search-field">
            <label htmlFor="city">City</label>
            <input
              id="city"
              value={city}
              onChange={(event) => setCity(event.target.value)}
              placeholder="e.g. Delhi"
            />
          </div>

          <div className="doctor-search-field">
            <label htmlFor="specialty">Specialty</label>
            <input
              id="specialty"
              value={specialty}
              onChange={(event) => setSpecialty(event.target.value)}
              placeholder="e.g. Cardiologist"
            />
          </div>

          <div className="doctor-search-field">
            <label htmlFor="sort">Sort results by</label>
            <select
              id="sort"
              value={sortBy}
              onChange={(event) => setSortBy(event.target.value)}
            >
              <option value="name">Name</option>
              <option value="experience">Experience</option>
              <option value="fees">Consultation fees</option>
            </select>
          </div>

          <button type="submit" disabled={searchingDoctors}>
            {searchingDoctors ? 'Searching…' : 'Search doctors'}
          </button>
        </form>
      </section>

      {doctorError && (
        <div className="error-box doctor-error" role="alert">
          {doctorError}
        </div>
      )}

      {doctorCount !== null && (
        <section className="doctor-results-section">
          <div className="doctor-results-heading">
            <div>
              <span className="eyebrow">YOUR SEARCH</span>
              <h3>Available doctors</h3>
            </div>
            <span className="doctor-count">
              {doctorCount} {doctorCount === 1 ? 'doctor' : 'doctors'} found
            </span>
          </div>

          {doctorCount === 0 ? (
            <div className="doctor-empty-state">
              <div className="doctor-empty-icon">⌕</div>
              <h3>No doctors found</h3>
              <p>
                We couldn't find doctors matching those filters.
                Try another city or specialty.
              </p>
            </div>
          ) : (
            <div className="doctor-results-grid">
              {doctors.map((doctor, index) => (
                <article
                  className="doctor-result-card"
                  key={
                    doctor.composite_doctor_id ||
                    doctor.doctor_id ||
                    index
                  }
                >
                  <div className="doctor-card-top">
                    <div className="doctor-profile">
                      <div className="doctor-result-avatar">
                        {(doctor.doctor_name || 'D')
                          .slice(0, 1)
                          .toUpperCase()}
                      </div>

                      <div className="doctor-result-identity">
                        <h3>{doctor.doctor_name || 'Doctor'}</h3>
                        <span>
                          {doctor.doctor_type || 'Medical professional'}
                        </span>
                      </div>
                    </div>

                    <span className="doctor-specialty-tag">
                      {doctor.doctor_type || 'General'}
                    </span>
                  </div>

                  <div className="doctor-card-details">
                    <div className="doctor-detail-item">
                      <span>Location</span>
                      <strong>
                        {doctor.city || doctor.location || 'Not listed'}
                      </strong>
                    </div>

                    <div className="doctor-detail-item">
                      <span>Experience</span>
                      <strong>
                        {doctor.experience_years ?? '—'} years
                      </strong>
                    </div>

                    <div className="doctor-detail-item doctor-fee-item">
                      <span>Consultation fee</span>
                      <strong>
                        {doctor.fees == null
                          ? 'Not listed'
                          : `₹${doctor.fees}`}
                      </strong>
                    </div>
                  </div>

                  <button
                    className="doctor-book-button"
                    onClick={() => {
                      setDoctorId(String(doctor.doctor_id || ''))
                      setActivePage('appointments')
                    }}
                  >
                    Book appointment <span aria-hidden="true">→</span>
                  </button>
                </article>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  )
}


function renderAppointmentsPage() {
  return (
    <div className="appointments-page">
      <section className="appointments-intro">
        <span className="eyebrow">CARE COORDINATION</span>
        <h2>Your appointments, made simpler.</h2>
        <p>
          Find available slots, request appointments and keep track of
          your existing bookings in one place.
        </p>
      </section>

      <div className="appointment-disclaimer">
        <span className="appointment-disclaimer-icon">i</span>
        <div>
          <strong>About appointment availability</strong>
          <p>
            These are application-level appointment slots, not live
            hospital schedules. Confirm availability with the healthcare
            provider before attending.
          </p>
        </div>
      </div>

      {!authUser && (
        <section className="appointment-auth-card">
          <div className="appointment-auth-icon">♧</div>
          <div>
            <h3>Sign in to manage your appointments</h3>
            <p>
              Access booking proposals, confirm appointments and
              manage existing bookings securely.
            </p>
            <button
              type="button"
              className="appointment-primary-button"
              onClick={() => {
                setAuthMode('login')
                setActivePage('auth')
              }}
            >
              Sign in to continue →
            </button>
          </div>
        </section>
      )}

      {authUser && (
        <>
          <div className="appointments-workspace">
            <section className="appointment-panel appointment-search-panel">
              <div className="appointment-section-heading">
                <div className="appointment-section-icon appointment-blue">
                  <span>⌕</span>
                </div>
                <div>
                  <span className="eyebrow">STEP 01</span>
                  <h3>Find available slots</h3>
                  <p>Choose a doctor and your preferred appointment date.</p>
                </div>
              </div>

              <form onSubmit={loadSlots} className="appointment-form">
                <div className="appointment-field">
                  <label htmlFor="doctorId">Doctor ID</label>
                  <input
                    id="doctorId"
                    type="number"
                    min="1"
                    value={doctorId}
                    onChange={(event) => setDoctorId(event.target.value)}
                    placeholder="Enter doctor ID"
                    required
                  />
                </div>

                <div className="appointment-field">
                  <label htmlFor="appointmentDate">Appointment date</label>
                  <input
                    id="appointmentDate"
                    type="date"
                    value={appointmentDate}
                    onChange={(event) => setAppointmentDate(event.target.value)}
                    required
                  />
                </div>

                <button type="submit" className="appointment-primary-button">
                  Find available slots →
                </button>
              </form>

              {slotError && (
                <div className="appointment-inline-error" role="alert">
                  {slotError}
                </div>
              )}

              {slots.length > 0 && (
                <div className="appointment-slots">
                  <div className="appointment-slots-heading">
                    <h4>Available time slots</h4>
                    <span>{slots.length} found</span>
                  </div>

                  <div className="appointment-slot-list">
                    {slots.map((slot) => (
                      <label
                        className={`appointment-slot-option ${
                          selectedSlot === String(slot.slot_id) ? 'selected' : ''
                        }`}
                        key={slot.slot_id}
                      >
                        <input
                          type="radio"
                          name="slot"
                          value={slot.slot_id}
                          checked={selectedSlot === String(slot.slot_id)}
                          onChange={() => setSelectedSlot(String(slot.slot_id))}
                        />
                        <span className="appointment-slot-time">
                          {slot.appointment_time}
                        </span>
                        <span className="appointment-slot-date">
                          {slot.appointment_date}
                        </span>
                        <span className="appointment-slot-status">
                          Available
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              <details className="appointment-development-tools">
                <summary>Development tools · Create a test slot</summary>
                <p>
                  This is an administrative development feature, not a
                  patient-facing hospital scheduling function.
                </p>

                <form onSubmit={createSlot} className="appointment-form">
                  <div className="appointment-field">
                    <label htmlFor="appointmentTime">Slot time</label>
                    <input
                      id="appointmentTime"
                      type="time"
                      value={appointmentTime}
                      onChange={(event) => setAppointmentTime(event.target.value)}
                      required
                    />
                  </div>

                  <button
                    type="submit"
                    className="appointment-secondary-button"
                  >
                    Create test slot
                  </button>
                </form>
              </details>
            </section>

            <section className="appointment-panel appointment-booking-panel">
              <div className="appointment-section-heading">
                <div className="appointment-section-icon appointment-mint">
                  <span>✓</span>
                </div>
                <div>
                  <span className="eyebrow">STEP 02</span>
                  <h3>Request an appointment</h3>
                  <p>Enter patient details to create a booking proposal.</p>
                </div>
              </div>

              <form onSubmit={bookAppointment} className="appointment-form">
                <div className="appointment-field">
                  <label htmlFor="selectedSlot">Selected slot ID</label>
                  <input
                    id="selectedSlot"
                    type="number"
                    min="1"
                    value={selectedSlot}
                    onChange={(event) => setSelectedSlot(event.target.value)}
                    placeholder="Select a slot above"
                    required
                  />
                </div>

                <div className="appointment-field">
                  <label htmlFor="patientName">Patient name</label>
                  <input
                    id="patientName"
                    value={patientName}
                    onChange={(event) => setPatientName(event.target.value)}
                    maxLength={100}
                    placeholder="Enter patient's full name"
                    required
                  />
                </div>

                <div className="appointment-field">
                  <label htmlFor="patientContact">Contact details</label>
                  <input
                    id="patientContact"
                    value={patientContact}
                    onChange={(event) => setPatientContact(event.target.value)}
                    maxLength={30}
                    placeholder="Phone number or email"
                    required
                  />
                </div>

                <button type="submit" className="appointment-primary-button">
                  Create booking proposal →
                </button>
              </form>

              {booking && (
                <div className="appointment-result-card">
                  <div className="appointment-result-heading">
                    <span className="appointment-result-icon">✓</span>
                    <div>
                      <h4>Booking response</h4>
                      <p>Your latest booking request response.</p>
                    </div>
                  </div>

                  {booking.status && (
                    <div className="appointment-result-status">
                      <span>Status</span>
                      <strong>
                        {String(booking.status).replaceAll('_', ' ')}
                      </strong>
                    </div>
                  )}

                  {(booking.booking_reference || booking.reference) && (
                    <div className="appointment-reference">
                      <span>Booking reference</span>
                      <strong>
                        {booking.booking_reference || booking.reference}
                      </strong>
                      <button
                        type="button"
                        className="appointment-text-button"
                        onClick={() =>
                          setBookingReference(
                            booking.booking_reference || booking.reference
                          )
                        }
                      >
                        Use for lookup →
                      </button>
                    </div>
                  )}

                  {booking.status === 'proposal_created' && (
                    <button
                      type="button"
                      className="appointment-primary-button"
                      onClick={confirmBookingProposal}
                    >
                      Explicitly confirm appointment →
                    </button>
                  )}

                  <details className="appointment-response-details">
                    <summary>View complete booking response</summary>
                    <pre>{JSON.stringify(booking, null, 2)}</pre>
                  </details>
                </div>
              )}
            </section>
          </div>

          <section className="appointment-panel appointment-lookup-panel">
            <div className="appointment-section-heading">
              <div className="appointment-section-icon appointment-lavender">
                <span>⌕</span>
              </div>
              <div>
                <span className="eyebrow">BOOKING MANAGEMENT</span>
                <h3>Manage an existing booking</h3>
                <p>Retrieve your booking details using its reference.</p>
              </div>
            </div>

            <form
              className="appointment-lookup-form"
              onSubmit={lookUpAppointment}
            >
              <div className="appointment-field">
                <label htmlFor="bookingReference">Booking reference</label>
                <input
                  id="bookingReference"
                  value={bookingReference}
                  onChange={(event) => setBookingReference(event.target.value)}
                  placeholder="Enter your booking reference"
                  required
                />
              </div>

              <button
                type="submit"
                className="appointment-secondary-button"
              >
                Look up booking →
              </button>
            </form>

            {lookupResult && (
              <div className="appointment-result-card appointment-lookup-result">
                <div className="appointment-result-heading">
                  <span className="appointment-result-icon">✓</span>
                  <div>
                    <h4>Booking details</h4>
                    <p>Retrieved booking information.</p>
                  </div>
                </div>

                <div className="appointment-result-status">
                  <span>Current status</span>
                  <strong>
                    {String(lookupResult.status || 'Unknown').replaceAll('_', ' ')}
                  </strong>
                </div>

                {String(lookupResult.status || '').toLowerCase() === 'confirmed' && (
                  <button
                    type="button"
                    className="appointment-danger-button"
                    onClick={cancelExistingAppointment}
                  >
                    Cancel appointment
                  </button>
                )}

                <details className="appointment-response-details">
                  <summary>View complete booking details</summary>
                  <pre>{JSON.stringify(lookupResult, null, 2)}</pre>
                </details>
              </div>
            )}
          </section>

          {bookingError && (
            <div className="error-box appointment-global-error" role="alert">
              {bookingError}
            </div>
          )}
        </>
      )}
    </div>
  )
}



  if (authChecking) {
    return (
      <div className="app-loading">
        Restoring your session...
      </div>
    )
  }

  
  return (
    <>
      <AppLayout
        activePage={activePage}
        setActivePage={setActivePage}
        authUser={authUser}
        onSignIn={() => {
          setAuthMode('login')
          setAuthError('')
          setAuthMessage('')
          setActivePage('auth')
        }}
        onLogout={logOut}
      >
        <div className="page-content">
          {activePage === 'overview' && renderOverview()}
          {activePage === 'medical' && renderMedicalPage()}
          {activePage === 'doctors' && renderDoctorsPage()}
          {activePage === 'appointments' && renderAppointmentsPage()}
          {activePage === 'auth' && renderAuthPage()}
        </div>

        <footer className="footer">
          Healthcare Navigator · Prototype · For informational use only
        </footer>
      </AppLayout>

      {showLogoutModal && (
        <div className="logout-modal-overlay">
          <div
            className="logout-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="logout-modal-title"
          >
            <h2 id="logout-modal-title">Sign out?</h2>

            <p>
              Are you sure you want to sign out of your account?
            </p>

            <div className="logout-modal-actions">
              <button
                type="button"
                className="logout-cancel-button"
                onClick={() => setShowLogoutModal(false)}
              >
                Cancel
              </button>

              <button
                type="button"
                className="logout-confirm-button"
                onClick={confirmLogout}
              >
                Yes, sign out
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )

}

export default App

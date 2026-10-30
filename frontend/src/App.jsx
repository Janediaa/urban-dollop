
import { useEffect, useState } from 'react'
import './App.css'

const navItems = [
  { id: 'overview', label: 'Overview', icon: '⌂' },
  { id: 'medical', label: 'Medical AI', icon: '✳' },
  { id: 'doctors', label: 'Find doctors', icon: '⚕' },
  { id: 'appointments', label: 'Appointments', icon: '▦' },
]

function App() {
  const [activePage, setActivePage] = useState('overview')
  const [authMode, setAuthMode] = useState('login')
  const [authUser, setAuthUser] = useState(null)
  const [showLogoutModal, setShowLogoutModal] = useState(false)
  const [authToken, setAuthToken] = useState('')
  const [authChecking, setAuthChecking] = useState(true)

  useEffect(() => {
    const savedToken = localStorage.getItem('healthcare_auth_token')

    if (!savedToken) {
      setAuthChecking(false)
      return
    }

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
        // A later refresh can retry session restoration.
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
    if (!answer || answer.intent === 'triage') return null


    const sources = Array.isArray(answer.sources) ? answer.sources : []

    return (
      <div className="answer-card">
        <h3>Answer</h3>
        <p className="answer-text">
          {answer.answer || 'No answer was returned.'}
        </p>
        {sources.length > 0 && (
          <div className="sources">
            <h4>Sources</h4>
            {sources.map((source, index) => (
              <div className="source-item" key={source.source || source.filename || index}>
                <span className="source-number">[{index + 1}]</span>
                <span>{source.title || source.source || source.filename || JSON.stringify(source)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  function renderOverview() {
    return (
      <>
        <div className="welcome">
          <span className="eyebrow">YOUR HEALTH, ONE PLACE</span>
          <h2>How can we help you today?</h2>
          <p>Medical information, doctor discovery and appointment management in one workspace.</p>
        </div>

        <form className="quick-question" onSubmit={(event) => {
          setActivePage('medical')
          askMedicalQuestion(event)
        }}>
          <span className="question-icon">✳</span>
          <input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask a health-related question..."
            minLength={3}
            required
          />
          <button type="submit" disabled={asking}>Ask AI ↗</button>
        </form>

        <div className="section-heading">
          <div>
            <span className="eyebrow">YOUR WORKSPACE</span>
            <h3>Explore Healthcare Navigator</h3>
          </div>
        </div>

        <div className="feature-grid">
          <button className="feature-card" onClick={() => setActivePage('medical')}>
            <span className="feature-icon mint">✳</span>
            <span className="feature-title">Medical AI</span>
            <span className="feature-description">Get evidence-informed answers from your medical knowledge base.</span>
            <span className="feature-link">Ask a question ↗</span>
          </button>
          <button className="feature-card" onClick={() => {
            setActivePage('doctors')
            searchDoctors()
          }}>
            <span className="feature-icon blue">⚕</span>
            <span className="feature-title">Find a doctor</span>
            <span className="feature-description">Search doctors by city and specialty, with experience and fee filters.</span>
            <span className="feature-link">Explore doctors ↗</span>
          </button>
          <button className="feature-card" onClick={() => setActivePage('appointments')}>
            <span className="feature-icon peach">▦</span>
            <span className="feature-title">Appointments</span>
            <span className="feature-description">Browse available slots and manage your application bookings.</span>
            <span className="feature-link">Manage appointments ↗</span>
          </button>
        </div>

        <div className="notice">
          <strong>Important:</strong> Medical AI provides general health information, not a diagnosis.
          For emergencies, seek immediate medical attention.
        </div>
      </>
    )
  }

  function renderMedicalPage() {
    return (
      <>
        <div className="page-intro">
          <span className="eyebrow">MEDICAL KNOWLEDGE ASSISTANT</span>
          <h2>Ask Medical AI</h2>
          <p>Ask a health-information question. Answers are generated using your medical knowledge base and may not replace professional advice.</p>
        </div>
        
        <section className="emergency-help" aria-labelledby="emergency-help-title">
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

        <form className="panel question-form" onSubmit={askMedicalQuestion}>
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
          <section className="panel">
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

      </>
    )
  }

  function renderDoctorsPage() {
    return (
      <>
        <div className="page-intro">
          <span className="eyebrow">HEALTHCARE DIRECTORY</span>
          <h2>Find the right doctor</h2>
          <p>Search the doctors available in the Healthcare Navigator database.</p>
        </div>

        <form className="panel filter-form" onSubmit={searchDoctors}>
          <div className="field">
            <label htmlFor="city">City</label>
            <input id="city" value={city} onChange={(event) => setCity(event.target.value)} placeholder="e.g. delhi" />
          </div>
          <div className="field">
            <label htmlFor="specialty">Specialty</label>
            <input id="specialty" value={specialty} onChange={(event) => setSpecialty(event.target.value)} placeholder="e.g. cardiologist" />
          </div>
          <div className="field">
            <label htmlFor="sort">Sort results by</label>
            <select id="sort" value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
              <option value="name">Name</option>
              <option value="experience">Experience</option>
              <option value="fees">Consultation fees</option>
            </select>
          </div>
          <button type="submit" disabled={searchingDoctors}>
            {searchingDoctors ? 'Searching…' : 'Search doctors'}
          </button>
        </form>

        {doctorError && <div className="error-box">{doctorError}</div>}
        {doctorCount !== null && (
          <div className="results-heading">
            <h3>Search results</h3>
            <span>{doctorCount} doctors found</span>
          </div>
        )}

        <div className="doctor-grid">
          {doctors.map((doctor, index) => (
            <article className="doctor-card" key={doctor.composite_doctor_id || doctor.doctor_id || index}>
              <div className="doctor-avatar">{(doctor.doctor_name || 'D').slice(0, 1).toUpperCase()}</div>
              <div className="doctor-main">
                <h3>{doctor.doctor_name || 'Doctor'}</h3>
                <p>{doctor.doctor_type || 'Medical professional'}</p>
              </div>
              <div className="doctor-details">
                <span>Location</span><strong>{doctor.city || doctor.location || 'Not listed'}</strong>
                <span>Experience</span><strong>{doctor.experience_years ?? '—'} years</strong>
                <span>Fees</span><strong>{doctor.fees == null ? 'Not listed' : `₹${doctor.fees}`}</strong>
              </div>
              <button className="secondary-button" onClick={() => {
                setDoctorId(String(doctor.doctor_id || ''))
                setActivePage('appointments')
              }}>Book appointment</button>
            </article>
          ))}
        </div>
        {doctorCount === 0 && <div className="empty-state">No doctors matched those filters. Try a different city or specialty.</div>}
      </>
    )
  }

  function renderAppointmentsPage() {
    return (
      <>
        <div className="page-intro">
          <span className="eyebrow">CARE COORDINATION</span>
          <h2>Appointments</h2>
          <p>Manage application-level appointment slots. These are not live hospital schedules.</p>
        </div>
        {!authUser && (
          <div className="notice">
            Please sign in to create bookings, look up appointments, or cancel them.
            <button
              type="button"
              className="secondary-button"
              onClick={() => {
                setAuthMode('login')
                setActivePage('auth')
              }}
            >
              Sign in
            </button>
          </div>
        )}
        {authUser && <div className="two-column">
          <section className="panel">
            <h3>Find available slots</h3>
            <form onSubmit={loadSlots} className="stack-form">
              <div className="field">
                <label htmlFor="doctorId">Doctor ID</label>
                <input id="doctorId" type="number" min="1" value={doctorId} onChange={(event) => setDoctorId(event.target.value)} required />
              </div>
              <div className="field">
                <label htmlFor="appointmentDate">Date</label>
                <input id="appointmentDate" type="date" value={appointmentDate} onChange={(event) => setAppointmentDate(event.target.value)} required />
              </div>
              <button type="submit">Find slots</button>
            </form>

            <form onSubmit={createSlot} className="stack-form create-slot-form">
              <h4>Development: create a slot</h4>
              <div className="field">
                <label htmlFor="appointmentTime">Time</label>
                <input id="appointmentTime" type="time" value={appointmentTime} onChange={(event) => setAppointmentTime(event.target.value)} required />
              </div>
              <button type="submit" className="secondary-button">Create slot</button>
            </form>


            {slotError && <div className="inline-message">{slotError}</div>}
            {slots.length > 0 && (
              <div className="slot-list">
                <h4>Available slots</h4>
                {slots.map((slot) => (
                  <label className={`slot-option ${selectedSlot === String(slot.slot_id) ? 'selected' : ''}`} key={slot.slot_id}>
                    <input
                      type="radio"
                      name="slot"
                      value={slot.slot_id}
                      checked={selectedSlot === String(slot.slot_id)}
                      onChange={() => setSelectedSlot(String(slot.slot_id))}
                    />
                    <span>{slot.appointment_date} · {slot.appointment_time}</span>
                    <span className="slot-available">Available</span>
                  </label>
                ))}
              </div>
            )}
          </section>

          <section className="panel">
            <h3>Book your appointment</h3>
            <form onSubmit={bookAppointment} className="stack-form">
              <div className="field">
                <label htmlFor="selectedSlot">Selected slot ID</label>
                <input id="selectedSlot" type="number" min="1" value={selectedSlot} onChange={(event) => setSelectedSlot(event.target.value)} required />
              </div>
              <div className="field">
                <label htmlFor="patientName">Patient name</label>
                <input id="patientName" value={patientName} onChange={(event) => setPatientName(event.target.value)} maxLength={100} required />
              </div>
              <div className="field">
                <label htmlFor="patientContact">Contact details</label>
                <input id="patientContact" value={patientContact} onChange={(event) => setPatientContact(event.target.value)} maxLength={30} placeholder="Phone or email" required />
              </div>
              <button type="submit">
                Create booking proposal
              </button>
            </form>


            {booking && (
              <div className="success-box">
                <h4>Booking response</h4>

                <pre>{JSON.stringify(booking, null, 2)}</pre>

                {booking.status === 'proposal_created' && (
                  <button
                    type="button"
                    onClick={confirmBookingProposal}
                  >
                    Explicitly confirm appointment
                  </button>
                )}

                {(booking.booking_reference || booking.reference) && (
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() =>
                      setBookingReference(
                        booking.booking_reference || booking.reference
                      )
                    }
                  >
                    Use reference for lookup
                  </button>
                )}
              </div>
            )}

            <form className="stack-form lookup-form" onSubmit={lookUpAppointment}>
              <h4>Find an existing booking</h4>
              <div className="field">
                <label htmlFor="bookingReference">Booking reference</label>
                <input id="bookingReference" value={bookingReference} onChange={(event) => setBookingReference(event.target.value)} required />
              </div>
              <button type="submit" className="secondary-button">Look up booking</button>
            </form>


            {lookupResult && (
              <div className="success-box">
                <h4>Booking details</h4>

                <pre>{JSON.stringify(lookupResult, null, 2)}</pre>

                {String(lookupResult.status || '').toLowerCase() === 'confirmed' && (
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={cancelExistingAppointment}
                  >
                    Cancel appointment
                  </button>
                )}
              </div>
            )}

            {bookingError && (
              <div className="error-box">{bookingError}</div>
            )}
          </section>
        </div>
        }
      </>
    )
  }

  const pageTitles = {
    overview: 'Overview',
    medical: 'Medical AI',
    doctors: 'Find doctors',
    appointments: 'Appointments',
    auth: 'Sign in',
  }


  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">H+</span>
          <div>
            <strong>Healthcare</strong>
            <span>Navigator</span>
          </div>
        </div>

        <div className="workspace-label">WORKSPACE</div>

        <nav className="nav-list">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${activePage === item.id ? 'active' : ''}`}
              onClick={() => setActivePage(item.id)}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="status-dot" />
          <div>
            <strong>API connected</strong>
            <span>Local development</span>
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div>
            <span className="breadcrumb">Healthcare Navigator /</span>
            <strong>{pageTitles[activePage]}</strong>
          </div>

          <div className="topbar-actions">
            {authUser ? (
              <>
                <span>Signed in as {authUser.full_name}</span>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={logOut}
                >
                  Sign out
                </button>
              </>
            ) : (
              <button
                type="button"
                className="secondary-button"
                onClick={() => {
                  setAuthMode('login')
                  setAuthError('')
                  setAuthMessage('')
                  setActivePage('auth')
                }}
              >
                Sign in
              </button>
            )}

            <span className="environment-pill">
              <span /> DEVELOPMENT
            </span>
          </div>
        </header>

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
      </main>

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
    </div>
  )
}

export default App


import { useState } from 'react'
import './App.css'

const navItems = [
  { id: 'overview', label: 'Overview', icon: '⌂' },
  { id: 'medical', label: 'Medical AI', icon: '✳' },
  { id: 'doctors', label: 'Find doctors', icon: '⚕' },
  { id: 'appointments', label: 'Appointments', icon: '▦' },
]

function App() {
  const [activePage, setActivePage] = useState('overview')
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState(null)
  const [asking, setAsking] = useState(false)
  const [medicalError, setMedicalError] = useState('')

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

  async function askMedicalQuestion(event) {
    event.preventDefault()
    setAsking(true)
    setAnswer(null)
    setMedicalError('')

    try {
      const response = await fetch('/medical/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, top_k: 3 }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Unable to answer your question.')
      setAnswer(data)
    } catch (error) {
      setMedicalError(error.message)
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

    try {
      const response = await fetch('/appointments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          slot_id: Number(selectedSlot),
          patient_name: patientName,
          patient_contact: patientContact,
        }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Unable to book appointment.')
      setBooking(data)
    } catch (error) {
      setBookingError(error.message)
    }
  }

  async function lookUpAppointment(event) {
    event.preventDefault()
    setLookupResult(null)
    setBookingError('')

    try {
      const response = await fetch(`/appointments/${encodeURIComponent(bookingReference.trim())}`)
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Appointment not found.')
      setLookupResult(data)
    } catch (error) {
      setBookingError(error.message)
    }
  }

  
async function cancelExistingAppointment() {
  if (!bookingReference.trim()) return

  const confirmed = window.confirm(
    'Are you sure you want to cancel this appointment?'
  )

  if (!confirmed) return

  setBookingError('')
  setLookupResult(null)

  try {
    const response = await fetch(
      `/appointments/${encodeURIComponent(bookingReference.trim())}/cancel`,
      { method: 'POST' }
    )

    const data = await response.json()

    if (!response.ok) {
      throw new Error(data.detail || 'Unable to cancel appointment.')
    }

    setLookupResult(data)
  } catch (error) {
    setBookingError(error.message)
  }
}


  function renderMedicalAnswer() {
    if (!answer) return null

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

        <div className="two-column">
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
              <button type="submit">Confirm booking</button>
            </form>

            {booking && (
              <div className="success-box">
                <h4>Booking response</h4>
                <pre>{JSON.stringify(booking, null, 2)}</pre>
                {(booking.booking_reference || booking.reference) && (
                  <button className="secondary-button" onClick={() => setBookingReference(booking.booking_reference || booking.reference)}>
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

            {bookingError && <div className="error-box">{bookingError}</div>}
          </section>
        </div>
      </>
    )
  }

  const pageTitles = {
    overview: 'Overview',
    medical: 'Medical AI',
    doctors: 'Find doctors',
    appointments: 'Appointments',
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">H+</span>
          <div><strong>Healthcare</strong><span>Navigator</span></div>
        </div>
        <div className="workspace-label">WORKSPACE</div>
        <nav className="nav-list">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${activePage === item.id ? 'active' : ''}`}
              onClick={() => setActivePage(item.id)}
            >
              <span className="nav-icon">{item.icon}</span>{item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="status-dot" />
          <div><strong>API connected</strong><span>Local development</span></div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div>
            <span className="breadcrumb">Healthcare Navigator /</span>
            <strong>{pageTitles[activePage]}</strong>
          </div>
          <span className="environment-pill"><span /> DEVELOPMENT</span>
        </header>

        <div className="page-content">
          {activePage === 'overview' && renderOverview()}
          {activePage === 'medical' && renderMedicalPage()}
          {activePage === 'doctors' && renderDoctorsPage()}
          {activePage === 'appointments' && renderAppointmentsPage()}
        </div>
        <footer className="footer">Healthcare Navigator · Prototype · For informational use only</footer>
      </main>
    </div>
  )
}

export default App

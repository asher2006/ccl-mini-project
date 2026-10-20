import { useState, useEffect, useRef } from 'react'

const API = '/api'

function formatDate(s) {
  if (!s) return ''
  try {
    const d = new Date(s)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + d.toLocaleDateString()
  } catch {
    return s
  }
}

export default function App() {
  const [url, setUrl] = useState('')
  const [format, setFormat] = useState('mp4')
  const [email, setEmail] = useState('')
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [time, setTime] = useState('')
  const [activeWindow, setActiveWindow] = useState('main') // 'main' | 'logs'
  const pollingRef = useRef(null)

  // Real-time retro clock
  useEffect(() => {
    const updateTime = () => {
      const now = new Date()
      setTime(now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }))
    }
    updateTime()
    const timer = setInterval(updateTime, 1000)
    return () => clearInterval(timer)
  }, [])

  const fetchJobs = async () => {
    try {
      const r = await fetch(`${API}/jobs?limit=25`)
      if (r.ok) {
        const j = await r.json()
        setJobs(Array.isArray(j) ? j : [])
      }
    } catch {}
  }

  useEffect(() => {
    fetchJobs()
    pollingRef.current = setInterval(fetchJobs, 3000)
    return () => clearInterval(pollingRef.current)
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    const trimmed = url.trim()
    if (!trimmed) {
      setError('ERROR: [NULL_PTR] Please specify a valid media URI.')
      return
    }

    const lower = trimmed.toLowerCase()
    if (!lower.includes('youtube.com') && !lower.includes('youtu.be') && !lower.includes('instagram.com')) {
      setError('UNSUPPORTED_HOST: Valid protocols: YouTube, Instagram.')
      return
    }

    setLoading(true)
    try {
      const r = await fetch(`${API}/jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: trimmed, format, email: email.trim() })
      })
      const resp = await r.json()
      if (!r.ok) {
        throw new Error(resp.detail || 'EXEC_FAIL: Cloud drop rejected.')
      }
      setUrl('')
      fetchJobs()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="scanlines" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      
      {/* ── DESKTOP ICONS (Visible on desktop/tablet) ── */}
      <div style={{
        position: 'absolute',
        top: 16,
        left: 16,
        display: 'flex',
        flexDirection: 'column',
        gap: 18,
        zIndex: 5,
        userSelect: 'none'
      }} className="desktop-only">
        <div
          onClick={() => setActiveWindow('main')}
          style={{ width: 72, textAlign: 'center', cursor: 'pointer' }}
        >
          <div style={{
            width: 42,
            height: 42,
            margin: '0 auto 4px',
            background: 'var(--surface)',
            border: '2px outset #fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 20
          }}>
            💾
          </div>
          <span style={{
            fontSize: 11,
            color: '#fff',
            background: activeWindow === 'main' ? '#000080' : 'transparent',
            padding: '1px 3px',
            fontFamily: 'var(--font-retro)'
          }}>
            CloudDrop.exe
          </span>
        </div>

        <div
          onClick={() => setActiveWindow('logs')}
          style={{ width: 72, textAlign: 'center', cursor: 'pointer' }}
        >
          <div style={{
            width: 42,
            height: 42,
            margin: '0 auto 4px',
            background: 'var(--surface)',
            border: '2px outset #fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 20
          }}>
            🗄️
          </div>
          <span style={{
            fontSize: 11,
            color: '#fff',
            background: activeWindow === 'logs' ? '#000080' : 'transparent',
            padding: '1px 3px',
            fontFamily: 'var(--font-retro)'
          }}>
            S3_Bucket
          </span>
        </div>

        <div style={{ width: 72, textAlign: 'center', cursor: 'pointer', opacity: 0.85 }}>
          <div style={{
            width: 42,
            height: 42,
            margin: '0 auto 4px',
            background: 'var(--surface)',
            border: '2px outset #fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 20
          }}>
            🌐
          </div>
          <span style={{ fontSize: 11, color: '#fff', padding: '1px 3px', fontFamily: 'var(--font-retro)' }}>
            AWS_VPC
          </span>
        </div>
      </div>

      {/* ── WORKSPACE AREA ── */}
      <div style={{
        flex: 1,
        padding: '16px 12px 64px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        
        {/* WINDOW: MAIN CLOUDDROP APPLICATION */}
        <div className="bevel-outset" style={{
          width: '100%',
          maxWidth: 680,
          padding: 3,
          boxShadow: '4px 6px 0px rgba(0, 0, 0, 0.45)',
          zIndex: 15
        }}>
          {/* WINDOW HEADER */}
          <div className="title-bar">
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span>💾</span>
              <span style={{ letterSpacing: '0.5px' }}>CLOUDDROP_95.EXE [AWS-US-EAST-1]</span>
            </div>
            <div style={{ display: 'flex', gap: 3 }}>
              <button className="retro-button" style={{ width: 18, height: 16, fontSize: 10, padding: 0, lineHeight: 1 }}>_</button>
              <button className="retro-button" style={{ width: 18, height: 16, fontSize: 10, padding: 0, lineHeight: 1 }}>□</button>
              <button className="retro-button" style={{ width: 18, height: 16, fontSize: 10, padding: 0, lineHeight: 1, fontWeight: 'bold' }}>✕</button>
            </div>
          </div>

          {/* MENUBAR */}
          <div style={{
            display: 'flex',
            gap: 12,
            padding: '3px 8px',
            fontSize: 12,
            borderBottom: '1px solid var(--border-dark)',
            marginBottom: 8,
            fontFamily: 'var(--font-mono)'
          }}>
            <span style={{ textDecoration: 'underline', cursor: 'pointer' }}>F</span>ile
            <span style={{ textDecoration: 'underline', cursor: 'pointer' }}>E</span>dit
            <span style={{ textDecoration: 'underline', cursor: 'pointer' }}>Q</span>ueue
            <span style={{ textDecoration: 'underline', cursor: 'pointer' }}>H</span>elp
            <span style={{ marginLeft: 'auto', color: 'var(--text-muted)' }}>v1.95</span>
          </div>

          {/* MAIN WINDOW BODY */}
          <div style={{ padding: '6px 8px 10px' }}>
            
            {/* HERO NOTICE */}
            <div className="bevel-inset" style={{
              padding: '8px 12px',
              marginBottom: 14,
              backgroundColor: '#ffffcc',
              fontSize: 12,
              display: 'flex',
              alignItems: 'center',
              gap: 8
            }}>
              <span style={{ fontSize: 18 }}>⚠️</span>
              <div>
                <strong>SYSTEM NOTICE:</strong> EC2 Worker unit active. Video & Audio assets converted via <code>ffmpeg</code> + <code>yt-dlp</code> pipeline.
              </div>
            </div>

            {/* DOWNLOAD FORM */}
            <form onSubmit={handleSubmit}>
              <div style={{ marginBottom: 12 }}>
                <label style={{
                  display: 'block',
                  fontFamily: 'var(--font-retro)',
                  fontSize: 11,
                  letterSpacing: '0.5px',
                  marginBottom: 4
                }}>
                  MEDIA_LOCATOR [TARGET URI]:
                </label>
                <input
                  type="text"
                  value={url}
                  onChange={e => setUrl(e.target.value)}
                  placeholder="https://youtube.com/watch?v=... OR instagram.com/reel/..."
                  className="bevel-inset"
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    outline: 'none',
                    fontSize: 13,
                    fontFamily: 'var(--font-mono)'
                  }}
                />
              </div>

              {/* FORMAT & OPTIONS GRID */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                gap: 12,
                marginBottom: 14
              }}>
                {/* FORMAT FIELDSET */}
                <fieldset className="bevel-outset" style={{ padding: '8px 10px' }}>
                  <legend style={{ fontFamily: 'var(--font-retro)', fontSize: 11, padding: '0 4px' }}>
                    CONVERT_OUTPUT
                  </legend>
                  <div style={{ display: 'flex', gap: 16, marginTop: 4 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
                      <input
                        type="radio"
                        name="fmt"
                        checked={format === 'mp4'}
                        onChange={() => setFormat('mp4')}
                      />
                      <span>MP4 (Video)</span>
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
                      <input
                        type="radio"
                        name="fmt"
                        checked={format === 'mp3'}
                        onChange={() => setFormat('mp3')}
                      />
                      <span>MP3 (Audio)</span>
                    </label>
                  </div>
                </fieldset>

                {/* SNS EMAIL NOTIFIER */}
                <fieldset className="bevel-outset" style={{ padding: '8px 10px' }}>
                  <legend style={{ fontFamily: 'var(--font-retro)', fontSize: 11, padding: '0 4px' }}>
                    SNS_DISPATCH [OPTIONAL]
                  </legend>
                  <input
                    type="email"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    placeholder="user@system.net"
                    className="bevel-inset"
                    style={{
                      width: '100%',
                      padding: '5px 8px',
                      fontSize: 12,
                      fontFamily: 'var(--font-mono)',
                      outline: 'none'
                    }}
                  />
                </fieldset>
              </div>

              {/* ERROR NOTIFIER */}
              {error && (
                <div className="bevel-inset" style={{
                  padding: '8px 12px',
                  marginBottom: 14,
                  backgroundColor: '#ffebe8',
                  border: '1px solid var(--danger)',
                  color: 'var(--danger)',
                  fontSize: 12,
                  fontFamily: 'var(--font-mono)'
                }}>
                  {error}
                </div>
              )}

              {/* ACTION EXECUTE BUTTON */}
              <div style={{ display: 'flex', gap: 10 }}>
                <button
                  type="submit"
                  disabled={loading}
                  className="retro-button"
                  style={{
                    flex: 1,
                    padding: '10px 14px',
                    fontSize: 13,
                    fontWeight: 'bold',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    letterSpacing: '1px'
                  }}
                >
                  {loading ? (
                    <>
                      <span className="blink">■</span>
                      <span>BUFFERING_JOB...</span>
                    </>
                  ) : (
                    <>
                      <span>💾</span>
                      <span>EXECUTE_DOWNLOAD [SQS]</span>
                    </>
                  )}
                </button>

                <button
                  type="button"
                  onClick={fetchJobs}
                  className="retro-button"
                  style={{ padding: '10px 16px', fontSize: 12 }}
                  title="Query EC2/RDS database"
                >
                  ↻ REFRESH
                </button>
              </div>
            </form>

            {/* QUEUE & COMPLETED RECORDS TABLE */}
            <div style={{ marginTop: 20 }}>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 6
              }}>
                <span style={{ fontFamily: 'var(--font-retro)', fontSize: 11 }}>
                  RDS_SQL_RECORD_STREAM [JOBS]
                </span>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  {jobs.length} records in buffer
                </span>
              </div>

              <div className="bevel-inset" style={{
                maxHeight: 260,
                overflowY: 'auto',
                backgroundColor: '#ffffff',
                padding: 4
              }}>
                {jobs.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '24px 8px', color: 'var(--text-muted)', fontSize: 12 }}>
                    -- NO JOBS DETECTED IN SPOOLER --
                  </div>
                ) : (
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, textAlign: 'left' }}>
                    <thead>
                      <tr style={{ background: 'var(--surface)', borderBottom: '1px solid #000' }}>
                        <th style={{ padding: '4px 6px', fontFamily: 'var(--font-retro)', fontSize: 10 }}>STATUS</th>
                        <th style={{ padding: '4px 6px', fontFamily: 'var(--font-retro)', fontSize: 10 }}>FORMAT</th>
                        <th style={{ padding: '4px 6px', fontFamily: 'var(--font-retro)', fontSize: 10 }}>METADATA / TITLE</th>
                        <th style={{ padding: '4px 6px', fontFamily: 'var(--font-retro)', fontSize: 10, textAlign: 'right' }}>ACTION</th>
                      </tr>
                    </thead>
                    <tbody>
                      {jobs.map((j) => (
                        <tr key={j.job_id} style={{ borderBottom: '1px solid #ececec' }}>
                          <td style={{ padding: '6px', whiteSpace: 'nowrap' }}>
                            {j.status === 'complete' && (
                              <span style={{ color: 'var(--success)', fontWeight: 'bold' }}>[OK]</span>
                            )}
                            {j.status === 'processing' && (
                              <span style={{ color: 'var(--warning)', fontWeight: 'bold' }} className="blink">
                                [CONV...]
                              </span>
                            )}
                            {j.status === 'queued' && (
                              <span style={{ color: '#000080', fontWeight: 'bold' }}>[SPOOL]</span>
                            )}
                            {j.status === 'failed' && (
                              <span style={{ color: 'var(--danger)', fontWeight: 'bold' }}>[ERR]</span>
                            )}
                          </td>
                          <td style={{ padding: '6px', fontFamily: 'var(--font-retro)', fontSize: 10 }}>
                            {j.format?.toUpperCase()}
                          </td>
                          <td style={{ padding: '6px', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            <div style={{ fontWeight: 600 }}>{j.title || j.url}</div>
                            {j.error_msg && (
                              <div style={{ color: 'var(--danger)', fontSize: 11, fontStyle: 'italic' }}>
                                {j.error_msg}
                              </div>
                            )}
                          </td>
                          <td style={{ padding: '6px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                            {j.status === 'complete' && j.download_url ? (
                              <a
                                href={j.download_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="retro-button"
                                download
                                style={{
                                  display: 'inline-block',
                                  padding: '2px 8px',
                                  fontSize: 10,
                                  textDecoration: 'none',
                                  color: 'var(--text)'
                                }}
                              >
                                ↓ SAVE
                              </a>
                            ) : (
                              <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>--</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            {/* STATUSBAR STRIP */}
            <div className="bevel-inset" style={{
              marginTop: 12,
              padding: '3px 8px',
              fontSize: 11,
              display: 'flex',
              justifyContent: 'space-between',
              color: 'var(--text-muted)'
            }}>
              <span>VPC: 10.0.0.0/16</span>
              <span>RDS: postgres:5432</span>
              <span>STORAGE: S3 AES-256</span>
            </div>
          </div>
        </div>

      </div>

      {/* ── RETRO WINDOWS 95 TASKBAR (Fixed Bottom) ── */}
      <footer className="bevel-outset" style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        height: 38,
        display: 'flex',
        alignItems: 'center',
        padding: '0 4px',
        zIndex: 50,
        gap: 6
      }}>
        {/* START BUTTON */}
        <button
          className="retro-button"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            height: 28,
            padding: '2px 10px',
            fontFamily: 'var(--font-retro)',
            fontWeight: 'bold',
            fontSize: 12
          }}
        >
          <span style={{ fontSize: 14 }}>🪟</span>
          <span>Start</span>
        </button>

        {/* TASKBAR ITEM */}
        <div
          className="bevel-inset"
          style={{
            height: 28,
            padding: '4px 10px',
            fontSize: 11,
            fontFamily: 'var(--font-retro)',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            maxWidth: 220,
            overflow: 'hidden',
            whiteSpace: 'nowrap',
            backgroundColor: 'var(--surface)'
          }}
        >
          <span>💾</span>
          <span>CloudDrop_95</span>
        </div>

        {/* SYSTEM TRAY (RIGHT) */}
        <div
          className="bevel-inset"
          style={{
            marginLeft: 'auto',
            height: 28,
            padding: '0 10px',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            fontSize: 11,
            fontFamily: 'var(--font-mono)'
          }}
        >
          <span>☁️ EC2:OK</span>
          <span>{time || '12:00:00'}</span>
        </div>
      </footer>

      {/* RESPONSIVE DESKTOP-SPECIFIC MEDIA QUERIES */}
      <style>{`
        @media (max-width: 768px) {
          .desktop-only {
            display: none !important;
          }
        }
      `}</style>
    </div>
  )
}

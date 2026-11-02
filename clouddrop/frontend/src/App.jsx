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

function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

const OPERATIONS = [
  { id: 'img2pdf', label: 'Image to PDF', icon: '🖼️', desc: 'Convert JPG, PNG, or WEBP images into a clean PDF document' },
  { id: 'pdf2img', label: 'PDF to Image', icon: '📸', desc: 'Extract high-resolution PNG images from PDF pages (auto-zipped if multi-page)' },
  { id: 'compress', label: 'Compress PDF', icon: '🗜️', desc: 'Reduce PDF file size using Ghostscript optimization engine' },
]

export default function App() {
  const [operation, setOperation] = useState('img2pdf')
  const [selectedFiles, setSelectedFiles] = useState([])
  const [compressLevel, setCompressLevel] = useState('ebook')
  const [dpi, setDpi] = useState('150')
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [statusMsg, setStatusMsg] = useState('')
  const [time, setTime] = useState('')

  // Windows state
  const [showMain, setShowMain] = useState(true)
  const [showLogs, setShowLogs] = useState(false)
  const [showAbout, setShowAbout] = useState(false)
  const [startMenuOpen, setStartMenuOpen] = useState(false)
  const [activeWindow, setActiveWindow] = useState('main')

  const fileInputRef = useRef(null)
  const pollingRef = useRef(null)

  // System clock
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
      const r = await fetch(`${API}/jobs?limit=30`)
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

  const handleFileChange = (e) => {
    if (e.target.files) {
      const fileList = Array.from(e.target.files)
      setSelectedFiles(fileList)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setStatusMsg('')

    if (!selectedFiles || selectedFiles.length === 0) {
      setError('ERROR: [NULL_INPUT] Please select file(s) to process.')
      return
    }

    setLoading(true)
    setStatusMsg('Uploading documents to Amazon S3...')

    try {
      const formData = new FormData()
      selectedFiles.forEach((f) => formData.append('files', f))
      formData.append('operation', operation)

      const options = {}
      if (operation === 'compress') options.compress_level = compressLevel
      if (operation === 'pdf2img') options.dpi = parseInt(dpi, 10) || 150
      formData.append('options', JSON.stringify(options))

      const r = await fetch(`${API}/jobs`, {
        method: 'POST',
        body: formData,
      })
      const resp = await r.json()
      if (!r.ok) {
        throw new Error(resp.detail || 'Processing task rejected.')
      }

      setSelectedFiles([])
      if (fileInputRef.current) fileInputRef.current.value = ''
      setStatusMsg(`Job dispatched to SQS queue: ${resp.job_id.substring(0, 8)}...`)
      fetchJobs()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const totalInputSize = selectedFiles.reduce((acc, f) => acc + f.size, 0)

  return (
    <div
      onClick={() => startMenuOpen && setStartMenuOpen(false)}
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        backgroundColor: '#008080',
      }}
    >
      {/* ── DESKTOP SHORTCUT ICONS ── */}
      <div
        style={{
          position: 'absolute',
          top: 16,
          left: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 20,
          zIndex: 5,
          userSelect: 'none',
        }}
        className="desktop-only"
      >
        <div
          onClick={() => { setShowMain(true); setActiveWindow('main'); }}
          style={{ width: 76, textAlign: 'center', cursor: 'pointer' }}
        >
          <div
            style={{
              width: 44,
              height: 44,
              margin: '0 auto 4px',
              background: '#c0c0c0',
              border: '2px solid #ffffff',
              borderRightColor: '#000000',
              borderBottomColor: '#000000',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 22,
            }}
          >
            📑
          </div>
          <span
            style={{
              fontSize: 11,
              color: '#fff',
              background: activeWindow === 'main' && showMain ? '#000080' : 'transparent',
              padding: '1px 3px',
              fontFamily: 'var(--font-retro)',
            }}
          >
            CloudDoc.exe
          </span>
        </div>

        <div
          onClick={() => { setShowLogs(true); setActiveWindow('logs'); }}
          style={{ width: 76, textAlign: 'center', cursor: 'pointer' }}
        >
          <div
            style={{
              width: 44,
              height: 44,
              margin: '0 auto 4px',
              background: '#c0c0c0',
              border: '2px solid #ffffff',
              borderRightColor: '#000000',
              borderBottomColor: '#000000',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 22,
            }}
          >
            🗄️
          </div>
          <span
            style={{
              fontSize: 11,
              color: '#fff',
              background: activeWindow === 'logs' && showLogs ? '#000080' : 'transparent',
              padding: '1px 3px',
              fontFamily: 'var(--font-retro)',
            }}
          >
            S3_Bucket
          </span>
        </div>

        <div
          onClick={() => { setShowAbout(true); setActiveWindow('about'); }}
          style={{ width: 76, textAlign: 'center', cursor: 'pointer' }}
        >
          <div
            style={{
              width: 44,
              height: 44,
              margin: '0 auto 4px',
              background: '#c0c0c0',
              border: '2px solid #ffffff',
              borderRightColor: '#000000',
              borderBottomColor: '#000000',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 22,
            }}
          >
            📋
          </div>
          <span
            style={{
              fontSize: 11,
              color: '#fff',
              background: activeWindow === 'about' && showAbout ? '#000080' : 'transparent',
              padding: '1px 3px',
              fontFamily: 'var(--font-retro)',
            }}
          >
            Architecture
          </span>
        </div>
      </div>

      {/* ── WORKSPACE WINDOWS AREA ── */}
      <div
        style={{
          flex: 1,
          padding: '16px 12px 64px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'flex-start',
          position: 'relative',
        }}
      >
        {/* ── MAIN WINDOW ── */}
        {showMain && (
          <div
            className="bevel-outset"
            onClick={() => setActiveWindow('main')}
            style={{
              width: '100%',
              maxWidth: 720,
              padding: 3,
              boxShadow: '4px 6px 0px rgba(0, 0, 0, 0.45)',
              zIndex: activeWindow === 'main' ? 20 : 10,
              marginBottom: 16,
            }}
          >
            {/* WINDOW TITLE BAR */}
            <div
              className="title-bar"
              style={{
                background: activeWindow === 'main' ? '#000080' : '#808080',
                color: '#ffffff',
                padding: '3px 4px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontWeight: 'bold',
                fontSize: 12,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span>📑</span>
                <span style={{ letterSpacing: '0.5px' }}>CLOUDDROP PDF PROCESSOR</span>
              </div>
              <div style={{ display: 'flex', gap: 3 }}>
                <button
                  onClick={(e) => { e.stopPropagation(); setShowMain(false); }}
                  className="retro-button"
                  style={{ width: 18, height: 16, fontSize: 10, padding: 0, lineHeight: 1 }}
                >
                  _
                </button>
                <button
                  className="retro-button"
                  style={{ width: 18, height: 16, fontSize: 10, padding: 0, lineHeight: 1 }}
                >
                  □
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); setShowMain(false); }}
                  className="retro-button"
                  style={{ width: 18, height: 16, fontSize: 10, padding: 0, lineHeight: 1, fontWeight: 'bold' }}
                >
                  ✕
                </button>
              </div>
            </div>

            {/* MAIN WINDOW BODY */}
            <div style={{ padding: '10px 10px 12px' }}>
              {/* OPERATION SELECTOR TABS (3 FEATURES ONLY) */}
              <div style={{ display: 'flex', gap: 2, marginBottom: -2, zIndex: 2, position: 'relative' }}>
                {OPERATIONS.map((op) => (
                  <button
                    key={op.id}
                    onClick={() => {
                      setOperation(op.id)
                      setSelectedFiles([])
                      if (fileInputRef.current) fileInputRef.current.value = ''
                    }}
                    style={{
                      padding: '5px 14px',
                      fontSize: 12,
                      fontFamily: 'var(--font-mono)',
                      background: operation === op.id ? '#c0c0c0' : '#a0a0a0',
                      borderTop: '2px solid #ffffff',
                      borderLeft: '2px solid #ffffff',
                      borderRight: '2px solid #000000',
                      borderBottom: operation === op.id ? 'none' : '2px solid #000000',
                      fontWeight: operation === op.id ? 'bold' : 'normal',
                      cursor: 'pointer',
                      outline: 'none',
                    }}
                  >
                    {op.icon} {op.label}
                  </button>
                ))}
              </div>

              {/* TAB CONTENT PANEL */}
              <div
                className="bevel-outset"
                style={{
                  padding: 14,
                  background: '#c0c0c0',
                  marginBottom: 12,
                }}
              >
                <form onSubmit={handleSubmit}>
                  <div style={{ fontSize: 11, color: '#333', marginBottom: 12 }}>
                    <strong>Task:</strong> {OPERATIONS.find((o) => o.id === operation)?.desc}
                  </div>

                  {/* FILE INPUT BOX */}
                  <div style={{ marginBottom: 14 }}>
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 'bold', marginBottom: 6 }}>
                      {operation === 'img2pdf' ? 'Select Image(s) (JPG, PNG, WEBP):' : 'Select PDF Document:'}
                    </label>
                    <div
                      className="bevel-inset"
                      style={{
                        padding: 10,
                        background: '#ffffff',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 8,
                      }}
                    >
                      <input
                        ref={fileInputRef}
                        type="file"
                        multiple={operation === 'img2pdf'}
                        accept={operation === 'img2pdf' ? 'image/png, image/jpeg, image/webp' : 'application/pdf'}
                        onChange={handleFileChange}
                        style={{ fontSize: 12 }}
                      />
                      {selectedFiles.length > 0 && (
                        <div style={{ fontSize: 11, color: '#000080' }}>
                          Selected {selectedFiles.length} file(s) ({formatBytes(totalInputSize)} total):
                          <ul style={{ margin: '4px 0 0 18px', padding: 0 }}>
                            {selectedFiles.map((f, i) => (
                              <li key={i}>{f.name} ({formatBytes(f.size)})</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* OPERATION SPECIFIC OPTIONS */}
                  {operation === 'compress' && (
                    <div style={{ marginBottom: 14 }}>
                      <label style={{ display: 'block', fontSize: 12, fontWeight: 'bold', marginBottom: 6 }}>
                        Compression Preset:
                      </label>
                      <select
                        value={compressLevel}
                        onChange={(e) => setCompressLevel(e.target.value)}
                        className="bevel-inset"
                        style={{ width: '100%', padding: '6px 8px', fontSize: 12, background: '#fff' }}
                      >
                        <option value="screen">Screen (72 DPI) - Maximum reduction, ideal for mobile/email</option>
                        <option value="ebook">eBook (150 DPI) - Standard web compression (Recommended)</option>
                        <option value="printer">Printer (300 DPI) - High quality reduction for printouts</option>
                      </select>
                    </div>
                  )}

                  {operation === 'pdf2img' && (
                    <div style={{ marginBottom: 14 }}>
                      <label style={{ display: 'block', fontSize: 12, fontWeight: 'bold', marginBottom: 6 }}>
                        Render Resolution:
                      </label>
                      <select
                        value={dpi}
                        onChange={(e) => setDpi(e.target.value)}
                        className="bevel-inset"
                        style={{ width: '100%', padding: '6px 8px', fontSize: 12, background: '#fff' }}
                      >
                        <option value="150">150 DPI (Standard Screen Quality - Fast)</option>
                        <option value="300">300 DPI (High Resolution Print Quality)</option>
                        <option value="72">72 DPI (Low Res / Fast Preview)</option>
                      </select>
                      <span style={{ fontSize: 10, color: '#555' }}>
                        Single page PDFs download directly as .PNG. Multi-page PDFs download as a .ZIP archive.
                      </span>
                    </div>
                  )}

                  {/* STATUS / ERROR NOTICES */}
                  {error && (
                    <div
                      className="bevel-inset"
                      style={{
                        padding: 8,
                        background: '#ffe0e0',
                        color: '#cc0000',
                        fontSize: 11,
                        marginBottom: 12,
                        fontWeight: 'bold',
                      }}
                    >
                      {error}
                    </div>
                  )}

                  {statusMsg && (
                    <div
                      className="bevel-inset"
                      style={{
                        padding: 8,
                        background: '#e0ffe0',
                        color: '#006600',
                        fontSize: 11,
                        marginBottom: 12,
                      }}
                    >
                      {statusMsg}
                    </div>
                  )}

                  {/* ACTION BUTTON */}
                  <button
                    type="submit"
                    disabled={loading || selectedFiles.length === 0}
                    className="retro-button"
                    style={{
                      width: '100%',
                      padding: '8px 16px',
                      fontSize: 13,
                      fontWeight: 'bold',
                      cursor: loading || selectedFiles.length === 0 ? 'not-allowed' : 'pointer',
                    }}
                  >
                    {loading ? 'PROCESSING VIA CLOUD WORKER...' : `EXECUTE ${operation.toUpperCase()} TASK`}
                  </button>
                </form>
              </div>

              {/* RECENT JOBS TABLE */}
              <div style={{ marginTop: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <span style={{ fontSize: 12, fontWeight: 'bold' }}>Active & Completed Cloud Jobs</span>
                  <span style={{ fontSize: 10, color: '#555' }}>Auto-refreshes every 3s</span>
                </div>

                <div
                  className="bevel-inset"
                  style={{
                    background: '#ffffff',
                    maxHeight: 240,
                    overflowY: 'auto',
                  }}
                >
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                    <thead>
                      <tr style={{ background: '#dcdcdc', borderBottom: '1px solid #999', textAlign: 'left' }}>
                        <th style={{ padding: '4px 8px' }}>File</th>
                        <th style={{ padding: '4px 8px' }}>Task</th>
                        <th style={{ padding: '4px 8px' }}>Size</th>
                        <th style={{ padding: '4px 8px' }}>Status</th>
                        <th style={{ padding: '4px 8px' }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {jobs.length === 0 ? (
                        <tr>
                          <td colSpan="5" style={{ padding: 16, textAlign: 'center', color: '#888' }}>
                            No jobs in RDS database yet. Submit a task above.
                          </td>
                        </tr>
                      ) : (
                        jobs.map((j) => {
                          const orig = j.original_size || 0
                          const res = j.result_size || 0
                          let sizeText = formatBytes(orig)
                          if (res > 0 && res !== orig) {
                            const diff = orig - res
                            const pct = Math.round((diff / orig) * 100)
                            sizeText = `${formatBytes(orig)} → ${formatBytes(res)} (${pct > 0 ? `-${pct}%` : `+${Math.abs(pct)}%`})`
                          }

                          return (
                            <tr key={j.job_id} style={{ borderBottom: '1px solid #eee' }}>
                              <td
                                style={{
                                  padding: '4px 8px',
                                  maxWidth: 180,
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  whiteSpace: 'nowrap',
                                }}
                                title={j.filename || j.job_id}
                              >
                                {j.filename || j.job_id.substring(0, 10)}
                              </td>
                              <td style={{ padding: '4px 8px', textTransform: 'uppercase', fontWeight: 'bold', fontSize: 10 }}>
                                {j.operation || 'process'}
                              </td>
                              <td style={{ padding: '4px 8px', fontSize: 10 }}>
                                {sizeText}
                              </td>
                              <td style={{ padding: '4px 8px' }}>
                                <span
                                  style={{
                                    padding: '1px 5px',
                                    fontSize: 9,
                                    fontWeight: 'bold',
                                    color: '#fff',
                                    background:
                                      j.status === 'complete'
                                        ? '#16a34a'
                                        : j.status === 'processing'
                                        ? '#d97706'
                                        : j.status === 'failed'
                                        ? '#dc2626'
                                        : '#2563eb',
                                  }}
                                >
                                  {j.status.toUpperCase()}
                                </span>
                              </td>
                              <td style={{ padding: '4px 8px' }}>
                                {j.status === 'complete' ? (
                                  <a
                                    href={`/api/download/${j.job_id}`}
                                    download={j.filename || 'document.pdf'}
                                    className="retro-button"
                                    style={{
                                      fontSize: 10,
                                      padding: '1px 6px',
                                      textDecoration: 'none',
                                      color: '#000',
                                      display: 'inline-block',
                                    }}
                                  >
                                    ⬇ Download
                                  </a>
                                ) : j.status === 'failed' ? (
                                  <span style={{ color: '#dc2626', fontSize: 10 }} title={j.error_msg}>
                                    Error
                                  </span>
                                ) : (
                                  <span style={{ color: '#888', fontSize: 10 }}>In Queue</span>
                                )}
                              </td>
                            </tr>
                          )
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── S3 BUCKET VIEWER WINDOW ── */}
        {showLogs && (
          <div
            className="bevel-outset"
            onClick={() => setActiveWindow('logs')}
            style={{
              width: '100%',
              maxWidth: 680,
              padding: 3,
              boxShadow: '4px 6px 0px rgba(0, 0, 0, 0.45)',
              zIndex: activeWindow === 'logs' ? 25 : 12,
              marginBottom: 16,
            }}
          >
            <div
              className="title-bar"
              style={{
                background: activeWindow === 'logs' ? '#000080' : '#808080',
                color: '#ffffff',
                padding: '3px 4px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontWeight: 'bold',
                fontSize: 12,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span>🗄️</span>
                <span>AMAZON S3 EXPLORER [clouddrop-media-23871]</span>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); setShowLogs(false); }}
                className="retro-button"
                style={{ width: 18, height: 16, fontSize: 10, padding: 0, lineHeight: 1, fontWeight: 'bold' }}
              >
                ✕
              </button>
            </div>
            <div style={{ padding: 8, background: '#c0c0c0' }}>
              <div
                className="bevel-inset"
                style={{
                  padding: 8,
                  background: '#ffffff',
                  fontSize: 11,
                  maxHeight: 280,
                  overflowY: 'auto',
                }}
              >
                <div style={{ marginBottom: 8, fontWeight: 'bold', color: '#000080' }}>
                  Bucket: clouddrop-media-23871 (Server-side AES256, 24-hr Expiration Lifecycle)
                </div>
                {jobs.map((j) => (
                  <div key={j.job_id} style={{ padding: '4px 0', borderBottom: '1px solid #eee' }}>
                    <div><strong>Key:</strong> processed/{j.job_id}/{j.filename || 'document.pdf'}</div>
                    <div style={{ color: '#555', fontSize: 10 }}>
                      Created: {formatDate(j.created_at)} | Size: {formatBytes(j.result_size || j.original_size)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── ABOUT WINDOW ── */}
        {showAbout && (
          <div
            className="bevel-outset"
            onClick={() => setActiveWindow('about')}
            style={{
              width: '100%',
              maxWidth: 540,
              padding: 3,
              boxShadow: '4px 6px 0px rgba(0, 0, 0, 0.45)',
              zIndex: activeWindow === 'about' ? 30 : 14,
              marginBottom: 16,
            }}
          >
            <div
              className="title-bar"
              style={{
                background: activeWindow === 'about' ? '#000080' : '#808080',
                color: '#ffffff',
                padding: '3px 4px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontWeight: 'bold',
                fontSize: 12,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span>📋</span>
                <span>ARCHITECTURE.TXT - Notepad</span>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); setShowAbout(false); }}
                className="retro-button"
                style={{ width: 18, height: 16, fontSize: 10, padding: 0, lineHeight: 1, fontWeight: 'bold' }}
              >
                ✕
              </button>
            </div>
            <div style={{ padding: 8, background: '#c0c0c0' }}>
              <div
                className="bevel-inset"
                style={{
                  padding: 12,
                  background: '#ffffff',
                  fontSize: 12,
                  lineHeight: 1.6,
                }}
              >
                <strong>CloudDrop Document Processing Pipeline</strong><br />
                • <strong>Features:</strong> Image to PDF, PDF to Image, PDF Compress<br />
                • <strong>Frontend:</strong> React 18, Vite (Static build served by Nginx)<br />
                • <strong>API Layer:</strong> FastAPI, Python 3.9 on Amazon EC2 (t3.micro)<br />
                • <strong>Queue:</strong> Amazon SQS (clouddrop-jobs) for decoupled async jobs<br />
                • <strong>Storage:</strong> Amazon S3 with 24-hr lifecycle & pre-signed download URLs<br />
                • <strong>Database:</strong> Amazon RDS PostgreSQL 15 in private subnets<br />
                • <strong>VPC:</strong> Custom 10.0.0.0/16 VPC with 4 subnets across 2 AZs<br />
                • <strong>Engines:</strong> Ghostscript 9.56 (compression), PyMuPDF & Pillow (image conversion)<br />
                • <strong>Alerts:</strong> Amazon SNS + CloudWatch idle auto-stop & $20 budget
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── START MENU ── */}
      {startMenuOpen && (
        <div
          className="bevel-outset"
          onClick={(e) => e.stopPropagation()}
          style={{
            position: 'fixed',
            bottom: 34,
            left: 2,
            width: 220,
            zIndex: 100,
            padding: 3,
            boxShadow: '3px 3px 0 #000',
          }}
        >
          <div
            style={{
              background: '#000080',
              color: '#ffffff',
              padding: '6px 8px',
              fontFamily: 'var(--font-retro)',
              fontSize: 12,
              fontWeight: 'bold',
              letterSpacing: 1,
              marginBottom: 4,
            }}
          >
            CloudDrop OS
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <button
              className="retro-button"
              style={{ textAlign: 'left', padding: '6px 10px', fontSize: 11 }}
              onClick={() => { setShowMain(true); setActiveWindow('main'); setStartMenuOpen(false); }}
            >
              📑 Open Document Tools
            </button>
            <button
              className="retro-button"
              style={{ textAlign: 'left', padding: '6px 10px', fontSize: 11 }}
              onClick={() => { setShowLogs(true); setActiveWindow('logs'); setStartMenuOpen(false); }}
            >
              🗄️ Browse S3 Storage
            </button>
            <button
              className="retro-button"
              style={{ textAlign: 'left', padding: '6px 10px', fontSize: 11 }}
              onClick={() => { setShowAbout(true); setActiveWindow('about'); setStartMenuOpen(false); }}
            >
              📋 Architecture Spec
            </button>
            <button
              className="retro-button"
              style={{ textAlign: 'left', padding: '6px 10px', fontSize: 11 }}
              onClick={() => { fetchJobs(); setStartMenuOpen(false); }}
            >
              🔄 Sync Database
            </button>
          </div>
        </div>
      )}

      {/* ── BOTTOM TASKBAR ── */}
      <div
        className="bevel-outset"
        style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          height: 32,
          padding: '2px 4px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          zIndex: 90,
          userSelect: 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {/* START BUTTON */}
          <button
            onClick={() => setStartMenuOpen(!startMenuOpen)}
            className={startMenuOpen ? 'bevel-inset' : 'bevel-outset'}
            style={{
              padding: '2px 8px',
              height: 24,
              fontSize: 11,
              fontFamily: 'var(--font-retro)',
              fontWeight: 'bold',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              cursor: 'pointer',
              background: '#c0c0c0',
            }}
          >
            <span>🏁</span> Start
          </button>

          {/* TASKBAR WINDOW TABS */}
          {showMain && (
            <button
              className={activeWindow === 'main' ? 'bevel-inset' : 'bevel-outset'}
              onClick={() => setActiveWindow('main')}
              style={{
                height: 24,
                padding: '2px 8px',
                fontSize: 11,
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                background: '#c0c0c0',
                fontWeight: activeWindow === 'main' ? 'bold' : 'normal',
                maxWidth: 160,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              <span>📑</span> CloudDoc.exe
            </button>
          )}

          {showLogs && (
            <button
              className={activeWindow === 'logs' ? 'bevel-inset' : 'bevel-outset'}
              onClick={() => setActiveWindow('logs')}
              style={{
                height: 24,
                padding: '2px 8px',
                fontSize: 11,
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                background: '#c0c0c0',
                fontWeight: activeWindow === 'logs' ? 'bold' : 'normal',
              }}
            >
              <span>🗄️</span> S3_Bucket
            </button>
          )}

          {showAbout && (
            <button
              className={activeWindow === 'about' ? 'bevel-inset' : 'bevel-outset'}
              onClick={() => setActiveWindow('about')}
              style={{
                height: 24,
                padding: '2px 8px',
                fontSize: 11,
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                background: '#c0c0c0',
                fontWeight: activeWindow === 'about' ? 'bold' : 'normal',
              }}
            >
              <span>📋</span> Architecture
            </button>
          )}
        </div>

        {/* SYSTEM TRAY WITH CLOCK */}
        <div
          className="bevel-inset"
          style={{
            height: 22,
            padding: '0 8px',
            fontSize: 11,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            background: '#ffffff',
          }}
        >
          <span>☁️</span>
          <span>{time}</span>
        </div>
      </div>
    </div>
  )
}

import React, { useState } from 'react'
import axios from 'axios'

export default function CaseUploader({ API_BASE }){
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [fecha, setFecha] = useState('')
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  async function handleSubmit(e){
    e.preventDefault()
    setLoading(true); setError(null); setResult(null)
    try{
      let res
      if(file){
        const fd = new FormData()
        fd.append('file', file)
        fd.append('title', title)
        if(fecha) fd.append('fecha', fecha)
        // if text provided, attach as well
        if(text) fd.append('text', text)
        res = await axios.post(`${API_BASE}/ingest_case`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      } else {
        const payload = { title, text }
        if(fecha) payload.fecha = fecha
        res = await axios.post(`${API_BASE}/ingest_case`, payload)
      }
      setResult(res.data)
      // notify other components a case was uploaded (so UI can refresh precedents)
      try{
        if (typeof window !== 'undefined' && window.dispatchEvent){
          window.dispatchEvent(new CustomEvent('case:uploaded', { detail: res.data }))
        }
      }catch(e){ console.warn('event dispatch failed', e) }
      setTitle(''); setText(''); setFecha('')
      setFile(null)
    }catch(err){
      console.error(err)
      setError(err.response && err.response.data ? err.response.data : String(err))
    }finally{
      setLoading(false)
    }
  }

  return (
    <div className="module-container">
      <div className="section-card">
        <div className="card-header">
          <h3>📁 Ingresar Caso / Precedente</h3>
          <p>Sube el texto del caso para que sea analizado y vinculado a artículos mencionados.</p>
        </div>
        <div className="card-body">
          <form onSubmit={handleSubmit}>
            <div className="form-row">
              <label>Título</label>
              <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Título del caso" />
            </div>
            <div className="form-row">
              <label>Fecha (opcional)</label>
              <input value={fecha} onChange={e => setFecha(e.target.value)} placeholder="YYYY-MM-DD" />
            </div>
            <div className="form-row">
              <label>Texto del caso</label>
              <textarea value={text} onChange={e => setText(e.target.value)} rows={10} placeholder="Pega aquí el texto del fallo o la URL..." />
            </div>
            <div className="form-row">
              <label>PDF (opcional)</label>
              <input type="file" accept="application/pdf" onChange={e => setFile(e.target.files[0])} />
              {file && <div className="file-info">Seleccionado: {file.name}</div>}
            </div>
            <div className="form-row">
              <button type="submit" disabled={loading}>{loading ? 'Guardando...' : 'Guardar caso'}</button>
            </div>
          </form>

          {result && (
            <div className="result-box">
              <strong>Guardado:</strong>
              <pre>{JSON.stringify(result, null, 2)}</pre>
            </div>
          )}

          {error && (
            <div className="error-box">Error: {JSON.stringify(error)}</div>
          )}
        </div>
      </div>
    </div>
  )
}

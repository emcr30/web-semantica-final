import React, { useState } from 'react'
import axios from 'axios'
import { Card, Form, Button, Alert, Spinner, Row, Col } from 'react-bootstrap'

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
        if(text) fd.append('text', text)
        res = await axios.post(`${API_BASE}/ingest_case`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      } else {
        const payload = { title, text }
        if(fecha) payload.fecha = fecha
        res = await axios.post(`${API_BASE}/ingest_case`, payload)
      }
      setResult(res.data)
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
    <div className="fade-in">
      <Card className="mb-4">
        <Card.Header>
          <Card.Title className="mb-0">Ingresar Caso o Precedente</Card.Title>
          <small className="text-white-50">Sube el texto del caso para análisis automático y vinculación a artículos</small>
        </Card.Header>
        <Card.Body>
          <Form onSubmit={handleSubmit}>
            <Form.Group className="mb-3">
              <Form.Label className="fw-bold">Título del Caso *</Form.Label>
              <Form.Control
                type="text"
                value={title}
                onChange={e => setTitle(e.target.value)}
                placeholder="Ej: CASACIÓN N.° 412-2022"
                required
              />
              <Form.Text className="text-muted">
                Identificador único del caso o precedente
              </Form.Text>
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label className="fw-bold">Fecha de Sentencia</Form.Label>
              <Form.Control
                type="date"
                value={fecha}
                onChange={e => setFecha(e.target.value)}
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label className="fw-bold">Texto del Caso *</Form.Label>
              <Form.Control
                as="textarea"
                rows={8}
                value={text}
                onChange={e => setText(e.target.value)}
                placeholder="Pega aquí el texto completo del fallo..."
                required
              />
              <Form.Text className="text-muted">
                Se analizará automáticamente para extraer artículos mencionados
              </Form.Text>
            </Form.Group>

            <Form.Group className="mb-4">
              <Form.Label className="fw-bold">PDF del Caso (Opcional)</Form.Label>
              <Form.Control
                type="file"
                accept="application/pdf"
                onChange={e => setFile(e.target.files[0])}
              />
              {file && (
                <Alert variant="info" className="mt-2 mb-0 small">
                  Archivo seleccionado: <strong>{file.name}</strong> ({(file.size / 1024).toFixed(2)} KB)
                </Alert>
              )}
            </Form.Group>

            <div className="d-flex gap-2">
              <Button
                variant="primary"
                type="submit"
                disabled={loading || !title || !text}
                size="lg"
              >
                {loading ? (
                  <>
                    <Spinner size="sm" animation="border" className="me-2" />
                    Guardando...
                  </>
                ) : (
                  'Guardar Caso'
                )}
              </Button>
            </div>
          </Form>

          {result && (
            <Alert variant="success" className="mt-4">
              <Alert.Heading>Caso guardado exitosamente</Alert.Heading>
              <hr />
              <p className="mb-0 small font-monospace">{JSON.stringify(result, null, 2)}</p>
            </Alert>
          )}

          {error && (
            <Alert variant="danger" className="mt-4">
              <Alert.Heading>Error al procesar</Alert.Heading>
              <p className="mb-0 small">{JSON.stringify(error)}</p>
            </Alert>
          )}
        </Card.Body>
      </Card>
    </div>
  )
}

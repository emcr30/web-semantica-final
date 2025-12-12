import React, { useState } from 'react'
import axios from 'axios'
import { Card, Form, Button, Alert, Spinner, Badge, ListGroup } from 'react-bootstrap'

const PdfUploader = ({ apiBase }) => {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [persist, setPersist] = useState(true)
  const [docId, setDocId] = useState('')

  function onFileChange(e){
    setFile(e.target.files[0])
    setResult(null)
    setError(null)
  }

  async function upload(){
    if(!file) return
    setLoading(true)
    setResult(null)
    setError(null)
    const form = new FormData()
    form.append('file', file)
    form.append('persist', persist ? '1' : '0')
    if(docId) form.append('doc_id', docId)
    try{
      const res = await axios.post(`${apiBase}/ingest_pdf`, form, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setResult(res.data)
    }catch(err){
      setError(err.response?.data || err.message)
    }finally{
      setLoading(false)
    }
  }

  return (
    <div className="fade-in">
      <Card className="mb-4">
        <Card.Header>
          <Card.Title className="mb-0">Subir y Analizar PDF</Card.Title>
          <small className="text-white-50">Carga un documento PDF para análisis automático con NLP</small>
        </Card.Header>
        <Card.Body>
          <Form.Group className="mb-3">
            <Form.Label className="fw-bold">Archivo PDF *</Form.Label>
            <Form.Control
              type="file"
              accept="application/pdf"
              onChange={onFileChange}
              disabled={loading}
            />
            {file && (
              <Alert variant="info" className="mt-2 mb-0 small">
                Archivo seleccionado: <strong>{file.name}</strong> ({(file.size / 1024 / 1024).toFixed(2)} MB)
              </Alert>
            )}
          </Form.Group>

          <Form.Group className="mb-3">
            <Form.Label className="fw-bold">ID del Documento (Opcional)</Form.Label>
            <Form.Control
              type="text"
              value={docId}
              onChange={e => setDocId(e.target.value)}
              placeholder="Ej: DOC_20251210_01"
              disabled={loading}
            />
            <Form.Text className="text-muted">
              Identificador único para referencias internas
            </Form.Text>
          </Form.Group>

          <Form.Group className="mb-4">
            <Form.Check
              type="checkbox"
              checked={persist}
              onChange={e => setPersist(e.target.checked)}
              label="Persistir en la Base de Conocimiento"
              disabled={loading}
            />
            <Form.Text className="text-muted d-block mt-2">
              Los datos extraídos se guardarán y estarán disponibles para futuras búsquedas
            </Form.Text>
          </Form.Group>

          <div className="d-flex gap-2">
            <Button
              variant="primary"
              onClick={upload}
              disabled={!file || loading}
              size="lg"
            >
              {loading ? (
                <>
                  <Spinner size="sm" animation="border" className="me-2" />
                  Procesando...
                </>
              ) : (
                'Subir y Analizar'
              )}
            </Button>
          </div>
        </Card.Body>
      </Card>

      {error && (
        <Alert variant="danger">
          <Alert.Heading>Error al procesar PDF</Alert.Heading>
          <p className="mb-0 small">{JSON.stringify(error)}</p>
        </Alert>
      )}

      {result && (
        <Card>
          <Card.Header>
            <Card.Title className="mb-0">Entidades Extraídas</Card.Title>
          </Card.Header>
          <Card.Body>
            {result.entities && (
              <>
                {result.entities.articles && result.entities.articles.length > 0 && (
                  <div className="mb-4">
                    <h6 className="mb-2">
                      Artículos <Badge bg="info">{result.entities.articles.length}</Badge>
                    </h6>
                    <ListGroup variant="flush">
                      {result.entities.articles.map((a, i) => (
                        <ListGroup.Item key={i} className="small">
                          {a}
                        </ListGroup.Item>
                      ))}
                    </ListGroup>
                  </div>
                )}

                {result.entities.laws && result.entities.laws.length > 0 && (
                  <div className="mb-4">
                    <h6 className="mb-2">
                      Leyes <Badge bg="info">{result.entities.laws.length}</Badge>
                    </h6>
                    <ListGroup variant="flush">
                      {result.entities.laws.map((l, i) => (
                        <ListGroup.Item key={i} className="small">
                          {l}
                        </ListGroup.Item>
                      ))}
                    </ListGroup>
                  </div>
                )}

                {result.entities.entities && result.entities.entities.length > 0 && (
                  <div className="mb-4">
                    <h6 className="mb-2">
                      Entidades Nombradas <Badge bg="info">{result.entities.entities.length}</Badge>
                    </h6>
                    <ListGroup variant="flush">
                      {result.entities.entities.map((en, idx) => (
                        <ListGroup.Item key={idx} className="small d-flex justify-content-between">
                          <span>{en.label}</span>
                          <Badge bg="secondary">{en.type}</Badge>
                        </ListGroup.Item>
                      ))}
                    </ListGroup>
                  </div>
                )}

                {result.entities.keywords && result.entities.keywords.length > 0 && (
                  <div className="mb-4">
                    <h6 className="mb-2">
                      Palabras Clave <Badge bg="info">{result.entities.keywords.length}</Badge>
                    </h6>
                    <div>
                      {result.entities.keywords.map((k, idx) => (
                        <Badge key={idx} bg="primary" className="me-2 mb-2">
                          {k}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </Card.Body>
        </Card>
      )}
    </div>
  )
}

export default PdfUploader

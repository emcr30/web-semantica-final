import React, { useState } from 'react';
import axios from 'axios';

const PdfUploader = ({ apiBase }) => {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [persist, setPersist] = useState(true);
  const [docId, setDocId] = useState('');

  function onFileChange(e){
    setFile(e.target.files[0]);
    setResult(null);
    setError(null);
  }

  async function upload(){
    if(!file) return;
    setLoading(true);
    setResult(null);
    setError(null);
    const form = new FormData();
    form.append('file', file);
    form.append('persist', persist ? '1' : '0');
    if(docId) form.append('doc_id', docId);
    try{
      const res = await axios.post(`${apiBase}/ingest_pdf`, form, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setResult(res.data);
    }catch(err){
      setError(err.response?.data || err.message);
    }finally{
      setLoading(false);
    }
  }

  return (
    <div className="module-container">
      <h2>Subir PDF / Analizar con NLP</h2>
      <div className="pdf-uploader">
        <input type="file" accept="application/pdf" onChange={onFileChange} />
        <button onClick={upload} disabled={!file || loading}>{loading? 'Procesando...':'Subir y analizar'}</button>
      </div>

        {error && <div className="error-box">Error: {JSON.stringify(error)}</div>}

        <div className="persist-controls">
          <label>
            <input type="checkbox" checked={persist} onChange={e=>setPersist(e.target.checked)} /> Persistir en la KB
          </label>
          <label style={{marginLeft:12}}>
            ID (opcional): <input type="text" value={docId} onChange={e=>setDocId(e.target.value)} placeholder="DOC_20251210_01" />
          </label>
        </div>

      {result && (
        <div className="result-box">
          <h3>Entidades extraídas</h3>
          <div className="entities">
            <strong>Articles:</strong>
            <ul>{(result.entities.articles||[]).map(a=> <li key={a}>{a}</li>)}</ul>
            <strong>Laws:</strong>
            <ul>{(result.entities.laws||[]).map(l=> <li key={l}>{l}</li>)}</ul>
            <strong>Entities:</strong>
            <ul>{(result.entities.entities||[]).map((en,idx)=> <li key={idx}>{en.label} ({en.type})</li>)}</ul>
            <strong>Keywords:</strong>
            <ul>{(result.entities.keywords||[]).map((k,idx)=> <li key={idx}>{k}</li>)}</ul>
          </div>
        </div>
      )}
    </div>
  )
}

export default PdfUploader;

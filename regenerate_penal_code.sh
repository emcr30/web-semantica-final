#!/bin/bash
# Regenerate Penal Code RDF Data
# Script for Unix/Linux/Mac

echo "Regenerating Penal Code RDF data..."
cd backend
python ../backend/ingest_penal_code.py
echo ""
echo "Done! Data saved to Ontologia/legal_working.ttl"

Activating stronger reasoning in GraphDB and using Pellet
===============================================

This document explains how to enable stronger reasoning for LegalOntoSystem and how to use Pellet for OWL-DL reasoning.

GraphDB built-in reasoning
-------------------------
GraphDB supports several rulesets and reasoning profiles. For many use-cases, enabling the OWL2-RL (or Owl-Horst) ruleset in the repository is sufficient and fast.

1) Enable ruleset in the repository (Workbench):
- Open GraphDB Workbench -> Repositories -> select your repository -> Settings.
- Under "Rulesets" choose one of: "OWL2-RL", "OWL-Horst" or "RDFS" depending on desired inference strength.
- Save settings and reindex the repository if needed.

2) Via REST API (example):
- If you have an admin user and want to change via API, you can PATCH repository settings. Replace placeholders.

  curl -u <user>:<pass> -X PATCH \
    -H "Content-Type: application/json" \
    -d '{"ruleset":"owl2-rl"}' \
    "<GRAPHDB_URL>/rest/repositories/<REPO>/settings"

- Note: endpoints may vary between GraphDB versions. Confirm the REST API docs for your GraphDB release.

Pellet (external OWL-DL reasoner)
---------------------------------
Pellet can be used externally to perform OWL-DL reasoning and produce inferred triples which can then be imported into GraphDB.

1) Install Pellet (Java required):
- Download Pellet: https://github.com/stardog-union/pellet (or use the distribution you prefer).
- Pellet can be run as a command-line tool or via its Java API.

2) Use Pellet to classify/infer and export inferred triples:
- Load your ontology and data TTL into Pellet (via its CLI or API).
- Run classification/realization to compute inferred axioms.
- Export inferred triples as TTL and then upload to GraphDB (either as a separate named graph or merged into the repository).

3) Example workflow (conceptual):
- Export working TTL from LegalOntoSystem: `Ontologia/legal_working.ttl`.
- Run Pellet to infer: `java -jar pellet.jar --reason Ontologia/legal_working.ttl --output inferred.ttl` (check actual Pellet CLI arguments for your distribution).
- Upload `inferred.ttl` to GraphDB (via Workbench import or `backend/graphdb_upload.py` helper).

Automating upload from LegalOntoSystem
-------------------------------------
- The repository includes `backend/graphdb_upload.py` which POSTs a TTL to the GraphDB statements endpoint. To use automated upload, create `backend/graphdb_config.json` with keys:
  {
    "graphdb_url": "http://localhost:7200",
    "repository": "my_repo",
    "username": "",
    "password": ""
  }

- If you want the server to attempt to enable a ruleset via REST you will need admin credentials and to call the appropriate PATCH/PUT endpoint (GraphDB versions differ). Use caution when automating repository-level changes.

Recommendations
---------------
- For production: enable OWL2-RL in GraphDB and rely on repository reasoning for many efficient inferences.
- For DL reasoning: use Pellet externally to produce inferred triples and import them into GraphDB as a separate graph (keeps provenance clear).
- Keep inferred triples in a separate named graph so you can recompute and update them without losing source data.

Need help?
----------
If you provide GraphDB admin URL and credentials (or allow me to run curl commands from here), I can attempt to set the ruleset programmatically and test an upload. Otherwise I can provide exact curl commands for your GraphDB version if you tell me its version (e.g. GraphDB 9.x, 8.x).

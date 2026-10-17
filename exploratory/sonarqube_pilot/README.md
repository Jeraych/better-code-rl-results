# SonarQube research pilot

This directory contains the reproducible SonarQube comparison described in
`RESULTS.md`. It scans source text only and never executes generated candidates.

## Reproduce locally

Prerequisites are Docker Desktop and Python 3.9 or newer. Use a dedicated branch
and virtual environment.

```powershell
docker run -d --name softeng700-sonarqube-pilot `
  -e SONAR_ES_BOOTSTRAP_CHECKS_DISABLE=true -p 9000:9000 `
  sonarqube@sha256:d4899d380ad9d7b63ebaa751e047f5a4f064f8902cdf7c1a3c3c96f7d71600ed

python -m venv ..\..\..\tmp\sonarqube_pilot_venv
..\..\..\tmp\sonarqube_pilot_venv\Scripts\python.exe -m pip install `
  --requirement requirements-pilot.txt
python prepare_dataset.py
python prepare_extension.py
```

Create a temporary user token in the local SonarQube UI, place it only in the
current process environment, and run:

```powershell
$env:SONAR_TOKEN = "temporary-local-token"
$env:SONAR_HOST_URL = "http://localhost:9000"
..\..\..\tmp\sonarqube_pilot_venv\Scripts\pysonar.exe `
  --sonar-qualitygate-wait --sonar-qualitygate-timeout 300
Remove-Item Env:SONAR_TOKEN
```

Run the unchanged scan twice before adding the exploratory extension. For the
extension scan, pass `--sonar-sources dataset,extension`. Export the API issue
responses to the filenames used by `summarize_results.py`, then regenerate the
compact tables with:

```powershell
python summarize_results.py
```

The generated source directories and scanner cache are intentionally ignored;
the manifests, source generators, raw API exports, and compact results preserve
the evidence without duplicating generated programs in Git.

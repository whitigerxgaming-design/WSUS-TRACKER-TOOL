Set-Location $PSScriptRoot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Write-Host "done - run: python wst.py"

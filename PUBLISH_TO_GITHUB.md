# Publish this source folder to GitHub

Do not run these commands from the old directory containing your private workspace. Work in this newly extracted repository folder. No GitHub repository has been created for you.

## Before publishing

Create an empty repository in your GitHub account. Choose the visibility required by your instructor; use private visibility while preparing, and give the examiner access. Do not initialize the remote with another README, license or .gitignore. Review any organizational/account restrictions before uploading.

Run local unit tests and inspect the source tree. Add your reviewed evidence and final student-authored report first when ready. Do not copy the private workspace into this folder.

```powershell
& {
    $ErrorActionPreference = "Stop"
    if (-not (Test-Path .\lab.py)) { throw "Open the extracted repository folder first." }
    python -m unittest -v test_lab test_recovery test_mining_permissions test_submission_tools
    if ($LASTEXITCODE -ne 0) { throw "Tests failed." }
    python .\tools\check_repository.py
    if ($LASTEXITCODE -ne 0) { throw "Publication guard failed." }
    git init -b main
    if ($LASTEXITCODE -ne 0) { throw "Git initialization failed." }
    git add .
    if ($LASTEXITCODE -ne 0) { throw "Staging failed." }
    python .\tools\check_repository.py --staged
    if ($LASTEXITCODE -ne 0) { throw "Review staged files before proceeding." }
    git diff --cached --stat
}
```

Inspect `git status` and the staged files. The guard checks conventional credential patterns and runtime file names; it cannot guarantee safety and does not inspect pixels in screenshots or prose inside PDFs. `.gitignore` does not remove secrets already tracked in an existing repository.

Then commit and push to your own empty repository:

```powershell
& {
    $ErrorActionPreference = "Stop"
    $Remote = Read-Host "Paste your empty GitHub repository HTTPS URL"
    if ($Remote -notmatch '^https://github\.com/[^/\s]+/[^/\s]+/?$') {
        throw "Expected an HTTPS GitHub repository URL without credentials."
    }
    git commit -m "Add MultiChain fake-media implementation and documentation"
    if ($LASTEXITCODE -ne 0) { throw "Commit failed. Check Git user.name and user.email configuration." }
    git remote add origin "$Remote"
    if ($LASTEXITCODE -ne 0) { throw "Remote already exists or is invalid. Inspect git remote -v; do not force-push." }
    git push -u origin main
    if ($LASTEXITCODE -ne 0) { throw "Push failed. Complete GitHub authentication and retry only the push." }
}
```

Use your normal approved GitHub authentication; never put a token in the URL or source files. Open the repository in a browser and verify that source code, paper, instructions and report are accessible. The Actions workflow tests Python code only; green CI does not prove a native blockchain benchmark.

Record the real URL and commit hash in your final report. `git rev-parse HEAD` prints the commit hash. For a later evidence/report update, review, stage, run the publication guard, commit and push again; do not reinitialize or force-push.

Source: GitHub Docs, "Adding locally hosted code to GitHub":
https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github

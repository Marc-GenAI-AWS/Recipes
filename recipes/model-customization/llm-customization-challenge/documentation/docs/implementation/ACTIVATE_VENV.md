# Quick Reference: Activating Virtual Environment

## Windows PowerShell

```powershell
.\venv\Scripts\Activate.ps1
```

## Windows Command Prompt

```cmd
.\venv\Scripts\activate.bat
```

## Verification

After activation, you should see `(venv)` prefix in your prompt:

```
(venv) PS C:\path\to\project>
```

Verify you're using the correct Python:

```powershell
python --version
# Should show: Python 3.11.9
```

## Deactivation

When done working:

```powershell
deactivate
```

## Troubleshooting

If you get an execution policy error in PowerShell:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then try activating again.

---

For detailed setup instructions, see [SETUP.md](SETUP.md)

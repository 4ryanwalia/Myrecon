# Understand a verdict in 30 seconds

From the repository root, run:

```bash
python examples/offline_demo.py
python examples/offline_demo.py --json
```

Python's standard library is enough. No package installation, account, API key, or network connection is required. The script also works when launched from another directory.

The [fixture](sample_verdicts.json) contains four fictional platforms: one positive account response, one explicit missing-user response, a sign-in wall, and a timeout. The last two stay `unknown`. A successful HTTP status alone cannot establish that an account exists.

This is an educational illustration of the verdict contract. It does not invoke the lookup engine, validate a provider, measure accuracy, or identify a real person. JSON includes `synthetic: true` so exported examples retain their sample label.

For a real lookup, install the backend requirements and run `python myrecon.py username yourhandle` using a handle you own or have permission to investigate. Provider responses may change and require verification at the source.

# Contributing

Bug reports and pull requests are welcome. Contributions are accepted under the project's license,
AGPL-3.0-or-later.

- Server: `pip install -r requirements-dev.txt && pytest`
- Client: `cd client && npm ci && npm test`
- Game rules live in `rules.py` / `variants.py`; the server decides what is legal. Add a test for any rule change.
- Don't add inline scripts or styles; the Content-Security-Policy forbids them.
- Python dependencies: edit `requirements.in` and regenerate `requirements.txt` (see the README).

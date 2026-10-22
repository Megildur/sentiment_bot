"""Code rules from AGENTS.md that a search can check.

- No f-string reuses its own quote inside a replacement field: Python 3.12 allows
  f"{x["key"]}", but 3.10 and 3.11 (which the host may run) can't parse it.
- No `match` statements.
- Sentiment's permissions are read only in Source/Utils/Permissions.py.
- No plain `content=` replies and no embeds: Components v2 only.

    venv\\Scripts\\python.exe scratch\\check_code_rules.py
"""
import ast
import glob
import io
import re
import sys
import tokenize

bad = []
files = glob.glob("Source/**/*.py", recursive=True) + glob.glob("*.py")
for path in files:
    with open(path, encoding="utf-8") as f:
        source = f.read()
    norm = path.replace("\\", "/")

    stack = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.FSTRING_START:
            quote = tok.string.lstrip("rRfFbB")[:1]
            if stack and quote == stack[-1]:
                bad.append(f"{norm}:{tok.start[0]} f-string reuses its quote")
            stack.append(quote)
        elif tok.type == tokenize.FSTRING_END:
            stack.pop()
        elif tok.type == tokenize.STRING and stack:
            if tok.string.lstrip("rRbBuU")[:1] == stack[-1]:
                bad.append(f"{norm}:{tok.start[0]} f-string reuses its quote")

    for node in ast.walk(ast.parse(source)):
        if type(node).__name__ == "Match":
            bad.append(f"{norm}:{node.lineno} match statement")

    for number, line in enumerate(source.splitlines(), 1):
        code = line.split("#", 1)[0]
        if norm != "Source/Utils/Permissions.py" and re.search(r"guild_permissions|permissions_for\(", code):
            bad.append(f"{norm}:{number} reads permissions outside Utils/Permissions.py")
        if re.search(r"discord\.Embed\b|\bembed=", code):
            bad.append(f"{norm}:{number} uses an embed")
        if re.search(r"(send_message|followup\.send|edit_message)\(\s*content=|(send_message|followup\.send)\(\s*[\"f]", code) and norm != "Source/Quicksync.py":
            bad.append(f"{norm}:{number} plain-text reply")

print("\n".join(bad) or "OK")
sys.exit(1 if bad else 0)

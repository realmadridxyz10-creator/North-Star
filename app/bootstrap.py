from pathlib import Path

# Bootstrap the governed DEV-006 runtime while applying tightly scoped
# runtime-compatibility corrections discovered during external UAT.
main_path = Path(__file__).with_name("main.py")
source = main_path.read_text(encoding="utf-8")

# 1) Prevent Python f-string parsing of JavaScript ${...} expressions in the
# account-page HTML while preserving the plan_cards interpolation.
account_marker = "    body=f'''<main id=\"main\"><section class=\"module-hero\"><div class=\"shell\"><div class=\"eyebrow\">Identity · Commerce · Access</div>"
account_replacement = "    body='''<main id=\"main\"><section class=\"module-hero\"><div class=\"shell\"><div class=\"eyebrow\">Identity · Commerce · Access</div>"
if account_marker not in source:
    raise RuntimeError("DEV-006 account-page marker not found; refusing uncontrolled source transformation")
source = source.replace(account_marker, account_replacement, 1)

account_end = "refresh();</script>'''\n    return layout('Account',body)"
account_end_replacement = "refresh();</script>'''.replace('{plan_cards}',plan_cards)\n    return layout('Account',body)"
if account_end not in source:
    raise RuntimeError("DEV-006 account-page end marker not found; refusing uncontrolled source transformation")
source = source.replace(account_end, account_end_replacement, 1)

# 2) External UAT found that entitlements has 8 columns while the insert used
# 9 placeholders. Keep the existing 8 supplied values and align placeholders.
entitlement_insert = "INSERT OR IGNORE INTO entitlements VALUES(?,?,?,?,?,?,?,?,?)"
entitlement_insert_fixed = "INSERT OR IGNORE INTO entitlements VALUES(?,?,?,?,?,?,?,?)"
if entitlement_insert not in source:
    raise RuntimeError("DEV-006 entitlement insert marker not found; refusing uncontrolled source transformation")
source = source.replace(entitlement_insert, entitlement_insert_fixed, 1)

namespace = {
    "__name__": "app.main_runtime",
    "__file__": str(main_path),
    "__package__": "app",
}
exec(compile(source, str(main_path), "exec"), namespace)
app = namespace["app"]

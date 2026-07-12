import json

with open("/home/du/exports/1508_export.blueprint") as f:
    bp = json.load(f)

bp["Model"]["Id"] = 1516
bp["Model"]["Name"] = "CONTROL reimport 1508 unchanged"

with open("/home/du/tests/1516_control_1508_unchanged.blueprint", "w") as f:
    json.dump(bp, f, separators=(',', ':'))

print("wrote /home/du/tests/1516_control_1508_unchanged.blueprint")

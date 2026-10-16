"""Manual check of the fallback provider: real headlines, no Gemini, nothing is sent or saved."""
import os
import time

os.environ["FORCE_FALLBACK"] = "1"
import analyze  # noqa: E402
import collect  # noqa: E402

hl = collect.collect()
print("headlines:", len(hl), flush=True)
t0 = time.time()
out = analyze.analyze(hl)
print("TOTAL %.0fs" % (time.time() - t0))
print("summary:", out.get("summary"))
for e in out.get("events", [])[:6]:
    print(" -", e.get("title"), "| sev", e.get("severity"), "| winners", [w.get("ticker") for w in e.get("winners", [])][:4],
          "| horizons", list((e.get("horizons") or {}).keys()))
print("events:", len(out.get("events", [])), "| regions:", len(out.get("regions_to_watch", [])))

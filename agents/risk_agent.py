#!/usr/bin/env python3
"""agents/risk_agent.py — risk-detektor (före leverans):
copyright / defamation / os­tödda påståenden / copycat.

Returnerar top-level status: GO | REVIEW | HOLD.
"""
import os, json

def run(factcheck_report, licensing_manifest, project_dir):
    risks = []
    yt_assets = 0
    if not factcheck_report.get("safe", False):
        if factcheck_report.get("rewritten"):
            pass  # fixade via LLM
        else:
            risks.append({"severity": "high", "type": "unsupported_assertions",
                          "detail": str(factcheck_report.get("pending_manual", True))})
    rev = [a for a in licensing_manifest if a.get("status") == "review"]
    if len(rev) >= 3 and not any(r["type"] == "copyright_fairuse" for r in risks):
        risks.append({"severity": "medium", "type": "copyright_review",
                      "detail": f"{len(rev)} assets kräver licensbeslut (fair use)"})
    for a in licensing_manifest:
        tag = (a.get("license") or "").lower()
        if a.get("type") == "clip" or ("youtube" in tag):
            yt_assets += 1
            risks.append({"severity": "medium", "type": "copyright_fairuse",
                          "detail": f"{a.get('file','')} — YouTube-material; "
                                    "transformation krävs för reused-content-policy"})
    if yt_assets >= 3:
        risks.append({"severity": "medium", "type": "reused_content",
                      "detail": f"{yt_assets} klipp från YouTube — risk för "
                                "reused-content-strike om inte transformativt"})
    blocked = [a for a in licensing_manifest if a.get("tier", 9) >= 5]
    if blocked:
        risks.append({"severity": "high", "type": "copyright_blocked",
                      "detail": f"{len(blocked)} assets tier>=5 (ej publiceringsbara)"})
    # defamation/advertiser: markera allegationer som "måste vara tydligt märkta"
    fc_blocks = factcheck_report.get("blocks", [])
    if factcheck_report.get("safe") and any(
            "alleg" in str(b.get("flags", "")).lower() for b in fc_blocks):
        risks.append({"severity": "medium", "type": "defamation",
                      "detail": "allegationer kvar i manus — verifiera "
                                "'reportedly/alleging'-formulering och källa"})
    if not factcheck_report.get("safe", False) and not factcheck_report.get("rewritten"):
        severity = "high"
    elif risks and any(r["severity"] == "high" for r in risks):
        severity = "high"
    elif len([r for r in risks if r["type"] in ("copyright_fairuse",
                                                "reused_content",
                                                "defamation")]) >= 2:
        severity = "medium"
    elif risks:
        severity = "medium"
    else:
        severity = "low"
    status = "HOLD" if severity == "high" else ("REVIEW" if severity == "medium" else "GO")
    report = {"status": status, "severity": severity, "risks": risks}
    with open(os.path.join(project_dir, "risk.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    return report

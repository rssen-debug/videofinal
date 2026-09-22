#!/usr/bin/env python3
"""engine/retry.py — självläkande körnings-lager (max N försök, diagnos -> fix -> retry).

Används av sunny_auto runt: TTS, footage, grafik, render, QC.
Fixarna postas som händelser i projects/<slug>/run_report.json.
"""
import os, json, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class RetryBudget:
    def __init__(self, limit=3):
        self.limit = limit

def run_with_retry(name, fn, max_retries=3, diagnose_fix=None, log=None):
    """fn() -> resultat. Vid undantag: diagnose_fix(exc, attempt) får chansen
    att åtgärda; därefter retry. Max max_retries ekstra försök.
    Returnerar resultatet eller RAISAR sista felet."""
    last = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            last = exc
            if log is not None:
                log.append({"stage": name, "attempt": attempt,
                            "error": str(exc)[:300]})
            if attempt < max_retries and diagnose_fix:
                try:
                    action = diagnose_fix(exc, attempt)
                    if log is not None and action:
                        log[-1]["fix"] = str(action)[:300]
                except Exception:
                    pass
            time.sleep(1.0 + attempt)
    raise last

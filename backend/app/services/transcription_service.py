from __future__ import annotations


def merge_transcriptions(mathpix_json: dict | None, azure_json: dict | None, openai_json: dict | None) -> dict:
    # Phase 2: implement robust fusion + traceability
    return {
        "status": "not_implemented",
        "inputs_present": {
            "mathpix": bool(mathpix_json),
            "azure": bool(azure_json),
            "openai": bool(openai_json),
        },
    }

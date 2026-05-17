"""
ECG Analysis — sample MCP plugin server.

This is an example of what a third-party cardiac AI vendor would ship.
Drop this file in plugins/, set KLINIKA_MCP_SERVERS=plugins/ecg_server.py,
and Klinika discovers analyze_ecg automatically at startup.

In production this would call a local AI analysis engine.
Here it returns realistic mock output for demonstration purposes.
"""

from fastmcp import FastMCP

mcp = FastMCP("ECG Analysis")


@mcp.tool()
def analyze_ecg(patient_name: str) -> str:
    """Analyze ECG recording for cardiac arrhythmias and structural findings.

    Returns a structured ECG interpretation report including rhythm analysis,
    rate, intervals, and clinical recommendations.
    """
    return (
        f"ECG Analysis Report — {patient_name}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Rhythm:         Irregular. No distinct P waves. Variable RR intervals.\n"
        "Interpretation: Consistent with paroxysmal atrial fibrillation (AF).\n"
        "Ventricular rate: 88 bpm  |  QRS duration: 98 ms (normal)\n"
        "ST changes:     None.  QTc: 412 ms (normal).\n"
        "Axis:           Normal (-15°).\n"
        "\n"
        "Clinical recommendation:\n"
        "  • Anticoagulation assessment — calculate CHA₂DS₂-VASc score\n"
        "  • Rate control achieved (target <110 bpm at rest met)\n"
        "  • Consider rhythm control strategy given NYHA IV status\n"
        "  • Follow-up Holter monitor if paroxysmal episodes suspected\n"
    )


if __name__ == "__main__":
    mcp.run()

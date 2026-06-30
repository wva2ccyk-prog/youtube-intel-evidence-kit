# Video Analysis Request Template

Use this template when requesting a video analysis through the MCP handoff layer.

## Topic

```
topic_id: synthetic_opinion_terrain_demo_v1
```

## Overlay Groups

| Group ID | Split Axis | Claim Count |
|----------|------------|-------------|
| overlay_SYNTH_CG0001_access_and_scope | access_and_scope | 3 |
| overlay_SYNTH_CG0002_cost_and_burden | cost_and_burden | 4 |
| overlay_SYNTH_CG0003_institutional_trust | institutional_trust | 3 |
| overlay_SYNTH_CG0004_implementation_risk | implementation_risk | 5 |

## Axes

Each overlay group covers a different opinion terrain axis:

- **access_and_scope**: Who can access what, and the scope of claims
- **cost_and_burden**: Financial and operational costs discussed
- **institutional_trust**: Trust in institutions, sources, and systems
- **implementation_risk**: Risks in implementing discussed proposals

## Limitations

```
synthetic_fixture_only
caption_fragment_claim_risk
not truth-ranked
not fact-checked
```

## Expected Output Format

The MCP handoff layer returns JSON with:

- `ok`: boolean indicating success
- Overlay-specific data (summary, groups, detail, limitations)
- `limitations_display`: Always-present limitations list
- `policy_display`: Always-present policy block

## Notes

- This is a synthetic demo. No real video IDs are used.
- The system is caption-first. Audio/video/OCR escalation is need-gated.
- No truth judgments or fact checks are performed.
- All claims are opinion terrain, not verified facts.

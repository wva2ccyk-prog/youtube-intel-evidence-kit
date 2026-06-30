# Cost Routing Matrix

The central product is a cross-video `TopicCollection`. Cost routing controls which selected videos become reliable enough to enter that collection and which claim groups deserve additional evidence work.

| Situation | Default route | Reason |
|---|---|---|
| Single video, low factual density | Do not escalate | Built-in video chat or a cheap summary is enough |
| Selected video with useful claims | Build residual package | Needed as input for `VideoKnowledgeRecord` |
| Multiple selected videos on same topic | Build `TopicCollection` | Opinion terrain requires cross-video grouping |
| Repeated claim across videos | Preserve as repeated group | Repetition is a terrain signal, not proof |
| Claim group contains support and caution | Mark disagreement point | Operator judgment or source verification may be needed |
| Single-source strong claim | Mark outlier | Do not promote without follow-up |
| Caption quality is suspect | Consider bounded ASR | Only if the claim matters |
| Screen table/map/chart carries evidence | Consider bounded OCR/vision | Only for the relevant timestamp range |
| Speaker identity changes meaning | Consider speaker check | Only for the affected segment |
| High-risk claim lacks external support | Consider source verification | Keep video-internal until verified |
| Side remark may matter but is weak | Preserve as residual candidate | Useful skim layer, not a conclusion |

## Rule

Do not spend expensive processing by default. Spend only when a specific claim group, disagreement, outlier, or modality gap justifies it.

## Additional Gate Rules

| Situation | Default route | Reason |
|---|---|---|
| Claim repeats but all instances come from one speaker/channel | Preserve, but mark low source diversity | Repetition is not independent corroboration |
| Disagreement group affects legal/medical/financial/political action | Add external verification gate | Topic terrain is not advice |
| Caption-only group has missing speaker attribution | Speaker check only for affected segment | Do not diarize whole video by default |
| Claim depends on a visible table, map, slide, chart, or dashboard | OCR/vision only for referenced timestamp range | Avoid blanket vision cost |
| Claim is outlier and high-stakes | Strong model review and source verification gate | Single-source high-stakes claims should not be promoted |
| Topic is too broad to form coherent claim groups | Stop and narrow topic scope | Prevent broad scraping and unusable terrain |

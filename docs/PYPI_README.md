# YouTube Intel Evidence Kit

`youtube-intel-evidence-kit` is an alpha, dependency-free Python toolkit for packaging operator-admitted YouTube transcript evidence into reusable single-video records and cross-video opinion-terrain artifacts.

It does **not** download media, scrape YouTube, certify truth, or provide medical, financial, legal, investment, or political advice. The bundled demos use synthetic fixtures only.

## Install

```bash
python -m pip install youtube-intel-evidence-kit==0.1.0
```

Python 3.10 or newer is required.

## Quick start

```bash
youtube-intel doctor
youtube-intel topic-demo --out outputs/topic_demo
youtube-intel single-video-demo --out outputs/single_video
```

The topic demo produces reusable `VideoKnowledgeRecord` and `TopicCollection` artifacts with claim groups, disagreement candidates, outliers, speakers, timestamps, evidence coordinates, and modality gaps.

## Main commands

- `youtube-intel doctor` — verify installed-package health and fixture availability.
- `youtube-intel topic-demo` — run the synthetic cross-video opinion-terrain flow.
- `youtube-intel single-video-demo` — run the synthetic residual package and handoff flow.
- `youtube-intel package` — build a residual package from operator-admitted segment JSON.
- `youtube-intel worth` — create an analysis-worth cost gate.
- `youtube-intel single-video-handoff` — create a validated AI handoff bundle.
- `youtube-intel topic-mcp-stdio` — expose a read-only TopicCollection JSON-RPC stdio facade.

## Reliability boundaries

- Invalid or incoherent package, timestamp, schema, grouping, and handoff inputs fail closed.
- Source claims, evidence records, and trace rows preserve exact identity and provenance contracts.
- Installed wheels include byte-for-byte checked synthetic fixtures.
- Korean high-risk marker matching avoids generic capacity and substring collisions.
- Hidden-information aside detection requires explicit private evidence, direct observation, or cross-category signal combinations.

## Development

```bash
git clone https://github.com/wva2ccyk-prog/youtube-intel-evidence-kit.git
cd youtube-intel-evidence-kit
python -m pip install -e ".[dev]"
python -m pytest -W error -q -p no:cacheprovider
python -m youtube_mcp_handoff.smoke
```

## Project links

- Source and documentation: https://github.com/wva2ccyk-prog/youtube-intel-evidence-kit
- Issues: https://github.com/wva2ccyk-prog/youtube-intel-evidence-kit/issues
- Changelog: https://github.com/wva2ccyk-prog/youtube-intel-evidence-kit/blob/main/CHANGELOG.md

## License

MIT

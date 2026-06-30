# Review Brief for GPT Pro

This repository is not a YouTube summarizer.

Please do not evaluate it as a single-video summarizer or transcript summarizer. The core question is whether the package is on a credible path toward cross-video `TopicCollection` / opinion-terrain synthesis.

The final objective is to turn multiple YouTube videos on a topic into reusable `VideoKnowledgeRecord` and `TopicCollection` artifacts that show repeated claims, disagreement points, outliers, source videos, speakers, timestamps, evidence coordinates, and modality gaps. Single-video evidence packets and analysis-worth decisions are input layers, not the final product.

Please review the repository with these questions:

1. Does the public package make the final objective clear: cross-video opinion terrain, not generic summarization?
2. Is the `youtube-intel topic-demo` flow enough to show `VideoKnowledgeRecord -> TopicCollection -> topic terrain`?
3. Is the older `youtube-intel demo` correctly positioned as a single-video input layer and cost gate?
4. Does the package overclaim MCP support, or is the MCP-ready/read-only handoff facade described accurately?
5. Are privacy, synthetic-only boundaries, and public-release safety checks sufficient?
6. Are Korean/English YouTube markers and cost-routing rules enough for the intended use case?
7. Are repeated claims, disagreements, outliers, timestamps, speakers, and evidence coordinates represented clearly enough?
8. What should be deleted, renamed, or moved before public release?
9. Are tests covering the operator flow, topic demo, answer guard, overlay schema, and leak scan?
10. Which open-source components or patterns could be used as parts, not as the product direction?

Do not score it by summary smoothness. Score it by whether it can help an operator reduce source-video watching time while preserving claim terrain and evidence coordinates for a YouTube-heavy topic.

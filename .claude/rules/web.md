---
paths:
  - "web/**"
---

# Web rules

- API access goes only through the generated client in `web/src/api/`. No hand-written fetch calls or hand-written API types.
- The map renders only through `MapRenderer`. Nothing else draws map elements.
- A hypothesis always shows its label, on the map and in the evidence panel.
- Never write transcript text or quotes to the console or to any monitoring tool.

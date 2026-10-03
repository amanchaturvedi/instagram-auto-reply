# AI Response Schema

AI analyzers return structured JSON objects. The browser never needs to parse model-generated Markdown.

## Account analysis
```json
{
  "summary": "string",
  "what_changed": [{"title": "string", "detail": "string"}],
  "patterns": [{"title": "string", "detail": "string", "sample_size": 0}],
  "possible_causes": [{"title": "string", "detail": "string"}],
  "experiments": [{"test": "string", "why": "string", "metric": "string"}],
  "metrics_to_monitor": ["string"]
}
```

## Reel analysis
```json
{
  "summary": "string",
  "working": [{"title": "string", "detail": "string"}],
  "possible_weaknesses": [{"title": "string", "detail": "string"}],
  "experiments": [{"test": "string", "why": "string", "metric": "string"}],
  "metrics_to_monitor": ["string"]
}
```

## Chat
```json
{
  "summary": "string",
  "observations": [{"title": "string", "detail": "string"}],
  "hypotheses": [{"title": "string", "detail": "string"}],
  "experiments": [{"test": "string", "why": "string", "metric": "string"}]
}
```

Python validates required fields and array types before returning the response to the UI. Invalid model output results in a controlled API error instead of displaying raw model text.
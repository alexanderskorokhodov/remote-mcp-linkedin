# Bridge Protocol

The server and bridge communicate over a WebSocket connection initiated by the
bridge.

Default URL:

```text
ws://127.0.0.1:8765/bridge
```

Every message includes:

```json
{
  "protocol_version": "0.1"
}
```

## Authentication

The first bridge message must be `bridge.hello`:

```json
{
  "type": "bridge.hello",
  "protocol_version": "0.1",
  "bridge_id": "default",
  "token": "shared-token"
}
```

The server replies:

```json
{
  "type": "server.ack",
  "protocol_version": "0.1",
  "accepted": true,
  "message": "bridge authenticated"
}
```

## Commands

v0.1 allows these read-only commands:

- `profile.get`
- `network.search`

### `profile.get`

```json
{
  "type": "command",
  "protocol_version": "0.1",
  "command_id": "uuid",
  "command": "profile.get",
  "payload": {
    "profile_url": "https://www.linkedin.com/in/example/",
    "username": null,
    "sections": ["top_card", "about", "experience", "education", "skills"],
    "max_scrolls": 10
  }
}
```

The target must provide `profile_url` or `username`.

Allowed sections:

- `top_card`
- `about`
- `experience`
- `education`
- `skills`
- `certifications`
- `projects`
- `languages`
- `contact_info`
- `posts`

When `posts` is requested, the Patchright bridge reads the profile activity URL:

```text
https://www.linkedin.com/in/{username}/recent-activity/all/
```

### `network.search`

```json
{
  "type": "command",
  "protocol_version": "0.1",
  "command_id": "uuid",
  "command": "network.search",
  "payload": {
    "keywords": "senior engineer",
    "location": "Remote",
    "network": ["F"],
    "current_company": null,
    "max_pages": 1,
    "max_scrolls": 5
  }
}
```

Allowed `network` values match LinkedIn's people-search facet:

- `F`: 1st-degree contacts
- `S`: 2nd-degree contacts
- `O`: 3rd-degree and beyond

If omitted, `network` defaults to `["F"]`. `current_company` must be the numeric
LinkedIn company URN id used by the `currentCompany` people-search facet.

## Results

Successful `profile.get` result:

```json
{
  "type": "result",
  "protocol_version": "0.1",
  "command_id": "uuid",
  "status": "ok",
  "payload": {
    "profile_url": "https://www.linkedin.com/in/example/",
    "username": "example",
    "requested_sections": ["top_card", "about"],
    "raw_sections": {
      "top_card": "Visible profile text"
    },
    "structured_sections": {},
    "extraction_errors": [],
    "warnings": [],
    "visible_only": true,
    "extractor": "patchright",
    "extracted_at": "2026-07-01T00:00:00Z"
  },
  "error": null
}
```

Successful `network.search` result:

```json
{
  "type": "result",
  "protocol_version": "0.1",
  "command_id": "uuid",
  "status": "ok",
  "payload": {
    "search_url": "https://www.linkedin.com/search/results/people/?network=%5B%22F%22%5D",
    "keywords": null,
    "location": null,
    "network": ["F"],
    "current_company": null,
    "profiles": [
      {
        "username": "example",
        "profile_url": "https://www.linkedin.com/in/example/",
        "name": "Example Person",
        "degree": "1st",
        "raw": "Visible result card text"
      }
    ],
    "raw_text": "Visible search result text",
    "page_texts": ["Visible search result text"],
    "references": [
      {
        "kind": "person",
        "url": "/in/example/",
        "text": "Example Person",
        "context": "network_search"
      }
    ],
    "warnings": [],
    "visible_only": true,
    "extractor": "patchright",
    "extracted_at": "2026-07-01T00:00:00Z"
  },
  "error": null
}
```

Error result:

```json
{
  "type": "result",
  "protocol_version": "0.1",
  "command_id": "uuid",
  "status": "error",
  "payload": null,
  "error": {
    "code": "extraction_failed",
    "message": "Visible profile section could not be extracted",
    "retryable": true,
    "details": {}
  }
}
```

## Error Codes

- `auth_failed`
- `bridge_unavailable`
- `command_timeout`
- `extraction_failed`
- `invalid_request`
- `protocol_error`
- `unsupported_command`

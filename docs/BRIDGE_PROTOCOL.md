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

v0.1 allows only `profile.get`:

```json
{
  "type": "command",
  "protocol_version": "0.1",
  "command_id": "uuid",
  "command": "profile.get",
  "payload": {
    "profile_url": "https://www.linkedin.com/in/example/",
    "username": null,
    "sections": ["top_card", "about", "experience", "education", "skills"]
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

## Results

Successful result:

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


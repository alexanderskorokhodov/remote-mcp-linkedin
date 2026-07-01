# Security

## Boundary

The local bridge is the only component allowed to touch a browser. Cookies,
browser profiles, storage state, auth headers, browser fingerprint data, and
session state must stay on the bridge machine.

The server may store extracted profile, post, network, and dossier JSON, but it
must not receive or store browser authentication material.

## Authentication

The bridge authenticates with `REMOTE_MCP_LINKEDIN_BRIDGE_TOKEN` in the initial
`bridge.hello` protocol message. The server rejects bridge connections that:

- Do not send a valid hello message.
- Use the wrong token.
- Use an unsupported protocol version.

Use a long random token and do not commit it to source control.

## MCP Transport

The server uses stdio by default. It refuses `streamable-http` unless
`--enable-http` is explicitly provided.

v0.1 does not include built-in MCP HTTP authentication. If HTTP is enabled, bind
to loopback or put it behind a trusted authenticated gateway.

## Read-only Command Allowlist

The bridge only accepts read-only commands in v0.1:

- `profile.get`
- `network.search`

Unsupported commands are rejected with `unsupported_command`.

No write actions are implemented:

- No send message.
- No connect.
- No apply job.
- No follow.
- No like.
- No comment.

## Logging

Logs should never include:

- Bridge tokens.
- Cookies.
- Auth headers.
- Browser profile paths.
- Browser storage state.
- Full session state.

Profile URLs and extracted data can be personally identifiable. Keep logs and
result storage access-controlled.

## Known Risks

- LinkedIn terms and account restrictions may apply.
- Account checkpoints, captchas, rate limits, or suspicious activity systems can
  interrupt extraction.
- Extraction is limited to data visible to the logged-in local user.
- DOM and text layout changes can break extraction.
- The v0.1 Patchright extractor is experimental and partial.

# Example Showcase Extension

Reference Flow Steward extension bundle for extension authors.

This bundle is intentionally synthetic. It shows the shape of a complete local
subprocess extension without depending on a real third-party service.

## What It Demonstrates

| Area | Files |
|---|---|
| Runtime manifest v2 | `extension.yaml` |
| Distribution/import descriptor | `extension-descriptor.yaml` |
| Config and encrypted secret fields | `schemas/*.schema.yaml`, `ui/components/*form.yaml` |
| Declarative UI pages | `ui/ui_manifest.yaml`, `ui/pages/*.yaml`, `ui/components/*.yaml` |
| Queries and actions | `ui/queries/queries.yaml`, `ui/actions/actions.yaml`, `handlers/*.py` |
| Workflow trigger catalog | `workflow_triggers` in `extension.yaml` |
| Contract v2 builder operations | `contracts/*.yaml` |
| Demo workflows, agents, skills, tools, datasets, saved queries | `artifacts/*/*.yaml` |
| External API integration pattern | `handlers/actions.py::test_external_request` |
| OAuth2 connection-scoped credentials | `contracts/connection_types.yaml`, `handlers/actions.py::oauth_profile` |
| Health check | `health.py` |
| Interface translations | `locales/en.yaml`, `locales/lt.yaml` |

## Structure

```text
extensions/flowsteward_example_showcase/
  extension.yaml              # local runtime manifest
  extension-descriptor.yaml   # import/distribution descriptor
  main.py                     # subprocess JSON envelope entrypoint
  health.py                   # health command
  handlers/                   # query/action routing
  schemas/                    # project config, secret, subscription schemas
  ui/                         # declarative extension UI
  contracts/                  # Extension Contract v2 examples
  artifacts/                  # sole-source YAML artifact definitions
  locales/                    # interface translations, one flat YAML per language
  scripts/smoke_check.py      # local executable smoke
  tests/                      # bundle-level tests
```

## Runtime Contract

The runtime reads one JSON request from stdin and writes one JSON response to
stdout. Requests use the same envelope shape as other local extensions:

```json
{"mode":"query","query":{"query_id":"provider_health","context":{"project_id":"demo"}}}
```

```json
{"mode":"action","action":{"action_id":"test_external_request","input":{"resource_id":"demo-resource-1"}}}
```

The example external request action defaults to mock mode. Live requests require
`mock_mode=false`, an HTTPS `base_url`, an `allowed_hosts` match, and project
connection secrets injected under `target.connection.secrets`.

The `oauth_profile` action demonstrates the platform-owned OAuth2 flow. The
workflow step selects a project connection, Flow Steward refreshes/injects the
current access token into `target.connection.secrets.access_token`, and the
extension never receives the refresh token.

## Dataset Example

Installation is global and creates no project, project connection, or artifact
assignment. To run `demo_dataset_open_orders`, install and enable
`flowsteward.toolbox-dataset-connector`, create a PostgreSQL connection in the
target project, and assign the projected dataset to that project.
The dataset query resolves the selected connection from project scope at runtime;
the bundle contains no connection ID, SQLite metadata, or embedded database.

Active projected workflows can be assigned through ordinary project create/edit
or through the dedicated workflow-binding API. Flow Steward materializes a
minimal owner-marked registry anchor and persists the project binding in the same
transaction. Disabling or uninstalling the extension remains dependency-safe and
prevents new use without leaving an invalid project workflow reference.

## Localization

Every readable string the extension declares can be translated without
touching the declaration. `locales/<language>.yaml` is a flat map from a key to
its text; the user's language is used first, then `en`, then the text written
in the declaration itself, so a missing key never leaves an empty label.

```yaml
# locales/lt.yaml
page.configuration.title: Nustatymai
component.connection_form.field.base_url.label: Bazinis URL
component.connection_form.field.default_priority.option.low.label: Žemas
op.test_external_request.display_name: Gauti išorinę būseną
op.test_external_request.input.resource_id.display_name: Ištekliaus ID
```

Keys are derived from ids, never from positions or labels:

| Text | Key |
|---|---|
| Page title / description | `page.<page_id>.title`, `page.<page_id>.description` |
| Component title / description / content | `component.<component_id>.title` … |
| Form field label / help / placeholder | `component.<component_id>.field.<field_id>.label` … |
| Select option | `component.<component_id>.field.<field_id>.option.<value>.label` |
| Repeater field | `component.<component_id>.field.<field_id>.field.<path>.label` |
| Form section, buttons | `….section.<section_id>.title`, `….save_label`, `….test_label` |
| Table column, row action, empty state | `….column.<key>.label`, `….row_action.<id>.label`, `….empty_state` |
| Workflow operation and its inputs/outputs | `op.<operation_id>.display_name`, `op.<operation_id>.input.<name>.display_name` … |
| Step form | `step.<operation_id>.section`, `step.<operation_id>.field.<name>.label` |
| Connection type, query, category | `connection.<id>.display_name`, `query.<id>.display_name`, `category.<id>.display_name` |

Keep `en.yaml` complete: validation warns about a key in `en.yaml` that no
declaration uses and about a key in another language that `en.yaml` lacks.
Values that are not language (URLs, sample ids) stay out of the other
languages and fall back to English.

## Validate

```bash
docker compose -f infra/docker/docker-compose.yaml -f infra/docker/docker-compose.dev.yaml run --rm fs-app \
  python -m core.entrypoints.cli extensions test flowsteward.example-showcase
```

## Notes For Authors

- Keep author-facing extension contract files in YAML.
- Put non-secret project settings in `schemas/config.schema.yaml`.
- Put passwords, API tokens, webhook shared secrets, and similar values in
  `schemas/secrets.schema.yaml`.
- Sign callback deliveries with `HMAC-SHA256` over
  `<unix-timestamp>.<delivery-id>.<raw-body>` using the registration secret.
  The platform rejects signatures outside the declared five-minute window and
  atomically rejects a repeated delivery ID for the same registration.
- Declare requirements in the schema, not in your extension code. A flat
  `required` list can only say "always"; most integrations need "required
  **when**", which the platform executes as `allOf` with `if`/`then` keyed on
  the field whose value decides. `schemas/config.schema.yaml` shows one:
  turning `mock_mode` off means live outbound requests, which are refused
  without an allowlist, so `allowed_hosts` stops being optional. Declaring it
  is what makes it enforced on every path that writes a connection - and it is
  the same source the connection form reads when it marks a field required, so
  the form and the API cannot disagree.
- The platform executes `type`, `enum`, `const`, `required`, `properties`,
  `additionalProperties`, `items`, the length and range bounds, `oneOf`,
  `anyOf`, `allOf`, `if`/`then`/`else` and `dependentRequired`. Annotations
  (`title`, `description`, `default`, `examples`, `format`) are allowed and
  carry no assertion - `format` included, which is what JSON Schema itself
  says unless a format-assertion vocabulary is enabled.
- **Anything outside that list is refused when your extension is installed,
  not ignored.** That is deliberate: a validator that skips what it does not
  understand lets you ship a rule that never runs and never tells you.
- Model dev/prod or per-client credentials as separate named project
  connections, even when they use the same `connection_type_id`.
- Do not echo secret values from runtime actions or queries. Return redacted
  references or status only.
- Use `extension.yaml` for installed local runtime behavior.
- Use `extension-descriptor.yaml` to publish workflows, agents, skills, tools,
  datasets, saved queries, and Contract v2 builder operations through local YAML
  refs.

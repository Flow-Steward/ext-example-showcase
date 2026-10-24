# Example Showcase Extension

Reference Flow Steward extension bundle for extension authors.

This bundle is intentionally synthetic. It shows the shape of a complete local
subprocess extension without depending on a real third-party service.

## Requirements

This release speaks the host contract `extension_host_v2` with its final
execution scope (`group_id`, `for_each_id`, `step_id`, `step_execution_id`)
and is built on `flowsteward-extension-sdk` 0.4.0. A request with another
contract, a missing scope key, or both a Group and a For each as its owner is
refused before anything is read, sent or written. Its demo workflows use the
final workflow model: steps, Groups (parallel lanes), For each containers and
one execution graph; there are no phases. Install it on a Flow Steward Core
that speaks this contract; an older Core does not run it.

Logo: `icon.png` at the bundle root (the Flow Steward wave mark, PNG, 128x128).

## What's New in 1.2.1

The hook example now describes a hook as a place where a project adds its own
steps (nothing is connected to it; with no steps the order passes through
unchanged). `scripts/smoke_check.py` moved to `.github/scripts/` so the
release archive no longer contains it.

## What's New in 1.2.0

Four runnable developer examples, all deterministic (Set Variable, Transform,
If, Collect, Break, Continue; no connectors, no network):

| Workflow | Shows |
|---|---|
| `demo_order_with_client_hook` | A protected author workflow with a **hook**, a place where a client adds its own steps |
| `demo_group_sequence_and_lanes` | A Group that runs its steps once in sequence, and one that runs parallel lanes once |
| `demo_for_each_collect_controls` | A For each over a list with Collect `append` and `set_key`, Continue and Break |
| `demo_container_error_route` | A For each whose On error routes to a Stop · fail step |

See [Hooks For Extension Authors](#hooks-for-extension-authors) and
[Container Examples](#container-examples).

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
  .github/scripts/smoke_check.py  # local executable smoke (repository tooling, not packaged)
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

`demo_oauth_connection_binding` is a pattern only: the `example_showcase_oauth_account`
connection type points at the placeholder identity provider `idp.example.com`,
so the connection can never be authorized and a run stops at
`connection_resolution_failed`. Copy the pattern with a real provider's
authorization, token and revocation endpoints to run it.

## Project Connection Settings

Configuration uses the host-managed project connection form. Save the non-secret
settings and optional password/API token there; Flow Steward owns the project
connection record and encrypted secret storage. No extension action acknowledges
an in-memory echo as a saved configuration or credential.

After a full page reload, select **Edit** on the stored connection row to load
its authoritative values. Save updates that selected connection. **Test Request**
uses the selected saved connection, so save configuration changes before testing.
Resource ID and Perform Live Request are request inputs and are never stored as
connection configuration. Keep Mock Mode enabled and Perform Live Request off
for the deterministic example. Host allowlists remain arrays of host strings.

The v2 API connection schema matches the generic config schema, including
Mock Mode, Default Priority, Notification Channel, and optional existing labels.
The provider-side webhook secret field is removed; callback registration owns
its separately issued HMAC secret.

Bundle tests check native UI wiring, schema parity, and host-injected request
configuration. Actual save/reload durability and project/install isolation need
a running host acceptance test; the public SDK has no connection storage harness.

## Dataset Example

Installation is global and creates no project, project connection, or artifact
assignment. To run `demo_dataset_open_orders`, install and enable
the PostgreSQL data connector `flowsteward.data-connector-mcp-toolbox-postgres`
(MCP Toolbox for PostgreSQL), create a PostgreSQL connection in the
target project, and assign the projected dataset to that project.
The dataset query resolves the selected connection from project scope at runtime;
the bundle contains no connection ID, SQLite metadata, or embedded database.

Active projected workflows can be assigned through ordinary project create/edit
or through the dedicated workflow-binding API. Flow Steward materializes a
minimal owner-marked registry anchor and persists the project binding in the same
transaction. Disabling or uninstalling the extension remains dependency-safe and
prevents new use without leaving an invalid project workflow reference.

## Hooks For Extension Authors

A workflow you ship in an extension is a **protected author workflow** in the
client's account: the client can read its graph, run it and use it in a
project, but cannot change it. A hook is the place you leave for the client to
add its own steps. `demo_order_with_client_hook` is the worked example:
it prepares an order, reaches the hook "Adjust the order before it is
confirmed", then confirms the order, or skips it when the client's steps
ask to. With no steps added, the order passes through unchanged and is
confirmed.

### Declaring a hook

A hook is an ordinary `invoke_workflow` step whose config carries `hook`
instead of a `workflow_id`. It names no child and no child mappings: each
project adds its own steps to the hook.

```yaml
- step_id: adjust_order
  step_kind: invoke_workflow
  override:
    invoke_workflow:
      hook:
        hook_id: adjust_order              # stable [a-z][a-z0-9_]*, unique in the workflow
        contract_version: 1                # bump when the contract changes
        display_name: Adjust the order before it is confirmed
        description: Change the quantity or the delivery note, or skip the order.
        input_schema:                      # what the client's steps receive (JSON Schema object)
          type: object
          properties:
            customer: {type: string}
            quantity: {type: number, minimum: 1}
            delivery_note: {type: string}
          required: [customer, quantity, delivery_note]
        input_mapping:                     # where each input comes from in your state
          customer: state.order_customer
          quantity: state.order_quantity
          delivery_note: state.order_delivery_note
        mutable_fields: [quantity, delivery_note]   # inputs the client may replace; customer is read-only
        additional_outputs:                # output-only fields
          skip_order: {schema: {type: boolean}, default: false}   # required: needs a default
          client_comment: {schema: {type: string}, optional: true}
        stage_contract:                    # where the hook runs
          summary: After the order is prepared and before it is confirmed.
          effects_before: [order_prepared]
          effects_after: [order_confirmed]
```

Rules Core enforces when the bundle is installed: unknown fields are refused;
every `input_mapping` key is an `input_schema` property and every required
input has a source; `mutable_fields` are input names; an output-only field has
its own name (not an input's), and a required one (`optional` not set) needs a
`default` that fits its schema.

### Reading what came back

The whole hook output is published at `state.hooks.<hook_id>.output`: the
inputs (as passed, or as replaced in a mutable field), plus every output-only
field. Your own variables never change. Later steps read it:

```yaml
- step_id: should_skip_order
  step_kind: if
  override:
    if:
      condition: state.hooks.adjust_order.output.skip_order == true
- step_id: confirm_order
  step_kind: set_variable
  override:
    set_variable:
      assignments:
        state.final_order: {source: state.hooks.adjust_order.output}
```

**An empty hook** (the project added no steps): nothing runs, the output
is the inputs plus the declared defaults (`skip_order: false`, no
`client_comment`), and the step succeeds. A hook step has two outcomes:
Success and On error.

### What a client sees

- The author graph is read-only. The hook is drawn on the canvas like a Group,
  with its own header (**Hook**, the hook's name, **Empty** while it holds no
  steps) and the stage (`stage_contract`) in its drawer. The client picks a
  project and uses **Add step** inside the hook, then edits and test-runs those
  steps like any other. A step can finish the hook, and the hook's **Test Run**
  shows what it would publish.
- Steps are per project: each project adds different steps to the same hook,
  or none. Nothing is connected to the hook; behind the canvas Flow Steward keeps
  the steps in a hidden per-project workflow, created by the first step added.
- A hook's steps belong to one install of your extension. When a client
  uninstalls it and installs it again, the workflow gets a new id and every
  project has to add its hook steps again. If your release notes ask clients to
  reinstall, say so there.
- Automation can still bind a hook to an existing callable workflow through
  the API (`/api/projects/{p}/workflows/{w}/hooks/{hook_id}/bind`, `/unbind`,
  `/create-and-bind`), MCP and the CLI; this example does not use that.

### What a protected author workflow refuses

The client cannot test-run one of your steps on its own, apply changes to the
graph, clone the workflow, or export it in full: an export holds only a
reference to the extension workflow, never its steps. Do not set
`settings.portability.allow_full_export` unless you mean to give the structure
away; the examples here never do.

## Container Examples

- `demo_group_sequence_and_lanes`: the root starts a quote, the sequence Group
  "Prepare the quote" sets a header and then title-cases the customer name,
  the lanes Group "Price the quote" computes the subtotal and picks shipping
  in parallel, and the root assembles `quote_summary` from what both Groups
  wrote. A Group runs its body once; iteration is a For each.
- `demo_for_each_collect_controls`: a list-mode Transform trims and
  normalises five raw pick lines, then a For each walks them
  (`item_name: line`, `index_name: line_index`). A line marked `stop` hits
  Break, so the For each ends at once and leaves on success; a line marked
  `skip` hits Continue and the next line starts; every other line is
  collected twice: `append` adds its SKU to `picked_skus`, `set_key` writes its
  quantity under its SKU in `picked_quantity_by_sku`. Result:
  `[A-100, C-300]` and `{A-100: 2, C-300: 5}`. Both targets are created before
  the For each: Collect never creates a variable. Break and Continue have no
  outgoing edges.
- `demo_container_error_route`: a For each indexes order lines by SKU and has
  `error_policy: {on_error: route_to_step}` with an `error` edge to a Stop · fail
  step. A list-mode Transform trims the SKUs first. By default every line has
  a SKU and the run completes. Run it with `include_bad_line: true` and the
  line whose SKU is only spaces is trimmed to an empty SKU and fails its Collect, the
  step inherits its For each's policy, the For each fails, and its error edge
  stops the run with the reason from the Stop · fail step.

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

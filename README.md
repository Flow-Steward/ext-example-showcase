# Example Showcase Extension

Example Showcase is an SDK reference bundle for developers building Flow Steward extensions. Explore project connection forms, encrypted secrets, declarative pages, queries, actions, workflow trigger declarations and packaged workflows, agents, tools, datasets and saved queries. Example operations demonstrate an external status request, record scoring with partial failures and reusable tool invocation.

The included workflows show sequential and parallel Groups, For each loops, collection, Break and Continue, and container error routes. A worked order-processing example introduces hooks: places where each project can add its own steps to an extension's workflow. Use these examples to learn how extension features fit together before adapting the patterns to a real integration.

Install the bundle on a compatible Flow Steward host and create a project connection for the API example. This is a demonstration rather than an operational service: the default status response and review notifications are simulated, and the OAuth example uses a placeholder provider. A live API example needs your own HTTPS endpoint and credentials. The dataset example separately requires the PostgreSQL connector and a project database connection.

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

## What's New in 1.2.5

- The `events` callback is now declared under `callbacks:` in
  `extension.yaml` (HMAC-SHA256 signed, project-scoped) and routed to the new
  `receive_provider_event` action, so a provider delivery reaches the
  extension end to end. The **Callback Registration** panel's
  **Create and Configure** and **Refresh Status** buttons now call the new
  `configure_webhook` and `get_webhook_status` actions (a mock provider). See
  [Workflow trigger, event bindings and callbacks](#workflow-trigger-event-bindings-and-callbacks).
- The panel shows the real callback path,
  `/webhook/extensions/flowsteward.example-showcase/events/<token>`.
- `demo_dataset_open_orders` no longer claims a bundled sales fixture: it
  reads the `orders` table through the project's own PostgreSQL connection.
- The descriptor's `support_url` points at this repository's issues.

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
| Signed provider callback | `callbacks` in `extension.yaml`, `handlers/actions.py::receive_provider_event` |
| OAuth2 connection-scoped credentials | `contracts/connection_types.yaml`, `handlers/actions.py::oauth_profile` |
| Health check | `health.py` |
| Interface translations | `locales/en.yaml`, `locales/lt.yaml` |
| Logo | `icon.png` |
| Network destinations | `egress` in `extension.yaml` |
| Tests, smoke check, packaging | `tests/`, `.github/scripts/`, `release/checks.py` |

## Feature Tour

Each part below names the files to read. Install the extension, open it under
**Extensions**, and compare what you see with the files.

### Manifest

`extension.yaml` declares a `tool_provider` with the features `tool`, `action`,
`query`, `workflow_trigger` and `artifact_bundle`, and:

- `runtime.contract_version: extension_host_v2`, required by Core;
- `egress`: the default API host `api.example.test` plus the `base_url` field
  of the `example_showcase_api` connection, so the administrator sees where the
  extension connects;
- `required_scopes`, `machine_auth` and `account_scope` (project-scoped
  configuration), which marketplace validation requires;
- an optional dependency on `flowsteward.telegram` (`required: false`), to show
  extension-to-extension dependency metadata;
- `callbacks`: the signed `events` callback a provider posts to (see
  [Workflow trigger, event bindings and callbacks](#workflow-trigger-event-bindings-and-callbacks));
- the UI, query and action manifests, and the six Contract v2 files.

### UI pages

`ui/ui_manifest.yaml` lists four pages; each page lists its components from
`ui/components/`:

| Page | Components |
| --- | --- |
| **Overview** (`overview`) | `markdown` introduction, `health_panel` bound to `provider_health`, `stats_row` with artifact counts from the same query, `callback_setup` panel |
| **Configuration** (`configuration`) | `connection_form`: the host-managed project connection form for `example_showcase_api` (settings, secrets, and **Test Request** through `test_external_request`); see [Project Connection Settings](#project-connection-settings) |
| **Operations** (`operations`) | `markdown` overview, `grid` of Contract v2 operations (`operation_contracts`), `form` with a repeater that runs `batch_score_records`, `form` that runs `send_review_notification` |
| **Demo Artifacts** (`artifacts`) | `markdown` overview and three `grid`s: workflows, agents, tools |

### Queries

Declared in `ui/queries/queries.yaml`, implemented in `handlers/queries.py`:

| Query | Returns |
| --- | --- |
| `provider_health` | Runtime health, project scope status and artifact counts |
| `list_demo_workflows`, `list_demo_agents`, `list_demo_tools` | The artifacts this extension publishes |
| `list_example_resources` | Rows for a resource picker in a workflow step form |
| `operation_contracts` | The Contract v2 operations, for the Operations grid |

### Actions

Declared in `ui/actions/actions.yaml`, implemented in `handlers/actions.py`.
None mutates the platform (`mutates_platform: false`).

| Action | Visible in workflows | Shows |
| --- | --- | --- |
| `test_external_request` | Yes | A safe outbound request: mock mode by default; live mode needs HTTPS, an `allowed_hosts` match and connection secrets |
| `send_review_notification` | Yes | The output shape of a notification dispatch |
| `batch_score_records` | Yes | A bulk action with per-record results and partial failure |
| `run_demo_tool` | Yes | Running a bundled deterministic tool |
| `invoke_tool` | Yes | The action behind the published tool artifacts; may write a file artifact through a host grant |
| `oauth_profile` | Yes | Receiving the OAuth access token of the selected connection |
| `receive_provider_event` | No | Handling a signed delivery on the `events` callback: returns a bounded summary (event type and id, at most 20 top-level keys, body size and SHA-256), never the headers or the body |
| `configure_webhook` | No | Handing the callback URL and signing secret to the provider; the example provider is a mock, so nothing is sent or echoed |
| `get_webhook_status` | No | The provider-side webhook status for the **Refresh Status** button (mock) |

### Workflow operations (Extension tools step)

An action shows up under **Extension tools** in the workflow builder because
it is `workflow_visible: true` **and** `contracts/operation_manifest.yaml`
declares an operation with the same id. The showcase covers each operation
kind: `test_external_request` is a `source`, `send_review_notification` a
`human_channel`, `batch_score_records` a `bulk_action` (`supports_batch`,
batch size 25, at most 100, input field `records`), and `run_demo_tool`,
`invoke_tool`, `oauth_profile` are `action`s.

- `contracts/step_ui_manifest.yaml`: the step form fields for each operation.
- `contracts/resource_query_manifest.yaml`: resource pickers backed by
  `list_example_resources` and the artifact lists.
- `contracts/connection_types.yaml`: `example_showcase_api` (API settings and
  secrets) and `example_showcase_oauth_account` (OAuth2 authorization code with
  PKCE).
- `contracts/artifact_policies.yaml`: the files an operation may read or write.

This is also how you add your own code to workflows: Flow Steward has no code
step, so custom logic is an extension action exposed this way.

### Settings and secrets

- `schemas/config.schema.yaml`: non-secret settings (`base_url`, `username`,
  `tenant`, `allowed_hosts`, `mock_mode`, `default_priority`,
  `notification_channel`, `labels`). Turning `mock_mode` off makes
  `allowed_hosts` required, through `if`/`then` in the schema.
- `schemas/secrets.schema.yaml`: password and API token. Flow Steward stores
  them in the project connection's encrypted secret storage; the callback
  signing secret is issued by callback registration, not stored here.
- `schemas/subscriptions.schema.yaml`: which events to subscribe to, a
  severity filter and an optional workflow filter.

### Workflow trigger, event bindings and callbacks

- `workflow_triggers` in `extension.yaml` adds the trigger type
  **Example Showcase Event** (`example_showcase_event`) to the workflow
  trigger catalog, with its own config form (source, signature requirement,
  default priority). It maps a provider event (`external.comment.received`)
  into a workflow run.
- `contracts/event_bindings.yaml` binds platform events to operations:
  `approval.requested` to `send_review_notification`, `job.completed` to
  `test_external_request`, `interaction.received` to `run_demo_tool`.
- `callbacks:` in `extension.yaml` declares the `events` callback:
  `purpose: inbound_events`, `methods: [POST]`, `connection_scoped: false`
  (one registration per project), `action_id: receive_provider_event`, and
  `auth.type: hmac_sha256` with the headers `X-Example-Showcase-Signature`,
  `X-Example-Showcase-Timestamp` and `X-Example-Showcase-Delivery` and
  `max_age_seconds: 300`. A provider posts to
  `/webhook/extensions/flowsteward.example-showcase/events/<token>`. Core checks
  the signature, the timestamp window and the delivery id (see
  [Notes For Authors](#notes-for-authors)) before it runs the action, and hands
  the action the parsed JSON body, the raw body and the headers with the
  signature redacted.
- `ui/components/callback_setup.yaml` shows the registration panel for that
  callback. **Create and Configure** creates the project's registration and
  calls `configure_webhook` with the callback URL and its signing secret;
  **Refresh Status** calls `get_webhook_status`. A real extension calls its
  provider's webhook API in those two actions; here they are a mock. Create and
  Configure needs `FS_PUBLIC_BASE_URL` set to a non-localhost address, because
  Core never hands a provider a URL built from request headers.

### Tools, workflows, agents and skills

`extension-descriptor.yaml` publishes everything under `artifacts/`:

- **Tools** (`artifacts/tools/`): `demo_content_tools`, `demo_weather_tools`,
  `demo_product_catalog_tools`. Their functions live in
  `demo_workflow_tools.py`, run through the `invoke_tool` action, and are
  deterministic; `demo_store_product_catalog_artifact` writes a CSV file
  artifact.
- **Workflows** (`artifacts/workflows/`), 14 of them:

  | Workflow | Shows |
  | --- | --- |
  | `demo_weather_city_brief` | If, Switch, HTTP request (a no-key Open-Meteo forecast), Extension tools, Stop · success |
  | `demo_weather_summary_child`, `demo_travel_day_planner` | A callable child workflow and Invoke workflow with output mapping |
  | `demo_content_campaign_router` | Switch branches per content channel |
  | `demo_parallel_launch_review` | Agent steps in parallel lanes, then a merge |
  | `demo_product_catalog_enrichment` | CSV loading, For each validation, Batch, enrichment and a file artifact |
  | `demo_dataset_open_orders` | A saved dataset query (see [Dataset Example](#dataset-example)) |
  | `demo_incoming_webhook_router` | Routing fields of an incoming webhook |
  | `demo_oauth_connection_binding` | A step whose OAuth connection is picked per project |
  | `demo_expected_failure_guardrail` | A run that ends at Stop · fail on purpose |
  | `demo_order_with_client_hook` | A hook ([Hooks For Extension Authors](#hooks-for-extension-authors)) |
  | `demo_group_sequence_and_lanes`, `demo_for_each_collect_controls`, `demo_container_error_route` | Groups, For each controls and error routes ([Container Examples](#container-examples)) |

- **Agents and skills** (`artifacts/agents/`, `artifacts/skills/`): five
  agent/skill pairs used by the agent steps (support ticket classifier and
  summarizer, launch copywriter, launch risk reviewer, change request risk
  router).
- **Datasets and saved queries**: `demo_sales_open_orders` and
  `demo_open_orders_query`.

### Health

`health.py` loads `main.py` and each handler module and prints one check per
file. The **Overview** page's health panel uses the `provider_health` query
instead, which also reports configuration and artifact counts.

### Dependencies and wheels

The showcase imports only the Python standard library and the Flow Steward
SDK, which the host provides, so `extension.yaml` has no `python_requirements`
and the archive has no `wheels/`. `dev-wheels/` holds the SDK wheel that
`requirements-dev.txt` installs for the tests; it is never packaged. An
extension with third-party libraries must ship hash-pinned wheels for both
Linux x86_64 and aarch64; see the Flow Steward guide *Build An Extension*,
section *Python Dependencies And Wheel Distribution*.

### Tests and scripts

| File | Runs |
| --- | --- |
| `tests/test_example_showcase.py` | Manifest and descriptor, health and queries, the external request (mock and live), OAuth token, artifact grants, the batch action, the `events` callback and its setup actions, envelope refusal, logo, workflow model and the hook |
| `tests/test_descriptor_compatibility.py` | The descriptor declares a minimum Flow Steward version |
| `tests/test_demo_workflow_tools.py` | The deterministic tool functions |
| `tests/test_showcase_release_checks.py` | The release-candidate checks |
| `tests/test_vendored_wheels.py` | Platform markers on wheels pinned in `requirements-dev.txt` |
| `.github/scripts/smoke_check.py` | Health plus representative queries and actions (repository tooling, not packaged) |
| `.github/scripts/package_extension.py`, `.github/scripts/catalog_check.py` | Builds the archive the catalog publishes and checks it |
| `release/checks.py` | Checks this bundle on a release candidate through the public API only |

## Structure

```text
flowsteward_example_showcase/   # the folder name Flow Steward expects for this id
  extension.yaml              # local runtime manifest
  extension-descriptor.yaml   # import/distribution descriptor
  icon.png                    # logo, required
  main.py                     # subprocess JSON envelope entrypoint
  health.py                   # health command
  demo_workflow_tools.py      # deterministic tool functions
  fixtures/                   # sample CSV for the product catalog demo
  handlers/                   # query/action routing
  schemas/                    # project config, secret, subscription schemas
  ui/                         # declarative extension UI
  contracts/                  # Extension Contract v2 examples
  artifacts/                  # sole-source YAML artifact definitions
  locales/                    # interface translations, one flat YAML per language
  .github/scripts/smoke_check.py  # local executable smoke (repository tooling, not packaged)
  release/                    # release-candidate checks over the public API
  tests/                      # bundle-level tests
  requirements-dev.txt        # test dependencies
  dev-wheels/                 # SDK wheel for tests (not packaged)
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

Flow Steward finds an extension by its folder name: for this id it must be
`flowsteward_example_showcase`. Copy this repository into a Flow Steward
Development checkout as `extensions/flowsteward_example_showcase/`, then run
from the checkout:

```bash
./flow-steward extensions validate flowsteward.example-showcase --root extensions --health
./flow-steward extensions test flowsteward.example-showcase --root extensions
./flow-steward extensions bundle flowsteward.example-showcase --root extensions --confirm
```

Install the archive with **Extensions › Install extension from file**, or
install the published release from **Extensions › Marketplace**.

## Notes For Authors

- Keep author-facing extension contract files in YAML.
- Put non-secret project settings in `schemas/config.schema.yaml`.
- Put passwords, API tokens, webhook shared secrets, and similar values in
  `schemas/secrets.schema.yaml`.
- Sign callback deliveries with `HMAC-SHA256` over
  `<unix-timestamp>.<delivery-id>.<raw-body>` using the registration secret,
  and send the hex digest (optionally prefixed `sha256=`), the timestamp and
  the delivery id in the headers the callback's `auth` names.
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

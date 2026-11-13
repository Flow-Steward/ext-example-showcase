# Workflow actions

Use the bundled example project connections where the action requires one. These actions demonstrate SDK contracts and deterministic sample data; configure a real provider only for the documented live-request example.

Select the connection in the workflow step. Map returned message IDs, file handles or dataset handles into later steps rather than pasting credentials or local paths.

## Fetch example external status (`test_external_request`)

Demonstrates a safe external API request pattern with HTTPS and host allowlisting. Use the bundled example project connections where the action requires one. These actions demonstrate SDK contracts and deterministic sample data; configure a real provider only for the documented live-request example. Example: Use resource_id=demo-resource-1 with live requests disabled to explore the request result without contacting a provider.

Inputs:

- `resource_id`: External resource identifier to include in the example status request.
- `resource_picker`: Choose a resource from the bundled example resource query, then use its identifier in Resource ID.
- `perform_live_request`: Leave disabled for a deterministic response. Enable only with a configured HTTPS base URL and allowed host; mock_mode=true still suppresses network calls.

Result fields: `status`, `external_request`.

## Prepare example review notification (`send_review_notification`)

Return a simulated review-notification delivery result with a deterministic message ID. Use the bundled example project connections where the action requires one. These actions demonstrate SDK contracts and deterministic sample data; configure a real provider only for the documented live-request example. Example: Submit a warning-severity review message to inspect the simulated delivery result and message preview.

Inputs:

- `message`: Review message included in the example notification request.
- `severity`: Choose info, warning or critical for the example notification payload.

Result fields: `delivered`, `provider_message_id`.

## Score example records (`batch_score_records`)

Demonstrates a bulk operation contract with partial failure reporting. Use the bundled example project connections where the action requires one. These actions demonstrate SDK contracts and deterministic sample data; configure a real provider only for the documented live-request example. Example: Score records [{"id":"order-100","active":true},{"id":"order-101","active":false}] and route the failed_records separately.

Inputs:

- `records`: List of JSON record objects with id (or record_id). Records with a missing ID or active=false are reported in failed_records.
- `batch_policy`: Host batch-processing policy for this example repeater. The scoring result reports scored_records and failed_records separately.

Result fields: `scored_records`, `failed_records`.

## Run example catalog tool (`run_demo_tool`)

Demonstrates mapping a workflow connector step to a bundled deterministic tool artifact. Use the bundled example project connections where the action requires one. These actions demonstrate SDK contracts and deterministic sample data; configure a real provider only for the documented live-request example. Example: Select demo_content_tools and pass {"topic":"launch"} to inspect the returned tool metadata and payload echo.

Inputs:

- `tool_id`: Choose a bundled demo tool ID from the tool catalog, such as demo_content_tools. This action returns catalog metadata and echoes payload.
- `payload`: JSON object echoed by the selected catalog tool; use it to explore input mapping.

Result fields: `tool_result`.

## Invoke bundled example tool (`invoke_tool`)

Invokes a bundled demo tool and may publish an allowed run-window artifact. Use the bundled example project connections where the action requires one. These actions demonstrate SDK contracts and deterministic sample data; configure a real provider only for the documented live-request example. Example: Call demo_measure_text with arguments {"value":"Launch update"} to inspect the deterministic tool result.

Inputs:

- `tool_name`: Bundled callable name. Use demo_measure_text for text metrics; see workflow-actions.md for other supported tools.
- `arguments`: JSON object containing arguments accepted by the chosen bundled callable. For demo_measure_text, supply text.

Result fields: `result`.

## Inspect example OAuth connection (`oauth_profile`)

Demonstrates runtime access-token injection for an OAuth-backed project connection. Use the bundled example project connections where the action requires one. These actions demonstrate SDK contracts and deterministic sample data; configure a real provider only for the documented live-request example. Example: Check that a configured OAuth example connection receives an access token at runtime without returning the token.

Result fields: `token_received`, `refresh_token_visible`, `connection_id`.

Supported `invoke_tool` names: `demo_load_product_catalog`, `demo_enrich_product_catalog`, `demo_store_product_catalog_artifact`, `demo_weather_brief`, `demo_measure_text`, `demo_compose_content_brief`, `demo_merge_launch_review`. Each callable has its own argument shape; inspect the bundled tools and workflow artifacts before changing the selected tool.

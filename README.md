# Taiga for Home Assistant

A custom Home Assistant integration for [Taiga](https://taiga.io/) project management. View and manage kanban board items (user stories, tasks) directly from your Home Assistant dashboard.

## Features

- View user stories and tasks in a kanban board or list layout
- Change item status via dropdowns
- Create new user stories and tasks
- Filter by epic
- Responsive design: kanban on desktop, list on mobile
- Configurable polling interval via options flow

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu (top right) and select **Custom repositories**
3. Add `https://github.com/edmundhighcock/ha-taiga` with category **Integration**
4. Search for "Taiga" and install
5. Restart Home Assistant

### Manual

1. Copy `custom_components/taiga/` to your Home Assistant `config/custom_components/taiga/` directory
2. Copy `www/taiga-board-card.js` to `config/www/taiga-board-card.js`
3. Restart Home Assistant

## Configuration

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for **Taiga**
3. Enter your Taiga instance URL (e.g., `http://localhost:8001`)
4. Choose authentication method:
   - **Username & Password** — your Taiga credentials
   - **Application Token** — generated in Taiga Settings
5. Select which projects to track

### Options

After setup, click **Configure** on the integration to adjust:
- **Scan interval** — how often to poll Taiga for updates (default: 30 seconds, min: 5, max: 3600)

## Lovelace Card Setup

### Register the card resource

Go to **Settings > Dashboards > Resources** and add:
- URL: `/local/taiga-board-card.js`
- Type: JavaScript Module

### Add the card

```yaml
type: custom:taiga-board-card
entity: sensor.taiga_your_project_slug
```

### Card configuration options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `entity` | string | *required* | Sensor entity ID |
| `title` | string | project name | Card title |
| `item_type` | string | `user_story` | `user_story`, `task`, or `both` |
| `view_mode` | string | `auto` | `kanban`, `list`, or `auto` (responsive) |
| `show_tags` | boolean | `true` | Show item tags |
| `show_assignee` | boolean | `true` | Show assigned user |
| `show_epic` | boolean | `true` | Show epic label |
| `show_add_form` | boolean | `true` | Show the "Add item" form |
| `epic_filter` | string/number | `null` | Filter items by epic name (substring match) or epic ID |
| `statuses` | list | all | List of status names to show |

> **A note on statuses and `item_type: both`.** Taiga keeps a *separate*
> status table for user stories and for tasks — different names, and ids
> that are independent sequences, so they overlap (a task's "New" and a
> story's "Todo" can both be id 1, and "In progress" can exist in both
> under different ids). With `item_type: both` the card resolves each
> row's statuses from that row's own type, and labels the group headings
> `stories` or `tasks` so two same-named groups stay distinguishable.
> `statuses:` filters by name within each type.

### Example: filtered kanban

```yaml
type: custom:taiga-board-card
entity: sensor.taiga_my_project
item_type: both
epic_filter: "Sprint 3"
statuses:
  - New
  - In progress
  - Ready for test
  - Done
```

## Services

| Service | Description |
|---------|-------------|
| `taiga.change_status` | Change an item's status |
| `taiga.create_user_story` | Create a new user story |
| `taiga.create_task` | Create a new task |
| `taiga.update_user_story` | Modify an existing user story's subject, description, or tags |
| `taiga.update_task` | Modify an existing task's subject or description |
| `taiga.add_comment` | Add a comment to a user story, task, issue, or epic |
| `taiga.refresh` | Force a data refresh |

`update_user_story` and `update_task` require at least one of their
optional fields; `add_comment` requires non-empty `comment` text. Taiga
needs each item's current `version` for these writes (optimistic
concurrency): the integration fetches it automatically and, if a 400
shows the version went stale in the meantime, re-fetches and retries
once before giving up.

## Development

```bash
make setup          # install Python test dependencies into venv/
make test           # everything — Python integration + JavaScript card
make test-py        # integration only (pytest)
make test-js        # card only (node --test; needs Node 18+, no npm install)
```

The card tests in `tests/js/` render `www/taiga-board-card.js` against a
minimal DOM stub and assert on the resulting HTML — chiefly that a row's
status options, its displayed status, and its grouping all come from its
own object type's status table. To check the suite against another
revision of the card:

```bash
git show <rev>:www/taiga-board-card.js > /tmp/old-card.js
TAIGA_CARD_PATH=/tmp/old-card.js make test-js
```

## License

MIT
